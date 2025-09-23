import asyncio
import subprocess
import sys
import contextlib
import time
from pathlib import Path
from urllib.request import urlopen
import os
import json

from playwright.async_api import async_playwright

from common.http_handler import HTTPHandler
from src.agent.discovery.proxy import MitmProxyHTTPHandler
from logger import get_agent_loggers

PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)
SERVER_HOST = "localhost"
SERVER_PORT = 8005
SERVER_BASE = f"http://{SERVER_HOST}:{SERVER_PORT}"
TARGET_URL = "http://147.79.78.153:3000/#/login"

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


def start_server():
    """Start the local FastAPI test server as a subprocess."""
    server_path = Path(__file__).resolve().parent / "proxy_intercept_server" / "server.py"
    assert server_path.exists(), f"Missing server.py at {server_path}"
    # Ensure server binds to the same host/port the test expects
    env = {**os.environ, "HOST": SERVER_HOST, "PORT": str(SERVER_PORT)}
    proc = subprocess.Popen([sys.executable, str(server_path)], cwd=str(server_path.parent), env=env)
    _wait_for_server(f"{SERVER_BASE}/")
    return proc


def stop_server(proc):
    """Stop the server process."""
    with contextlib.suppress(Exception):
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        with contextlib.suppress(Exception):
            proc.kill()


async def create_proxy_handler():
    """Initialize and connect the proxy handler for local server scope."""
    http_handler = HTTPHandler(
        scopes=[
            "http://147.79.78.153:3000/rest/",
            "http://147.79.78.153:3000/api/",
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
    return proxy_handler


async def create_browser_context(proxy_handler):
    """Launch a simple Chromium context configured to use the proxy."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        # user_data_dir=None,
        headless=False,
        executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
        proxy={"server": f"http://{PROXY_HOST}:{PROXY_PORT}"},
    )
    return browser


async def test_http_proxy_local_server():
    """Start local server, drive a browser through proxy, capture 304 JSON message."""
    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting local server proxy test")
    
    try:
        # Create proxy handler
        proxy_handler = await create_proxy_handler()
        
        try:
            # Create browser context
            browser = await create_browser_context(proxy_handler)
            
            try:
                # Navigate and trigger XHR
                page = await browser.new_page()
                await page.goto(f"{TARGET_URL}")
                # await page.click("#btn")

                # Allow the XHR to complete and be relayed to the handler
                await asyncio.sleep(2)
                msgs = await proxy_handler.flush()

                # Find the /api/data message and inspect body or X-JSON header
                target = None
                for m in msgs:
                    print(m.request.url)
                    print(m.response.get_body())

            finally:
                await browser.close()
                
        finally:
            await proxy_handler.disconnect()
            
    finally:
        pass


async def main():
    """Main entry point for the script."""
    await test_http_proxy_local_server()


if __name__ == "__main__":
    asyncio.run(main())
