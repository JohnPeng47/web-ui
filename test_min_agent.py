import asyncio
from itertools import filterfalse

from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller
from browser_use.llm.google.chat import ChatGoogle
from browser_use.llm.openai.chat import ChatOpenAI

from src.llm_models import LLMHub
from src.agent.min_agent import MinimalAgent

from src.agent.prompts import CUSTOM_SYSTEM_PROMPT
from pentest_bot.logger import setup_agent_logger, get_agent_loggers

MODEL_DICT = {
    "browser_use": "gemini-2.5-flash",
}

TASK = """
Go to the url: http://147.79.78.153:3000

If you see home page, great, exit
If you see login page, login with following credentials:
username: bjoern.kimminich@gmail.com
password: bW9jLmxpYW1nQGhjaW5pbW1pay5ucmVvamI=

Once you login, add an item to cart then finish
"""

MODEL_CONFIG = {
    "browser_use": "gpt-4o",
}

async def main():
    """Initialize MinimalAgent using the new BrowserSession-based API."""

    setup_agent_logger("min_agent", subfolder="min_agent")
    agent_log, _ = get_agent_loggers()
    agent_log.info("Starting agent")

    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=False,
        )
    )
    await browser_session.start()

    try:
        # LLM and Controller
        llm = LLMHub(MODEL_CONFIG)
        controller = Controller()

        # MinimalAgent now uses browser_session instead of Browser/BrowserContext
        agent = MinimalAgent(
            start_task=TASK,
            llm=llm,
            max_steps=5,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
        )
        await agent.run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Browser session failed: {e}")
    finally:
        await browser_session.kill()

if __name__ == "__main__":
    asyncio.run(main())