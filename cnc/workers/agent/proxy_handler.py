import asyncio
import logging
import threading
from typing import Optional, Dict, Any
from common.constants import BROWSER_PROXY_HOST, BROWSER_PROXY_PORT

try:
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import http
except ImportError as e:
    raise ImportError(
        "mitmproxy is required. Install with: pip install mitmproxy"
    ) from e

from logger import get_agent_loggers
from src.agent.http_history import HTTPHandler
from httplib import (
    HTTPRequest,
    HTTPResponse,
    HTTPRequestData,
    HTTPResponseData,
    post_data_to_dict,
)

agent_log, _ = get_agent_loggers()


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
        self._thread: Optional[threading.Thread] = None
        self._browser_task: Optional[asyncio.Task] = None
        self._connected = False

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

        options = Options(
            listen_host=self._listen_host,
            listen_port=self._listen_port,
            http2=self._http2,
            ssl_insecure=self._ssl_insecure,
        )

        self._master = DumpMaster(options, with_termlog=False, with_dumper=False)
        self._master.addons.add(_RelayAddon(self))

        async def _run_mitm():
            try:
                agent_log.info(
                    "Starting mitmproxy on %s:%d (http2=%s ssl_insecure=%s)",
                    self._listen_host,
                    self._listen_port,
                    self._http2,
                    self._ssl_insecure,
                )
                await self._master.run()
            except Exception:
                agent_log.exception("mitmproxy master crashed")
            finally:
                agent_log.info("mitmproxy master exited")

        self._thread = asyncio.create_task(_run_mitm())
        self._connected = True

    async def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            if self._master:
                self._master.shutdown()
            
            # Stop browser if we started it
            if self._browser_task and not self._browser_task.done():
                self._browser_task.cancel()
                try:
                    await self._browser_task
                except asyncio.CancelledError:
                    agent_log.info("Browser task cancelled")
        finally:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            self._master = None
            self._thread = None
            self._browser_task = None
            self._connected = False
            agent_log.info("Handler '%s' disconnected", self._handler_name)

    async def flush(self):
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
        if not self._loop:
            return
        # Fire-and-forget; log exceptions so they don't get swallowed
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        def _log_err(_fut: "asyncio.Future[Any]") -> None:
            exc = _fut.exception()
            if exc:
                agent_log.exception("Handler coroutine failed: %s", exc)
        fut.add_done_callback(_log_err)

    def _flow_to_http_request(self, flow: http.HTTPFlow) -> HTTPRequest:
        req = flow.request
        url = req.pretty_url
        method = req.method
        headers = dict(req.headers)

        post_dict: Optional[Dict[str, Any]] = None
        if method in {"POST", "PUT", "PATCH", "DELETE"} and req.content:
            ctype = headers.get("content-type", "")
            try:
                if "application/json" in ctype:
                    import json
                    post_dict = json.loads(req.get_text(strict=False) or "")
                else:
                    post_dict = post_data_to_dict(req.get_text(strict=False) or "")
            except Exception:
                post_dict = post_data_to_dict(req.get_text(strict=False) or "")

        data = HTTPRequestData(
            method=method,
            url=url,
            headers={k.lower(): v for k, v in headers.items()},
            post_data=post_dict,
            redirected_from_url=None,
            redirected_to_url=None,
            is_iframe=False,
        )
        return HTTPRequest(data=data)

    def _flow_to_http_response(self, flow: http.HTTPFlow) -> HTTPResponse:
        resp = flow.response
        req = flow.request
        headers = dict(resp.headers) if resp else {}
        body = resp.raw_content if resp and resp.raw_content is not None else None

        # Detect and decode body content based on byte data analysis
        processed_body = body
        body_error = None
        
        if body:
            try:
                # Analyze the raw byte data to determine content type
                if isinstance(body, bytes):
                    # Check for JSON by looking at the first non-whitespace bytes
                    stripped_body = body.lstrip()
                    is_json = stripped_body.startswith((b"{", b"["))
                    
                    # Check for common text patterns
                    is_text = True
                    try:
                        # Try to decode as UTF-8 to see if it's text
                        text_body = body.decode("utf-8", errors="strict")
                    except UnicodeDecodeError:
                        # If strict UTF-8 decoding fails, likely binary
                        is_text = False
                        text_body = body.decode("utf-8", errors="replace")
                    
                    if is_text and is_json:
                        # Parse as JSON if it looks like JSON and is valid text
                        import json
                        try:
                            processed_body = json.loads(text_body)
                        except (json.JSONDecodeError, ValueError):
                            # If JSON parsing fails, keep as text
                            processed_body = text_body
                    elif is_text:
                        # For other text content, use the decoded text
                        processed_body = text_body
                    else:
                        # For binary content, keep as raw bytes
                        processed_body = body
                else:
                    # Non-bytes body, convert to string
                    text_body = str(body)
                    # Check if it looks like JSON
                    if text_body.strip().startswith(("{", "[")):
                        import json
                        try:
                            processed_body = json.loads(text_body)
                        except (json.JSONDecodeError, ValueError):
                            processed_body = text_body
                    else:
                        processed_body = text_body
                    
            except Exception as e:
                body_error = str(e)
                processed_body = body

        print(f"Processed body [{req.url}]: {processed_body}")
        
        data = HTTPResponseData(
            url=req.pretty_url,
            status=resp.status_code if resp else 0,
            headers={k.lower(): v for k, v in headers.items()},
            is_iframe=False,
            body=processed_body,
            body_error=body_error,
        )
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
