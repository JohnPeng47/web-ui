import logging
import asyncio
import json
import base64
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

try:
    import websockets
except ImportError as e:
    raise ImportError(
        "websockets is required for CDPHTTPHandler. Install with: pip install websockets"
    ) from e

from logger import get_agent_loggers
from common.http_handler import HTTPHandler
from httplib import (
    HTTPRequest, 
    HTTPResponse, 
    HTTPRequestData, 
    HTTPResponseData, 
    post_data_to_dict
)

agent_log, _ = get_agent_loggers()


class CDPHTTPHandler:
    """
    Connects an HTTPHandler to Chrome DevTools Protocol (CDP) to capture HTTP(S) traffic
    and feed it into the handler as HTTPMessage objects.
    
    This implementation uses passive monitoring via the Network domain, which observes
    all network traffic without the ability to modify requests/responses.
    
    Notes:
    - Chrome/Chromium must be started with --remote-debugging-port flag
    - No certificate setup required - CDP handles HTTPS naturally
    - Passive monitoring means we observe but cannot block/modify requests
    """
    
    def __init__(
        self,
        handler: HTTPHandler,
        *,
        cdp_host: str = "127.0.0.1",
        cdp_port: int = 9899,
        handler_name: Optional[str] = None,
    ) -> None:
        """
        Args:
            handler: Your HTTPHandler instance.
            cdp_host: Host where Chrome DevTools Protocol is listening.
            cdp_port: Port where Chrome DevTools Protocol is listening.
            handler_name: Unique name for this handler. Auto-generated if None.
        """
        self._cdp_host = cdp_host
        self._cdp_port = cdp_port
        self._handler = handler
        self._handler_name = handler_name or f"cdp_handler_{id(self)}"
        
        self._websocket = None
        self._connected = False
        self._message_id = 1
        self._pending_responses: Dict[str, Dict[str, Any]] = {}  # requestId -> response data
        self._event_handlers: Dict[str, Callable] = {}
        self._stop_event = asyncio.Event()
        self._work_q: asyncio.Queue = asyncio.Queue()
        self._worker_task = None
        self._cmd_futures: Dict[int, asyncio.Future] = {}
        # Multi-target sockets and state
        self._sockets: Dict[str, Any] = {}
        self._listener_tasks: Dict[str, asyncio.Task] = {}
        self._cmd_futures_by_socket: Dict[str, Dict[int, asyncio.Future]] = {}
        
        print(f"[CDPHTTPHandler] Initialized handler '{self._handler_name}'")
        print(f"[CDPHTTPHandler] CDP endpoint: ws://{cdp_host}:{cdp_port}")

    async def connect(self) -> None:
        """
        Connect to Chrome DevTools Protocol and start monitoring network traffic.
        """
        if self._connected: 
            agent_log.info("Handler '%s' already connected to CDP", self._handler_name)
            return
        
        try:
            # Reset stop signal on each connect
            self._stop_event = asyncio.Event()
            # Discover targets and connect to all with a debugger URL
            import aiohttp
            print(f"[CDPHTTPHandler] Discovering CDP targets at http://{self._cdp_host}:{self._cdp_port}")

            targets: list = []
            async with aiohttp.ClientSession() as session:
                for path in ("/json/list", "/json"):
                    try:
                        async with session.get(f"http://{self._cdp_host}:{self._cdp_port}{path}") as resp:
                            if resp.status != 200:
                                continue
                            items = await resp.json()
                            if isinstance(items, dict):
                                items = items.get("targets") or []
                            if items:
                                targets = items
                                break
                    except Exception:
                        continue

            if not targets:
                raise Exception("No CDP targets available")

            # Register event handlers
            self._register_event_handlers()

            # Connect to all targets
            connected = 0
            for t in targets:
                ws_url = t.get("webSocketDebuggerUrl")
                if not ws_url:
                    continue
                target_key = t.get("id") or ws_url
                try:
                    ws = await websockets.connect(ws_url, max_size=None)
                    self._sockets[target_key] = ws
                    self._cmd_futures_by_socket[target_key] = {}
                    # Start per-socket listener
                    self._listener_tasks[target_key] = asyncio.create_task(self._listen_on_socket(target_key))
                    # Enable Network for this target
                    await self._send_command_on(target_key, "Network.enable")
                    print(f"[CDPHTTPHandler] Connected target {t.get('type')} {t.get('title')} ({target_key})")
                    connected += 1
                except Exception as se:
                    agent_log.error("Failed to connect to target %s: %s", target_key, se)

            if connected == 0:
                raise Exception("Failed to connect to any CDP targets")

            # Start worker to process handler work without blocking listeners
            self._worker_task = asyncio.create_task(self._drain_work_q())

            self._connected = True
            agent_log.info("Handler '%s' connected to CDP at ws://%s:%s", 
                          self._handler_name, self._cdp_host, self._cdp_port)
            print(f"[CDPHTTPHandler] Successfully connected and monitoring network traffic")
            
        except Exception as e:
            agent_log.error("Failed to connect to CDP: %s", e)
            print(f"[CDPHTTPHandler] ERROR: Failed to connect to CDP: {e}")
            print(f"[CDPHTTPHandler] Make sure Chrome is running with --remote-debugging-port={self._cdp_port}")
            raise

    async def disconnect(self) -> None:
        """
        Disconnect from CDP and stop monitoring.
        """
        if not self._connected:
            return
        
        print(f"[CDPHTTPHandler] Disconnecting from CDP...")
        
        try:
            # Signal listener to stop
            self._stop_event.set()
            
            # Try to disable Network domain and close all websockets
            for ws_key, ws in list(self._sockets.items()):
                try:
                    await self._send_command_on(ws_key, "Network.disable")
                except Exception:
                    pass
                try:
                    await ws.close()
                except Exception:
                    pass

            # Cancel all listener tasks
            for _, task in list(self._listener_tasks.items()):
                if not task.done():
                    task.cancel()
            
            # Drain any remaining work before shutting down worker
            try:
                await asyncio.wait_for(self._work_q.join(), timeout=5)
            except asyncio.TimeoutError:
                pass

            # Await worker task to finish, cancel as fallback
            if self._worker_task:
                try:
                    await asyncio.wait_for(self._worker_task, timeout=2)
                except asyncio.TimeoutError:
                    self._worker_task.cancel()
                    try:
                        await self._worker_task
                    except asyncio.CancelledError:
                        pass
            
            # Listener tasks are per-socket; already cancelled above
            
        except Exception as e:
            agent_log.error("Error during disconnect: %s", e)
            print(f"[CDPHTTPHandler] Warning during disconnect: {e}")
        
        finally:
            self._sockets.clear()
            self._listener_tasks.clear()
            self._cmd_futures_by_socket.clear()
            self._connected = False
            self._worker_task = None
            agent_log.info("Handler '%s' disconnected from CDP", self._handler_name)
            print(f"[CDPHTTPHandler] Disconnected")

    @property
    def cdp_url(self) -> str:
        return f"ws://{self._cdp_host}:{self._cdp_port}"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def flush(self):
        """
        Delegate to your HTTPHandler.flush(). Use this after browser requests
        should have finished to collect the captured step messages.
        """
        return await self._handler.flush()

    def get_history(self):
        """
        Delegate to your HTTPHandler.get_history().
        """
        return self._handler.get_history()

    # ─────────────────────────────────────────────────────────────────────
    # CDP Communication
    # ─────────────────────────────────────────────────────────────────────
    
    async def _send_command_on(self, ws_key: str, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a command on a specific socket and wait for correlated response."""
        ws = self._sockets.get(ws_key)
        if not ws:
            raise Exception("Socket not connected")
        message_id = self._message_id
        self._message_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        futures = self._cmd_futures_by_socket.setdefault(ws_key, {})
        futures[message_id] = future
        message = {"id": message_id, "method": method, "params": params or {}}
        await ws.send(json.dumps(message))
        data = await future
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def _listen_on_socket(self, ws_key: str) -> None:
        """Listen for CDP events on a specific target socket."""
        ws = self._sockets.get(ws_key)
        if not ws:
            return
        try:
            async for message in ws:
                if self._stop_event.is_set():
                    break
                try:
                    data = json.loads(message)
                except Exception:
                    continue
                # Command responses for this socket
                if "id" in data:
                    futures = self._cmd_futures_by_socket.get(ws_key, {})
                    fut = futures.pop(data["id"], None)
                    if fut and not fut.done():
                        fut.set_result(data)
                    continue
                # Events
                if "method" in data:
                    event_name = data["method"]
                    params = data.get("params", {})
                    handler = self._event_handlers.get(event_name)
                    if handler:
                        await handler(params, ws_key)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            agent_log.error("CDP socket %s listener error: %s", ws_key, e)

    def _register_event_handlers(self):
        """Register handlers for CDP Network events."""
        self._event_handlers = {
            "Network.requestWillBeSent": self._handle_request_will_be_sent,
            "Network.responseReceived": self._handle_response_received,
            "Network.loadingFinished": self._handle_loading_finished,
            "Network.loadingFailed": self._handle_loading_failed,
        }
        print(f"[CDPHTTPHandler] Registered handlers for {len(self._event_handlers)} CDP events")

    # ─────────────────────────────────────────────────────────────────────
    # CDP Event Handlers (passive monitoring)
    # ─────────────────────────────────────────────────────────────────────
    
    async def _handle_request_will_be_sent(self, params: Dict, ws_key: str) -> None:
        """Handle Network.requestWillBeSent event."""
        try:
            request = params.get("request", {})
            url = request.get("url", "")
            method = request.get("method", "")
            
            # Check if URL is banned
            if getattr(self._handler, "_is_banned", lambda x: False)(url):
                print("CDP dropped banned URL: %s", url)
                return

            print(f"[CDPHTTPHandler] Request will be sent: {url} {method}")            

            # Convert CDP request to HTTPRequest
            http_request = self._cdp_to_http_request(params)
            
            # Store request for later response matching
            request_id = params.get("requestId")
            if request_id:
                self._pending_responses[request_id] = {"request": http_request, "ws_key": ws_key}
            
            # Push to handler (decoupled via work queue)
            await self._work_q.put((self._handler.handle_request, (http_request,)))
            
        except Exception as e:
            agent_log.exception("CDP request ingestion failed: %s", e)

    async def _handle_response_received(self, params: Dict, ws_key: str) -> None:
        """Handle Network.responseReceived event."""
        try:
            request_id = params.get("requestId")
            if request_id and request_id in self._pending_responses:
                # Store response data for when loading finishes
                self._pending_responses[request_id]["response_params"] = params
                
        except Exception as e:
            agent_log.exception("CDP response received handling failed: %s", e)

    async def _handle_loading_finished(self, params: Dict, ws_key: str) -> None:
        """Handle Network.loadingFinished event - response body is now available."""
        try:
            request_id = params.get("requestId")
            if request_id not in self._pending_responses:
                return
            
            pending = self._pending_responses[request_id]
            
            # Get response body if needed
            try:
                ws_sel = pending.get("ws_key") or ws_key
                body_result = await self._send_command_on(
                    ws_sel,
                    "Network.getResponseBody",
                    {"requestId": request_id}
                )
                body = None
                if body_result:
                    raw_body = body_result.get("body", "")
                    if body_result.get("base64Encoded"):
                        try:
                            body = base64.b64decode(raw_body)
                        except Exception:
                            body = None
                    else:
                        body = raw_body.encode()
            except:
                body = None
            
            # Convert CDP response to HTTPResponse
            response_params = pending.get("response_params", {})
            if not response_params:
                # Be defensive: synthesize minimal response if missing
                request_obj = pending.get("request")
                fallback_url = getattr(getattr(request_obj, "data", None), "url", "") if request_obj else ""
                response_params = {"response": {"url": fallback_url, "status": 0, "headers": {}}}
            http_response = self._cdp_to_http_response(response_params, body)
            
            # Push to handler
            await self._work_q.put((self._handler.handle_response, (http_response, pending["request"])) )
            
            # Cleanup
            del self._pending_responses[request_id]
            
        except Exception as e:
            agent_log.exception("CDP loading finished handling failed: %s", e)

    async def _handle_loading_failed(self, params: Dict) -> None:
        """Handle Network.loadingFailed event."""
        try:
            request_id = params.get("requestId")
            if request_id in self._pending_responses:
                # Could create an error response here if needed
                del self._pending_responses[request_id]
                
        except Exception as e:
            agent_log.exception("CDP loading failed handling failed: %s", e)

    async def _drain_work_q(self) -> None:
        """Background worker that drains handler work without blocking CDP listener."""
        print(f"[CDPHTTPHandler] Worker started")
        try:
            while True:
                if self._stop_event.is_set() and self._work_q.empty():
                    break
                try:
                    fn, args = await asyncio.wait_for(self._work_q.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                try:
                    await fn(*args)
                except Exception:
                    agent_log.exception("Worker task failed")
                finally:
                    self._work_q.task_done()
        finally:
            print(f"[CDPHTTPHandler] Worker exited")

    # ─────────────────────────────────────────────────────────────────────
    # CDP → Model converters
    # ─────────────────────────────────────────────────────────────────────
    
    def _cdp_to_http_request(self, params: Dict) -> HTTPRequest:
        """Convert CDP request data to HTTPRequest."""
        request = params.get("request", {})
        
        url = request.get("url", "")
        method = request.get("method", "GET")
        headers = {k.lower(): v for k, v in request.get("headers", {}).items()}
        
        # Parse POST data
        post_dict: Optional[Dict[str, Any]] = None
        post_data = request.get("postData")
        if post_data:
            ctype = headers.get("content-type", "")
            if "application/json" in ctype:
                try:
                    post_dict = json.loads(post_data)
                except:
                    post_dict = post_data_to_dict(post_data)
            else:
                post_dict = post_data_to_dict(post_data)
        
        # Check for redirects
        redirect_response = params.get("redirectResponse")
        redirected_from = redirect_response.get("url") if redirect_response else None
        
        data = HTTPRequestData(
            method=method,
            url=url,
            headers=headers,
            post_data=post_dict,
            redirected_from_url=redirected_from,
            redirected_to_url=None,
            is_iframe=params.get("frameId") != params.get("loaderId", params.get("frameId")),
        )
        
        return HTTPRequest(data=data)

    def _cdp_to_http_response(self, params: Dict, body: Optional[bytes] = None) -> HTTPResponse:
        """Convert CDP response data to HTTPResponse."""
        response = params.get("response", {})
        
        url = response.get("url", "")
        status = response.get("status", 0)
        headers = {k.lower(): v for k, v in response.get("headers", {}).items()}
        
        data = HTTPResponseData(
            url=url,
            status=status,
            headers=headers,
            is_iframe=params.get("frameId") != params.get("loaderId", params.get("frameId")),
            body=body,
            body_error=None,
        )
        
        return HTTPResponse(data=data)


# Context manager for automatic connection/disconnection
class CDPConnection:
    """
    Context manager for automatically connecting/disconnecting a CDPHTTPHandler.
    """
    
    def __init__(self, handler: CDPHTTPHandler):
        self.handler = handler
    
    async def __aenter__(self):
        await self.handler.connect()
        return self.handler
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.handler.disconnect()