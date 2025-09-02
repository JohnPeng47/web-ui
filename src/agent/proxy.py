import threading
import time
import logging
import asyncio
from typing import Optional, Dict, Any

try:
    # Programmatic mitmproxy API
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    from mitmproxy import http
except ImportError as e:
    raise ImportError(
        "mitmproxy is required for ProxyHandler. Install with: pip install mitmproxy"
    ) from e

from logger import get_agent_loggers
from src.agent.http_history import HTTPHandler
from httplib import (
    HTTPMessage, 
    HTTPRequest, 
    HTTPResponse, 
    HTTPRequestData, 
    HTTPResponseData, 
    post_data_to_dict
)

agent_log, _ = get_agent_loggers()

class ProxyHandler:
    """
    Wraps an HTTPHandler and runs a local MITM HTTP(S) proxy that captures traffic
    and feeds it into the handler as HTTPMessage objects.

    Notes:
    - You must trust mitmproxy's CA on the client making requests to intercept HTTPS.
      Default CA path: ~/.mitmproxy
    - Proxy URL will be http://{listen_host}:{listen_port}
    """

    def __init__(
        self,
        handler: HTTPHandler,
        *,
        listen_host: str = "127.0.0.1",
        listen_port: int = 8081,
        ssl_insecure: bool = True,
        http2: bool = True,
        mode: Optional[str] = None,
    ) -> None:
        """
        Args:
            handler: Your HTTPHandler instance (from the code you shared).
            listen_host: Address to bind the proxy on.
            listen_port: Port to bind the proxy on.
            ssl_insecure: If True, do not verify upstream TLS certs.
            http2: Enable HTTP/2 interception.
            mode: mitmproxy "mode" string if you want upstream mode (e.g., "upstream:http://proxy:port").
        """
        self._handler = handler
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._ssl_insecure = ssl_insecure
        self._http2 = http2
        self._mode = mode

        self._master: Optional[DumpMaster] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._running = False

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────
    def start(self) -> None:
        """
        Start the proxy in a background thread. No-op if already started.
        """
        if self._running:
            agent_log.info("Proxy already running at %s", self.proxy_url)
            return

        opts = Options(
            listen_host=self._listen_host,
            listen_port=self._listen_port,
            http2=self._http2,
            ssl_insecure=self._ssl_insecure,
        )
        if self._mode:
            # Example: "regular" (default), "transparent", or "upstream:http://upstream:3128"
            opts.mode = [self._mode]

        self._master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        self._master.addons.add(_MitmAddon(self))

        self._thread = threading.Thread(target=self._run_master, name="mitmproxy-thread", daemon=True)
        self._thread.start()
        self._running = True
        agent_log.info("Proxy listening on %s", self.proxy_url)

    def stop(self) -> None:
        """
        Stop the proxy and join the background thread.
        """
        if not self._running:
            return
        try:
            if self._master:
                self._master.shutdown()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
        finally:
            self._running = False
            self._master = None
            self._thread = None
            agent_log.info("Proxy stopped")

    @property
    def proxy_url(self) -> str:
        return f"http://{self._listen_host}:{self._listen_port}"

    async def flush(self):
        """
        Delegate to your HTTPHandler.flush(). Use this after browser/app requests
        should have finished to collect the captured step messages.
        """
        return await self._handler.flush()

    def get_history(self):
        """
        Delegate to your HTTPHandler.get_history().
        """
        return self._handler.get_history()

    # ─────────────────────────────────────────────────────────────────────
    # Internal: mitmproxy master lifecycle
    # ─────────────────────────────────────────────────────────────────────
    def _run_master(self) -> None:
        assert self._master is not None
        try:
            # mitmproxy's DumpMaster.run() is async; run it in this thread's event loop
            asyncio.run(self._master.run())
        except Exception as e:
            agent_log.exception("mitmproxy master crashed: %s", e)
        finally:
            self._running = False

    # ─────────────────────────────────────────────────────────────────────
    # Internal: conversions and ingestion
    # ─────────────────────────────────────────────────────────────────────
    async def _ingest_request(self, flow: "http.HTTPFlow") -> None:
        """
        Convert mitmproxy request to your HTTPRequest and push into handler's queue.
        """
        try:
            url = flow.request.url
            
            if getattr(self._handler, "_is_banned")(url):  # uses your handler's method
                agent_log.debug("Proxy dropped banned URL: %s", url)
                return

            req = self._flow_to_http_request(flow)
            await self._handler.handle_request(req)
        except Exception as e:
            agent_log.exception("Proxy request ingestion failed: %s", e)

    async def _ingest_response(self, flow: "http.HTTPFlow") -> None:
        """
        Convert mitmproxy response to your HTTPResponse and finalize an HTTPMessage.
        """
        try:
            if not flow.response:
                return

            req = self._flow_to_http_request(flow)
            resp = self._flow_to_http_response(flow)

            await self._handler.handle_response(resp, req)
        except Exception as e:
            agent_log.exception("Proxy response ingestion failed: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # Internal: mitm→model converters
    # ─────────────────────────────────────────────────────────────────────
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
        # agent_log.info(f"Request: [{request.method}] {request.url}\n{request.data}")
        return request

    def _flow_to_http_response(self, flow: "http.HTTPFlow") -> HTTPResponse:
        """
        Map mitmproxy flow.response to your HTTPResponse.
        """
        if not flow.response:
            headers: Dict[str, str] = {}
            body_bytes: Optional[bytes] = None
            status_code: int = 0
        else:
            headers = {k.lower(): v for k, v in flow.response.headers.items()}
            body_bytes = None
            try:
                body_bytes = flow.response.raw_content if flow.response.raw_content is not None else None
            except Exception:
                body_bytes = None
            status_code = getattr(flow.response, "status_code", 0)

        data = HTTPResponseData(
            url=flow.request.url,
            status=status_code,
            headers=headers,
            is_iframe=False,
            body=body_bytes,
            body_error=None,
        )
        return HTTPResponse(data=data)


class _MitmAddon:
    """
    mitmproxy addon that forwards events into ProxyHandler.
    """

    def __init__(self, proxy_handler: ProxyHandler) -> None:
        self._proxy = proxy_handler

    async def request(self, flow: "http.HTTPFlow") -> None:
        await self._proxy._ingest_request(flow)

    async def response(self, flow: "http.HTTPFlow") -> None:
        await self._proxy._ingest_response(flow)
