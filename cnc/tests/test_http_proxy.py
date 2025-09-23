import pytest_asyncio
import asyncio
import subprocess
import sys
import contextlib
import time
from pathlib import Path
from urllib.request import urlopen
import pytest
import os

from playwright.async_api import async_playwright

from common.http_handler import HTTPHandler
from src.agent.discovery.proxy import MitmProxyHTTPHandler
from logger import get_agent_loggers


SERVER_HOST = "localhost"
SERVER_PORT = 8005
SERVER_BASE = f"http://{SERVER_HOST}:{SERVER_PORT}"
TARGET_URL = SERVER_BASE

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8081

def _wait_for_server(url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    raise AssertionError(f"Server not reachable at {url}: {last_err}")


def setup_agent_dir(agent_name: str):
    agent_dir = Path(f".{agent_name}")
    agent_dir.mkdir(exist_ok=True)

    log_dir = agent_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    return agent_dir, log_dir


@pytest.fixture(scope="module")
def server_process():
    """Start the local FastAPI test server as a subprocess and stop it after tests."""
    server_path = Path(__file__).resolve().parent / "proxy_intercept_server" / "server.py"
    assert server_path.exists(), f"Missing server.py at {server_path}"
    # Ensure server binds to the same host/port the test expects
    env = {**os.environ, "HOST": SERVER_HOST, "PORT": str(SERVER_PORT)}
    proc = subprocess.Popen([sys.executable, str(server_path)], cwd=str(server_path.parent), env=env)
    try:
        _wait_for_server(f"{SERVER_BASE}/")
        yield proc
    finally:
        with contextlib.suppress(Exception):
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            with contextlib.suppress(Exception):
                proc.kill()


@pytest_asyncio.fixture
async def proxy_handler():
    """Initialize and connect the proxy handler for local server scope."""
    http_handler = HTTPHandler(
        scopes=[
            f"{SERVER_BASE}/",
        ]
    )
    proxy_handler = MitmProxyHTTPHandler(
        handler=http_handler,
        listen_host=PROXY_HOST,
        listen_port=PROXY_PORT,
        ssl_insecure=True,
        http2=True,
    )
    await proxy_handler.connect()
    try:
        yield proxy_handler
    finally:
        await proxy_handler.disconnect()

@pytest_asyncio.fixture
async def browser_context(proxy_handler):
    """Launch a simple Chromium context configured to use the proxy."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, proxy={"server": f"http://{PROXY_HOST}:{PROXY_PORT}"})
    context = await browser.new_context()
    try:
        yield context
    finally:
        await context.close()
        await browser.close()
        await pw.stop()

@pytest.mark.asyncio
async def test_http_proxy_local_server(server_process, proxy_handler, browser_context):
    """Start local server, drive a browser through proxy, capture 304 JSON message."""
    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting local server proxy test")

    # Navigate and trigger XHR
    page = await browser_context.new_page()
    await page.goto(f"{TARGET_URL}")
    # await page.click("#btn")

    # Allow the XHR to complete and be relayed to the handler
    await asyncio.sleep(0.5)
    msgs = await proxy_handler.flush()

    # Find the /api/data message and inspect body or X-JSON header
    target = None
    for m in msgs:
        print(m.request.url)
        print(m.response.get_body())
        if m.request.url.startswith(f"{SERVER_BASE}/api/data"):
            target = m
            break

    assert target is not None, "/api/data request should be captured"
    assert target.response is not None, "Captured message should include a response"

    body = json.dumps(target.response.get_body())
    assert "Hello from 304" in body, "Expected 'Hello from 304' in body or X-JSON header"

    agent_log.info("Local server proxy test completed successfully")
