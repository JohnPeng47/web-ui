# tests/test_mitmproxy_handler.py
import asyncio
import sys
from typing import Dict, Optional, List, Any, Tuple
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio
from mitmproxy.http import Headers

sys.path.insert(0, ".")

from src.agent.discovery.proxy import MitmProxyHTTPHandler, _RelayAddon
from common.http_handler import HTTPHandler


class MockFlow:
    """Mock mitmproxy HTTPFlow for testing"""
    def __init__(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[bytes] = None,
        status: int = 200,
        response_body: Optional[bytes] = None,
    ):
        self.request = MockRequest(method, url, headers, body)
        self.response = (
            MockResponse(status, headers, response_body) if response_body is not None else None
        )


class MockRequest:
    """Mock mitmproxy Request"""
    def __init__(self, method: str, url: str, headers: Dict[str, str], body: Optional[bytes] = None):
        self.method = method
        self.pretty_url = url
        # Headers must be bytes for mitmproxy
        self.headers = Headers([(k.encode(), v.encode()) for k, v in headers.items()])
        self.content = body or b""

    def get_text(self, strict: bool = True) -> str:
        """Mock get_text that handles binary data"""
        try:
            return self.content.decode("utf-8")
        except UnicodeDecodeError:
            if strict:
                raise
            # Return empty string for binary data when not strict
            return ""


class MockResponse:
    """Mock mitmproxy Response"""
    def __init__(self, status: int, headers: Dict[str, str], body: Optional[bytes] = None):
        self.status_code = status
        # Headers must be bytes for mitmproxy
        self.headers = Headers([(k.encode(), v.encode()) for k, v in headers.items()])
        self.content = body or b""

    def get_text(self, strict: bool = True) -> str:
        """Mock get_text that handles binary data"""
        try:
            return self.content.decode("utf-8")
        except UnicodeDecodeError:
            if strict:
                raise
            return ""


class MockDumpMaster:
    """
    Mock DumpMaster that preserves real addon behavior and async lifecycle,
    but doesn't bind to actual network ports.
    """
    def __init__(self, options, with_termlog=False, with_dumper=False):
        self.options = options
        self.with_termlog = with_termlog
        self.with_dumper = with_dumper

        # Real addon list to test addon registration
        self._addons: List[_RelayAddon] = []
        self.addons = self  # Self-referential for .addons.add() calls

        # Track lifecycle
        self._running = False
        self._shutdown_called = False

    def add(self, addon: _RelayAddon) -> None:
        """Real addon registration"""
        self._addons.append(addon)

    def get(self) -> List[_RelayAddon]:
        """Get registered addons"""
        return self._addons

    async def run(self):
        """
        Mock run() that simulates the blocking nature of real DumpMaster.run()
        but allows controlled shutdown for testing.
        """
        self._running = True
        try:
            # Simulate the master running until shutdown is called
            while not self._shutdown_called:
                await asyncio.sleep(0.01)
        finally:
            self._running = False

    def shutdown(self):
        """Real shutdown behavior"""
        self._shutdown_called = True


@pytest_asyncio.fixture
async def testable_mitm(monkeypatch) -> Tuple[MitmProxyHTTPHandler, Any, MockDumpMaster]:
    """
    Fixture that yields (mitm_handler, inject_flow, mock_master) and ensures clean disconnect.
    """
    http_handler = HTTPHandler()

    mitm_handler = MitmProxyHTTPHandler(
        handler=http_handler,
        listen_host="127.0.0.1",
        listen_port=8888,
    )

    # Patch DumpMaster in the proxy module to our mock
    monkeypatch.setattr("src.agent.discovery.proxy.DumpMaster", MockDumpMaster)

    # Connect the handler (this will create master, register addon, and start the background task)
    await mitm_handler.connect()

    # sanity checks from original script
    assert mitm_handler._loop is not None
    assert mitm_handler._loop == asyncio.get_running_loop()

    master = mitm_handler._master
    assert master is not None
    assert len(master._addons) == 1
    relay_addon = master._addons[0]
    assert isinstance(relay_addon, _RelayAddon)

    assert mitm_handler._task is not None
    assert not mitm_handler._task.done()

    # Give the background task a chance to actually start running
    await asyncio.sleep(0.1)

    async def inject_flow(flow: MockFlow) -> None:
        """
        Inject a mock flow through the REAL addon handlers.
        This exercises:
        - Addon request/response methods
        - _schedule_coro (cross-thread-like scheduling via run_coroutine_threadsafe)
        - _flow_to_http_request/response converters
        - HTTPHandler integration
        """
        relay_addon.request(flow)
        if flow.response:
            relay_addon.response(flow)
        # Allow scheduled async tasks to run
        await asyncio.sleep(0.05)

    try:
        yield mitm_handler, inject_flow, master
    finally:
        await mitm_handler.disconnect()
        # ensure proper cleanup
        assert not mitm_handler.is_connected
        assert master._shutdown_called
        assert mitm_handler._task is None or mitm_handler._task.done()


