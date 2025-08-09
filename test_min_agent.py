from itertools import filterfalse
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.controller.service import Controller

from src.agent.min_agent import MinimalAgent
from src.llm_models import LLMHub
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT

from pentest_bot.logger import setup_agent_logger


MODEL_DICT = {
    "browser_use": "gemini-2.5-flash",
}
TASK = """
Go to the url: http://147.79.78.153:8080/

If you see home page, great, exit
If you see login page, login with following credentials:
username: user1
password: 1234

Once you login, click on the dataset page
"""

async def main():
    """Initialize MinimalAgent following the harness flow (browser -> context -> agent)."""

    setup_agent_logger("min_agent", subfolder="min_agent")

    # 1) Create a Browser similar to harness usage
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
        )
    )

    # 2) Create an isolated BrowserContext (harness creates one per agent)
    context = None
    try:
        context = await browser.new_context(config=BrowserContextConfig(no_viewport=False))

        # 3) Build LLMHub and Controller (kept minimal; we are not invoking the LLM here)
        llm = LLMHub(MODEL_DICT)
        controller = Controller()

        # 4) Initialize the MinimalAgent with the created context and controller
        agent = MinimalAgent(
            start_task=TASK,
            llm=llm,
            max_steps=5,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_context=context,
            controller=controller,
        )
        await agent.run()

    except Exception as e:
        print(f"Playwright browser/context not available: {e}")
    finally:
        # Cleanup resources like the harness
        if context is not None:
            await context.close()
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())