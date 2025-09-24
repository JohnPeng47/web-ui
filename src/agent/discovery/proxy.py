import asyncio
import inspect
import contextlib
import logging
import threading
import socket
import time
from typing import Optional, Dict, Any
from common.constants import BROWSER_PROXY_HOST, BROWSER_PROXY_PORT

try:
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import http
    from mitmproxy import log as mitm_log
except ImportError as e:
    raise ImportError(
        "mitmproxy is required. Install with: pip install mitmproxy"
    ) from e

from logger import get_agent_loggers
from common.http_handler import HTTPHandler
from httplib import (
    HTTPRequest,
    HTTPResponse,
    HTTPRequestData,
    HTTPResponseData,
    post_data_to_dict,
)

agent_log, _ = get_agent_loggers()
agent_log.propagate = False


def _detach_mitm_logging_handlers() -> None:
    """Detach mitmproxy logging handlers to prevent event loop errors during shutdown."""
    root = logging.getLogger()
    mitm_handler_cls = getattr(mitm_log, "MitmLogHandler", None)
    for handler in list(root.handlers):
        try:
            is_mitm = False
            if mitm_handler_cls is not None and isinstance(handler, mitm_handler_cls):
                is_mitm = True
            elif handler.__class__.__name__ == "MitmLogHandler":
                is_mitm = True
            if is_mitm:
                root.removeHandler(handler)
                with contextlib.suppress(Exception):
                    handler.close()
        except Exception:
            with contextlib.suppress(Exception):
                handler.close()