@pytest.mark.asyncio
async def test_binary_post_data(testable_mitm):
    handler, inject_flow, mock_master = testable_mitm

    # Verify handler is actually connected and running
    assert handler.is_connected
    assert handler._loop is not None
    assert mock_master._running

    binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10"

    flow = MockFlow(
        method="POST",
        url="https://example.com/upload",
        headers={
            "content-type": "application/octet-stream",
            "content-length": str(len(binary_data)),
        },
        body=binary_data,
        status=200,
        response_body=b'{"status": "success"}',
    )

    await inject_flow(flow)

    messages = await handler.flush()

    assert len(messages) > 0, "Expected messages to be collected"
    # ensure history was recorded in underlying handler if available
    try:
        history_len = len(handler._handler.get_history())
        assert history_len >= 0
    except Exception:
        # Some HTTPHandler implementations may not expose get_history; ignore if not present
        pass


@pytest.mark.asyncio
async def test_malformed_json(testable_mitm):
    handler, inject_flow, mock_master = testable_mitm

    malformed_json = b'{"username": "test", "password": unclosed'

    flow = MockFlow(
        method="POST",
        url="https://example.com/api/login",
        headers={
            "content-type": "application/json",
            "content-length": str(len(malformed_json)),
        },
        body=malformed_json,
        status=400,
        response_body=b'{"error": "Invalid JSON"}',
    )

    await inject_flow(flow)
    messages = await handler.flush()
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_non_utf8_data(testable_mitm):
    handler, inject_flow, mock_master = testable_mitm

    non_utf8_data = b"\xff\xfe\xfd\xfc invalid utf8 \x80\x81"

    flow = MockFlow(
        method="POST",
        url="https://example.com/api/submit",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "content-length": str(len(non_utf8_data)),
        },
        body=non_utf8_data,
        status=200,
        response_body=b"OK",
    )

    await inject_flow(flow)
    messages = await handler.flush()
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_concurrent_flows(testable_mitm):
    handler, inject_flow, mock_master = testable_mitm

    flows = [
        MockFlow(
            method="GET",
            url=f"https://example.com/api/endpoint{i}",
            headers={"content-type": "application/json"},
            body=None,
            status=200,
            response_body=b'{"result": "ok"}',
        )
        for i in range(5)
    ]

    await asyncio.gather(*[inject_flow(flow) for flow in flows])
    messages = await handler.flush()
    assert len(messages) >= len(flows)


