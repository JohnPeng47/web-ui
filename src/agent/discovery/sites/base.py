from pathlib import Path
from typing import List, Dict
import json

from playwright.async_api import async_playwright
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller

from src.llm_models import LLMHub
from src.agent.discovery.agent import DiscoveryAgent
from src.agent.discovery.prompts.sys_prompt import CUSTOM_SYSTEM_PROMPT
from src.agent.discovery.proxy import MitmProxyHTTPHandler

from common.http_handler import HTTPHandler
from common.constants import (
    DISCOVERY_MODEL_CONFIG,
    BROWSER_PROFILE_DIR_2,
    BROWSER_CDP_HOST,
    BROWSER_CDP_PORT,
    BROWSER_PROXY_HOST,
    BROWSER_PROXY_PORT
)

from eval.client import PagedDiscoveryEvalClient

from logger import get_or_init_log_factory

PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)
PORT = 9898
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8083

async def start_discovery_agent(
    start_urls: List[str], 
    scopes: List[str], 
    challenge_client: PagedDiscoveryEvalClient | None = None,
    init_task: str | None = None,
    auth_cookies: List[Dict[str, str]] | None = None,
):
    """Initialize SimpleAgent using the new BrowserSession-based API."""
    server_log_factory = get_or_init_log_factory(base_dir=".min_agent")
    agent_log, full_log = server_log_factory.get_discovery_agent_loggers()
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE_DIR_2),
        headless=False,
        executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
        args=[f"--remote-debugging-port={BROWSER_CDP_PORT}", f"--remote-debugging-address={BROWSER_CDP_HOST}"],
        proxy={"server": f"http://{BROWSER_PROXY_HOST}:{BROWSER_PROXY_PORT}"},
    )
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=True,
        ),
        is_local=False,
        cdp_url=f"http://{BROWSER_CDP_HOST}:{BROWSER_CDP_PORT}/",
    )
    await browser_session.start()

    # Start proxy handler (mitmproxy)
    http_handler = HTTPHandler(
        scopes=scopes
    )
    proxy_handler = MitmProxyHTTPHandler(
        handler=http_handler,
        listen_host=BROWSER_PROXY_HOST,
        listen_port=BROWSER_PROXY_PORT,
        ssl_insecure=True,
        http2=True,
    )
    await proxy_handler.connect()

    # Launch external Playwright Chromium with proxy + CDP enabled    
    # Navigate to the test URL
    # page = await browser.new_page()
    # await page.goto(TEST_URL)

    try:
        # LLM and Controller
        llm = LLMHub(DISCOVERY_MODEL_CONFIG["model_config"])
        controller = Controller(exclude_actions=["extract_structured_data"])

        # SimpleAgent for single-shot execution
        agent = DiscoveryAgent(
            start_urls=start_urls,
            llm=llm,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
            max_steps=10,
            max_page_steps=2,
            challenge_client=challenge_client,
            proxy_handler=proxy_handler,
            agent_log=agent_log,
            full_log=full_log,
            init_task=init_task,
            auth_cookies=auth_cookies,
        )
        await agent.run()

        with open("good_summary.json", "w") as f:
            f.write(json.dumps(await agent.pages.to_json(), indent=2))

        agent_log.info("SimpleAgent execution completed")

    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        try:
            await browser_session.stop()
        finally:
            await browser.close()
            await pw.stop()
            # proxy_handler.stop()
