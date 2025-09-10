import asyncio
from pathlib import Path
import json

from playwright.async_api import async_playwright
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller

from eval.client import PagedDiscoveryEvalClient
from src.llm_models import LLMHub
from src.agent.discovery.min_agent_single_page import MinimalAgentSinglePage
from src.agent.discovery.prompts.sys_prompt import CUSTOM_SYSTEM_PROMPT
from common.http_handler import HTTPHandler

from eval.datasets.discovery.juiceshop import JUICE_SHOP_ALL as JUICE_SHOP_ALL_DISCOVERY
from eval.datasets.discovery.juiceshop_exploit import JUICE_SHOP_VULNERABILITIES as JUICE_SHOP_VULNERABILITIES_EXPLOIT

from cnc.workers.agent.cdp_handler import CDPHTTPHandler

from logger import setup_agent_logger, get_agent_loggers

MODEL_CONFIG = {
    "browser_use": "gpt-4.1",
    "update_plan": "o3-mini",
    "create_plan": "o3-mini",
    "check_plan_completion": "gpt-4.1",
}
PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)
PORT = 9899
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8081

TEST_PATHS = [
    "/login"
]
START_URLS = ["http://147.79.78.153:3000/#/login"]
JUICE_SHOP_BASE_URL = "http://147.79.78.153:3000"
JUICE_SHOP_ALL = {**JUICE_SHOP_ALL_DISCOVERY, **JUICE_SHOP_VULNERABILITIES_EXPLOIT}
JUICE_SHOP_SUBSET = {p: JUICE_SHOP_ALL.get(p, []) for p in TEST_PATHS if p}

# Single task for SimpleAgent
TASK = """
Visit the login page at http://147.79.78.153:3000/#/login and attempt to log in with test credentials:

email: bjoern.kimminich@gmail.com
password: 'bW9jLmxpYW1nQGhjaW5pbW1pay5ucmVvamI='

Then exit
"""

# 6 urls
TEST_URLS = [
    # "http://147.79.78.153:3000/#/",
    "http://147.79.78.153:3000/#/login",
    # "http://147.79.78.153:3000/#/contact",
    # "http://147.79.78.153:3000/#/about",
    # "http://147.79.78.153:3000/#/photo-wall",
    # "http://147.79.78.153:3000/#/search",
]

def setup_agent_dir(agent_name: str):
    agent_dir = Path(f".{agent_name}")
    agent_dir.mkdir(exist_ok=True)

    log_dir = agent_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    return agent_dir, log_dir

# 1) Start proxy handler (mitmproxy)    
async def main():
    """Initialize MinimalAgent using the new BrowserSession-based API."""
    agent_dir, log_dir = setup_agent_dir("min_agent")
    setup_agent_logger(log_dir=str(log_dir))

    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting agent")

    # 2) Launch external Playwright Chromium with proxy + CDP enabled
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
        args=[f"--remote-debugging-port={PORT}", "--remote-debugging-address=127.0.0.1"],
    )

    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=True,
        ),
        is_local=False,
        cdp_url=f"http://127.0.0.1:{PORT}/",
    )
    await browser_session.start()

    cdp_handler = CDPHTTPHandler(
        handler=HTTPHandler(
            scopes=[
                "http://147.79.78.153:3000/rest/",
                "http://147.79.78.153:3000/api/",
            ]
        ),
        cdp_host=PROXY_HOST,
        cdp_port=PORT,
    )
    await cdp_handler.connect()

    try:
        # LLM and Controller
        client = PagedDiscoveryEvalClient(
            challenges=JUICE_SHOP_SUBSET,
            base_url=JUICE_SHOP_BASE_URL,
        )
        llm = LLMHub(MODEL_CONFIG)
        controller = Controller(exclude_actions=["extract_structured_data"])

        # MinimalAgent now uses browser_session instead of Browser/BrowserContext
        agent = MinimalAgentSinglePage(
            start_urls=TEST_URLS,
            llm=llm,
            max_steps=10,
            max_page_steps=10,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
            cdp_handler=cdp_handler,
            challenge_client=client,
            agent_dir=agent_dir,
        )
        await agent.run()

        complete, complete_str = client.report_progress()
        agent_log.info(f"[Challenge Status]: {complete_str}")

        with open("agent_summary.json", "w") as f:
            f.write(json.dumps(await agent.pages.to_json(), indent=2))

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Browser session failed: {e}")
    finally:
        try:
            await browser_session.stop()
        finally:
            await browser.close()
            await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())