class MitmProxyHTTPHandler:
    """
    Proxy-server implementation of the same interface as CDPHTTPHandler.

    What it does:
      - Starts a mitmproxy HTTPS/HTTP proxy (in a background thread).
      - For every flow, forwards a synthesized HTTPRequest to handler.handle_request(...)
        and then an HTTPResponse to handler.handle_response(...).
      - Delegates flush()/get_history() to your HTTPHandler.

    Notes:
      - You must trust mitmproxy's CA on the client/browser making requests
        to intercept HTTPS. Default CA path: ~/.mitmproxy
      - Point your browser/app at http://<listen_host>:<listen_port> as an HTTP(S) proxy.
      - This is passive with respect to traffic modification (no edits).
    """

    def __init__(
        self,
        handler: HTTPHandler,
        *,
        listen_host: str = BROWSER_PROXY_HOST,
        listen_port: int = BROWSER_PROXY_PORT,
        ssl_insecure: bool = True,
        http2: bool = True,
        handler_name: Optional[str] = None,
        start_browser: bool = False,
    ) -> None:
        self._handler = handler
        self._handler_name = handler_name or f"mitm_handler_{id(self)}"

        self._listen_host = listen_host
        self._listen_port = listen_port
        self._ssl_insecure = ssl_insecure
        self._http2 = http2
        self._start_browser = start_browser

        self._master: Optional[DumpMaster] = None
        self._task: Optional[asyncio.Task] = None
        self._browser_task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._alive = False

        # We need the loop where handler coroutines should run
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        agent_log.info(
            "Initialized MitmProxyHTTPHandler '%s' on %s:%d",
            self._handler_name,
            self._listen_host,
            self._listen_port,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public API (mirrors CDPHTTPHandler)
    # ─────────────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._connected:
            agent_log.info("Handler '%s' already connected", self._handler_name)
            return

        # Capture the loop where we will schedule handler coroutines
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError as e:
            raise RuntimeError("connect() must be called from within an asyncio loop") from e

        # Start browser if requested
        if self._start_browser:
            await self._start_browser_instance()

        # Wait briefly for port to be released from any previous run
        released = await self._wait_for_port_release(self._listen_host, self._listen_port, timeout=3.0)
        if not released:
            agent_log.warning(
                "Port %s:%d still in use after grace period; attempting start anyway",
                self._listen_host,
                self._listen_port,
            )

        options = Options(
            listen_host=self._listen_host,
            listen_port=self._listen_port,
            http2=self._http2,
            ssl_insecure=self._ssl_insecure,
        )

        self._master = DumpMaster(options, with_termlog=False, with_dumper=False)
        self._master.addons.add(_RelayAddon(self))

        self._alive = True

        def _run_mitm_blocking() -> None:
            try:
                agent_log.info(
                    "Starting mitmproxy on %s:%d (http2=%s ssl_insecure=%s)",
                    self._listen_host,
                    self._listen_port,
                    self._http2,
                    self._ssl_insecure,
                )
                if self._master is not None:
                    result = self._master.run()
                    if inspect.iscoroutine(result):
                        asyncio.run(result)
            except Exception:
                agent_log.exception("mitmproxy master crashed")
            finally:
                agent_log.info("mitmproxy master exited")
                self._alive = False
                _detach_mitm_logging_handlers()

        self._thread = threading.Thread(
            target=_run_mitm_blocking,
            name=f"mitm-thread-{self._listen_port}",
            daemon=True,
        )
        self._thread.start()

        self._connected = True

    async def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            if self._master:
                # orderly shutdown of mitmproxy
                self._master.shutdown()
            
            if self._thread is not None:
                self._thread.join(timeout=8.0)
                if self._thread.is_alive():
                    agent_log.warning("mitm proxy thread did not stop within timeout")
            
            # Stop browser if we started it
            if self._browser_task and not self._browser_task.done():
                self._browser_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._browser_task
            # small pause to ensure sockets fully released
            await asyncio.sleep(0.05)

        finally:
            _detach_mitm_logging_handlers()
            self._master = None
            self._task = None
            self._thread = None
            self._browser_task = None
            self._connected = False
            agent_log.info("Handler '%s' disconnected", self._handler_name)

    async def _wait_for_port_release(self, host: str, port: int, *, timeout: float = 3.0, interval: float = 0.1) -> bool:
        """Poll until a TCP bind to (host, port) succeeds or timeout elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._can_bind(host, port):
                return True
            await asyncio.sleep(interval)
        return self._can_bind(host, port)

    @staticmethod
    def _can_bind(host: str, port: int) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
        except OSError:
            return False
        finally:
            with contextlib.suppress(Exception):
                s.close()

    async def flush(self):
        # If mitm died, either return what you have or raise a controlled error.
        if not self._alive:
            return await self._handler.flush()
        return await self._handler.flush()

    def get_history(self):
        return self._handler.get_history()

    @property
    def proxy_url(self) -> str:
        return f"http://{self._listen_host}:{self._listen_port}"

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────────────────────────────
    # Browser management
    # ─────────────────────────────────────────────────────────────────────
    async def _start_browser_instance(self) -> None:
        """Start a browser instance configured to use this proxy."""
        try:
            from common.constants import BROWSER_PROFILE_DIR, BROWSER_CDP_PORT
            from playwright.async_api import async_playwright
            
            agent_log.info("Starting browser with proxy configuration")
            
            async def _run_browser():
                pw = None
                browser = None
                try:
                    pw = await async_playwright().start()
                    browser = await pw.chromium.launch_persistent_context(
                        user_data_dir=str(BROWSER_PROFILE_DIR),
                        headless=True,
                        executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
                        args=[
                            f"--remote-debugging-port={BROWSER_CDP_PORT}", 
                            "--remote-debugging-address=127.0.0.1",
                            f"--proxy-server={self.proxy_url}"
                        ],
                    )
                    
                    agent_log.info("Browser started with proxy %s", self.proxy_url)
                    
                    # Keep browser running until cancelled
                    while True:
                        await asyncio.sleep(1)
                        
                except asyncio.CancelledError:
                    agent_log.info("Browser shutdown requested")
                    raise
                except Exception as e:
                    agent_log.error("Browser error: %s", e)
                finally:
                    if browser:
                        try:
                            await browser.close()
                            agent_log.info("Browser closed")
                        except Exception as e:
                            agent_log.error("Error closing browser: %s", e)
                    
                    if pw:
                        try:
                            await pw.stop()
                            agent_log.info("Playwright stopped")
                        except Exception as e:
                            agent_log.error("Error stopping playwright: %s", e)
            
            self._browser_task = asyncio.create_task(_run_browser())
            
        except ImportError as e:
            agent_log.warning("Could not start browser - missing dependencies: %s", e)
        except Exception as e:
            agent_log.error("Failed to start browser: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # Addon → handler bridging
    # ─────────────────────────────────────────────────────────────────────
    def _schedule_coro(self, coro) -> None:
        loop = self._loop
        if loop is None:
            return
        if loop.is_closed():
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError as e:
            # loop is closing/closed
            agent_log.debug("Dropped handler coroutine: %s", e)
            return
        def _log_err(_fut) -> None:
            exc = _fut.exception()
            if exc:
                agent_log.exception("Handler coroutine failed: %s", exc)
        fut.add_done_callback(_log_err)

    def _flow_to_http_request(self, flow: "http.HTTPFlow") -> HTTPRequest:
        """
        Map mitmproxy flow.request to your HTTPRequest.
        """
        headers: Dict[str, str] = {k.lower(): v for k, v in flow.request.headers.items()}
        post_dict: Optional[Dict[str, Any]] = None

        ctype = headers.get("content-type", "")
        try:
            # Try urlencoded first
            if "application/x-www-form-urlencoded" in ctype and flow.request.urlencoded_form:
                post_dict = {k: v for k, v in flow.request.urlencoded_form.items(multi=False)}
            # Fallback to JSON
            elif "application/json" in ctype:
                try:
                    post_dict = flow.request.json()
                except Exception:
                    txt = flow.request.get_text(strict=False)
                    if txt and txt.strip().startswith("{") and txt.strip().endswith("}"):
                        import json  # local import to avoid module load if unused
                        post_dict = json.loads(txt)
            # Last resort: plain text
            else:
                txt = flow.request.get_text(strict=False)
                if txt:
                    # Reuse your existing helper to parse common cases
                    post_dict = post_data_to_dict(txt)
        except Exception:
            post_dict = None  # do not fail ingestion on parsing errors

        data = HTTPRequestData(
            method=flow.request.method,
            url=flow.request.url,
            headers=headers,
            post_data=post_dict,
            redirected_from_url=None,
            redirected_to_url=None,
            is_iframe=False,
        )
        request = HTTPRequest(data=data)
        # agent_log.info(f"Request: {request}")
        
        return request

    def _flow_to_http_response(self, flow: "http.HTTPFlow") -> HTTPResponse:
        """
        Map mitmproxy flow.response to your HTTPResponse.
        """
        headers: Dict[str, str] = {k.lower(): v for k, v in flow.response.headers.items()}
        body_bytes: Optional[bytes] = None
        try:
            body_bytes = flow.response.raw_content if flow.response.raw_content is not None else None
        except Exception:
            body_bytes = None

        data = HTTPResponseData(
            url=flow.request.url,
            status=flow.response.status_code,
            headers=headers,
            is_iframe=False,
            body=body_bytes,
            body_error=None,
        )
        # agent_log.info(f"Response: {data}")
        return HTTPResponse(data=data)

class _RelayAddon:
    """
    mitmproxy addon that relays request/response events into MitmProxyHTTPHandler.
    """

    def __init__(self, outer: MitmProxyHTTPHandler) -> None:
        self.outer = outer

    def request(self, flow: http.HTTPFlow) -> None:
        try:
            url = flow.request.pretty_url
            # Optional ban-list hook from user's HTTPHandler
            if getattr(self.outer._handler, "_is_banned", lambda u: False)(url):
                return
            http_request = self.outer._flow_to_http_request(flow)
            self.outer._schedule_coro(self.outer._handler.handle_request(http_request))
        except Exception:
            agent_log.exception("Failed to relay request")

    def response(self, flow: http.HTTPFlow) -> None:
        try:
            url = flow.request.pretty_url
            if getattr(self.outer._handler, "_is_banned", lambda u: False)(url):
                return
            http_response = self.outer._flow_to_http_response(flow)
            http_request = self.outer._flow_to_http_request(flow)
            self.outer._schedule_coro(
                self.outer._handler.handle_response(http_response, http_request)
            )
        except Exception:
            agent_log.exception("Failed to relay response")

    def error(self, flow: http.HTTPFlow) -> None:
        # You could synthesize an error HTTPResponse and forward it if needed.
        pass


# Optional context manager, mirroring your CDPConnection
class ProxyConnection:
    def __init__(self, handler: MitmProxyHTTPHandler):
        self.handler = handler

    async def __aenter__(self):
        await self.handler.connect()
        return self.handler

    async def __aexit__(self, exc_type, exc, tb):
        await self.handler.disconnect()
