import asyncio
from pathlib import Path
from urllib.parse import urlparse
import json

from playwright.async_api import async_playwright
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller

from src.llm_models import LLMHub
from src.agent.min_agent import MinimalAgent
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT
from src.agent.http_history import HTTPHandler
from src.agent.proxy import ProxyHandler
from eval.client import PagedDiscoveryEvalClient

from eval.datasets.discovery.juiceshop import JUICE_SHOP_ALL as JUICE_SHOP_ALL_DISCOVERY
from eval.datasets.discovery.juiceshop_exploit import JUICE_SHOP_VULNERABILITIES as JUICE_SHOP_VULNERABILITIES_EXPLOIT

from logger import setup_agent_logger, get_agent_loggers

def normalize_urls(urls):
    norm_urls = []
    for url in urls:
        norm_urls.append(urlparse(url).path)
        norm_urls.append(urlparse(url).fragment)
    return norm_urls

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

# Single URL for SimpleAgent
TEST_URL = "http://147.79.78.153:3000/#/login"

def setup_agent_dir(agent_name: str):
    agent_dir = Path(f".{agent_name}")
    agent_dir.mkdir(exist_ok=True)

    log_dir = agent_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    return agent_dir, log_dir

async def main():
    """Initialize SimpleAgent using the new BrowserSession-based API."""
    agent_dir, log_dir = setup_agent_dir("min_agent")
    setup_agent_logger(log_dir=str(log_dir))

    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting SimpleAgent")
    
    # Start proxy handler (mitmproxy)
    http_handler = HTTPHandler(
        scopes=[
            "http://147.79.78.153:3000/rest/",
            "http://147.79.78.153:3000/api/",
        ]
    )
    proxy_handler = ProxyHandler(
        handler=http_handler,
        listen_host=PROXY_HOST,
        listen_port=PROXY_PORT,
        ssl_insecure=True,
        http2=True,
    )
    proxy_handler.start()

    # Launch external Playwright Chromium with proxy + CDP enabled
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        executable_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
        args=[f"--remote-debugging-port={PORT}", "--remote-debugging-address=127.0.0.1"],
        proxy={"server": f"http://{PROXY_HOST}:{PROXY_PORT}"},
    )
    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=True,
        ),
        is_local=False,
        cdp_url=f"http://127.0.0.1:{PORT}/",
    )
    await browser_session.start()
    
    # Navigate to the test URL
    page = await browser.new_page()
    await page.goto(TEST_URL)

    try:
        challenge_client=PagedDiscoveryEvalClient(
            challenges=JUICE_SHOP_SUBSET,
            base_url=JUICE_SHOP_BASE_URL,
        )
        # LLM and Controller
        llm = LLMHub(MODEL_CONFIG)
        controller = Controller(exclude_actions=["extract_structured_data"])

        # SimpleAgent for single-shot execution
        agent = MinimalAgent(
            start_urls=START_URLS,
            llm=llm,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
            agent_dir=agent_dir,
            max_steps=10,
            cdp_handler=proxy_handler,
            challenge_client=challenge_client,
            init_task=TASK,
        )
        await agent.run()
        for challenges in challenge_client.get_solved()["/login"]:
            for challenge in challenges:
                print(challenge)

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
            proxy_handler.stop()

if __name__ == "__main__":
    asyncio.run(main())
