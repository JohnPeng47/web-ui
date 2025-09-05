import logging
import asyncio
import json
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

try:
    import websockets
except ImportError as e:
    raise ImportError(
        "websockets is required for CDPHTTPHandler. Install with: pip install websockets"
    ) from e

from logger import get_agent_loggers
from src.agent.http_history import HTTPHandler
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
        self._listen_task = None
        
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
            # Get the WebSocket debugger URL from CDP
            import aiohttp
            print(f"[CDPHTTPHandler] Fetching CDP targets from http://{self._cdp_host}:{self._cdp_port}/json")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{self._cdp_host}:{self._cdp_port}/json") as resp:
                    targets = await resp.json()
                    if not targets:
                        raise Exception("No CDP targets available")
                    
                    # Use the first page target
                    target = targets[0]
                    ws_url = target['webSocketDebuggerUrl']
                    print(f"[CDPHTTPHandler] Found target: {target.get('title', 'Untitled')} ({target.get('type', 'unknown')})")
                    print(f"[CDPHTTPHandler] Connecting to WebSocket: {ws_url}")
            
            # Connect to CDP WebSocket
            self._websocket = await websockets.connect(ws_url)
            print(f"[CDPHTTPHandler] WebSocket connection established")
            
            # Enable Network domain for passive monitoring
            await self._send_command("Network.enable")
            print(f"[CDPHTTPHandler] Network domain enabled - passive monitoring active")
            
            # Register event handlers
            self._register_event_handlers()
            
            # Start listening for CDP events
            self._listen_task = asyncio.create_task(self._listen_for_events())
            
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
            # Disable Network domain
            if self._websocket:
                await self._send_command("Network.disable")
                print(f"[CDPHTTPHandler] Network domain disabled")
            
            # Cancel event listener
            if self._listen_task:
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            
            # Close WebSocket
            if self._websocket:
                await self._websocket.close()
                print(f"[CDPHTTPHandler] WebSocket connection closed")
            
        except Exception as e:
            agent_log.error("Error during disconnect: %s", e)
            print(f"[CDPHTTPHandler] Warning during disconnect: {e}")
        
        finally:
            self._websocket = None
            self._connected = False
            self._listen_task = None
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
    
    async def _send_command(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a command to CDP and wait for response."""
        if not self._websocket:
            raise Exception("Not connected to CDP")
        
        message = {
            "id": self._message_id,
            "method": method,
            "params": params or {}
        }
        self._message_id += 1
        
        await self._websocket.send(json.dumps(message))
        # For simplicity, we're not waiting for command responses here
        # In production, you'd want to track responses by message ID
        return {}

    async def _listen_for_events(self):
        """Listen for CDP events and route them to handlers."""
        print(f"[CDPHTTPHandler] Event listener started")
        try:
            async for message in self._websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle CDP events (not command responses)
                    if "method" in data:
                        event_name = data["method"]
                        params = data.get("params", {})
                        
                        # Route to appropriate handler
                        if event_name in self._event_handlers:
                            await self._event_handlers[event_name](params)
                            
                except json.JSONDecodeError as e:
                    agent_log.error("Failed to parse CDP message: %s", e)
                except Exception as e:
                    agent_log.error("Error handling CDP event: %s", e)
                    
        except websockets.exceptions.ConnectionClosed:
            agent_log.info("CDP WebSocket connection closed")
            print(f"[CDPHTTPHandler] WebSocket connection closed")
        except asyncio.CancelledError:
            agent_log.info("CDP event listener cancelled")
            print(f"[CDPHTTPHandler] Event listener stopped")
            raise
        except Exception as e:
            agent_log.error("CDP event listener error: %s", e)
            print(f"[CDPHTTPHandler] Event listener error: {e}")

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
    
    async def _handle_request_will_be_sent(self, params: Dict) -> None:
        """Handle Network.requestWillBeSent event."""
        try:
            request = params.get("request", {})
            url = request.get("url", "")
            
            # Check if URL is banned
            if getattr(self._handler, "_is_banned", lambda x: False)(url):
                agent_log.debug("CDP dropped banned URL: %s", url)
                return

            print(f"[CDPHTTPHandler] Request will be sent: {params}")            

            # Convert CDP request to HTTPRequest
            http_request = self._cdp_to_http_request(params)
            
            # Store request for later response matching
            request_id = params.get("requestId")
            if request_id:
                self._pending_responses[request_id] = {"request": http_request}
            
            # Push to handler
            await self._handler.handle_request(http_request)
            
        except Exception as e:
            agent_log.exception("CDP request ingestion failed: %s", e)

    async def _handle_response_received(self, params: Dict) -> None:
        """Handle Network.responseReceived event."""
        try:
            request_id = params.get("requestId")
            if request_id and request_id in self._pending_responses:
                # Store response data for when loading finishes
                self._pending_responses[request_id]["response_params"] = params
                
        except Exception as e:
            agent_log.exception("CDP response received handling failed: %s", e)

    async def _handle_loading_finished(self, params: Dict) -> None:
        """Handle Network.loadingFinished event - response body is now available."""
        try:
            request_id = params.get("requestId")
            if request_id not in self._pending_responses:
                return
            
            pending = self._pending_responses[request_id]
            if "response_params" not in pending:
                return
            
            # Get response body if needed
            try:
                body_result = await self._send_command(
                    "Network.getResponseBody", 
                    {"requestId": request_id}
                )
                body = body_result.get("body", "").encode() if body_result else None
            except:
                body = None
            
            # Convert CDP response to HTTPResponse
            http_response = self._cdp_to_http_response(
                pending["response_params"], 
                body
            )
            
            # Push to handler
            await self._handler.handle_response(
                http_response, 
                pending["request"]
            )
            
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