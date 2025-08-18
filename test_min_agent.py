import asyncio
from itertools import filterfalse
from pathlib import Path

from playwright.async_api import async_playwright
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller
from browser_use.llm.google.chat import ChatGoogle
from browser_use.llm.openai.chat import ChatOpenAI

from src.llm_models import LLMHub
from src.agent.min_agent import MinimalAgent
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT

from pentest_bot.logger import LOG_DIR,setup_agent_logger, get_agent_loggers

MODEL_DICT = {
    "browser_use": "gemini-2.5-flash",
}
TASK = """
Go to the url: http://147.79.78.153:3000/#/
"""
MODEL_CONFIG = {
    "browser_use": "gpt-4.1",
    "update_plan": "o3-mini",
    "create_plan": "o3-mini",
    "check_plan_completion": "gpt-4.1",
}

PORT = 9899

def setup_agent_dir(agent_name: str):
    agent_dir = Path(f".{agent_name}")
    agent_dir.mkdir(exist_ok=True)
    
    log_dir = agent_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    
    return agent_dir, log_dir
    
async def main():
    """Initialize MinimalAgent using the new BrowserSession-based API."""
    agent_dir, log_dir = setup_agent_dir("min_agent")
    setup_agent_logger(log_dir=log_dir)

    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting agent")

    # TODO: fix this up and then wire up the http_listeners
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=[f"--remote-debugging-port={PORT}"],
    )
    context = await browser.new_context()

    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=True,
        ),
        is_local=False,
        cdp_url=f"http://127.0.0.1:{PORT}/",
    )
    await browser_session.start()
    try:
        # LLM and Controller
        llm = LLMHub(MODEL_CONFIG)
        controller = Controller(exclude_actions=["extract_structured_data"])

        # MinimalAgent now uses browser_session instead of Browser/BrowserContext
        agent = MinimalAgent(
            start_task=None,
            start_urls=["http://147.79.78.153:3000/#/"],
            llm=llm,
            max_steps=5,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
            agent_dir=agent_dir,
        )
        await agent.run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Browser session failed: {e}")
    finally:
        try:
            await browser_session.stop()
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())