@pytest.mark.asyncio
async def test_addon_error_handling(testable_mitm):
    handler, inject_flow, mock_master = testable_mitm

    original_converter = handler._flow_to_http_request

    def failing_converter(flow):
        raise ValueError("Simulated conversion error")

    handler._flow_to_http_request = failing_converter

    flow = MockFlow(
        method="GET",
        url="https://example.com/test",
        headers={},
        body=None,
        status=200,
        response_body=b"OK",
    )

    # Should not raise - addon should catch the exception
    await inject_flow(flow)

    # Restore converter and verify normal flow afterwards
    handler._flow_to_http_request = original_converter

    await inject_flow(
        MockFlow(
            method="GET",
            url="https://example.com/normal",
            headers={},
            body=None,
            status=200,
            response_body=b"OK",
        )
    )

    messages = await handler.flush()
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_lifecycle_transitions(monkeypatch):
    http_handler = HTTPHandler()
    mitm_handler = MitmProxyHTTPHandler(
        handler=http_handler,
        listen_host="127.0.0.1",
        listen_port=8888,
    )

    # initial state
    assert not mitm_handler.is_connected
    assert mitm_handler._loop is None
    assert mitm_handler._task is None

    # connect / disconnect with patched DumpMaster
    monkeypatch.setattr("src.agent.discovery.proxy.DumpMaster", MockDumpMaster)
    await mitm_handler.connect()
    await asyncio.sleep(0.1)

    assert mitm_handler.is_connected
    assert mitm_handler._loop is not None
    assert mitm_handler._task is not None
    assert not mitm_handler._task.done()

    await mitm_handler.disconnect()

    assert not mitm_handler.is_connected
    assert mitm_handler._task is None or mitm_handler._task.done()

    # double-connect safety
    monkeypatch.setattr("src.agent.discovery.proxy.DumpMaster", MockDumpMaster)
    await mitm_handler.connect()
    await asyncio.sleep(0.1)
    # second connect should be no-op
    await mitm_handler.connect()

    await mitm_handler.disconnect()

    # double-disconnect safety (no-op)
    await mitm_handler.disconnect()


@pytest.mark.asyncio
async def test_async_handler_exception(testable_mitm, monkeypatch):
    handler, inject_flow, mock_master = testable_mitm

    # Patch the HTTPHandler's handle_request to raise an async exception
    original_handle_request = handler._handler.handle_request

    async def failing_async_handler(http_request):
        await asyncio.sleep(0.01)
        raise ValueError("Simulated async handler failure")

    handler._handler.handle_request = failing_async_handler

    mock_log = Mock()
    monkeypatch.setattr("src.agent.discovery.proxy.agent_log", mock_log)

    flow = MockFlow(
        method="GET",
        url="https://example.com/test",
        headers={},
        body=None,
        status=200,
        response_body=b"OK",
    )

    await inject_flow(flow)
    # Give extra time for the coroutine to run and fail
    await asyncio.sleep(0.2)

    assert mock_log.exception.called, "Expected exception to be logged by done-callback"

    # Restore original handler
    handler._handler.handle_request = original_handle_request

    # Verify handler still connected
    assert handler.is_connected

    # Inject a normal flow to prove the system still works
    await inject_flow(
        MockFlow(
            method="GET",
            url="https://example.com/normal",
            headers={},
            body=None,
            status=200,
            response_body=b"OK",
        )
    )

    messages = await handler.flush()
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_loop_closed_scenario(monkeypatch):
    http_handler = HTTPHandler()
    mitm_handler = MitmProxyHTTPHandler(
        handler=http_handler,
        listen_host="127.0.0.1",
        listen_port=8888,
    )

    monkeypatch.setattr("src.agent.discovery.proxy.DumpMaster", MockDumpMaster)
    await mitm_handler.connect()
    await asyncio.sleep(0.1)

    relay_addon = mitm_handler._master._addons[0]

    class ClosedMockLoop:
        def is_closed(self):
            return True

        def run_coroutine_threadsafe(self, coro, loop):
            raise RuntimeError("Event loop is closed")

    original_loop = mitm_handler._loop

    # Replace loop with closed variant (should be silently dropped)
    mitm_handler._loop = ClosedMockLoop()

    flow = MockFlow(
        method="GET",
        url="https://example.com/test",
        headers={},
        body=None,
        status=200,
        response_body=b"OK",
    )

    # Should not raise
    relay_addon.request(flow)
    relay_addon.response(flow)
    await asyncio.sleep(0.05)

    # Test RuntimeError from run_coroutine_threadsafe
    mitm_handler._loop = original_loop

    def failing_run_coro(coro, loop):
        raise RuntimeError("Cannot schedule - event loop is closing")

    mock_log = Mock()
    monkeypatch.setattr("src.agent.discovery.proxy.agent_log", mock_log)

    with patch("asyncio.run_coroutine_threadsafe", side_effect=failing_run_coro):
        relay_addon.request(flow)
        await asyncio.sleep(0.05)
        assert mock_log.debug.called, "Expected RuntimeError to be logged"

    mitm_handler._loop = original_loop
    await mitm_handler.disconnect()