from itertools import filterfalse
from pathlib import Path
import httpx

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.controller.service import Controller

from src.agent.min_agent_plan import MinimalAgent
from src.llm_models import LLMHub
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT

from eval.client import PagedDiscoveryEvalClient
from eval.discovery import JUICE_SHOP_ALL

from pentest_bot.logger import setup_agent_logger

MODEL_DICT = {
    "browser_use": "gpt-4o",
    "create_plan": "o3",
    "update_plan": "o3",
    "check_plan_completion": "gemini-2.5-flash",
    "determine_new_page": "gemini-2.5-flash",
}
PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)


async def main():
    """Initialize MinimalAgent following the harness flow (browser -> context -> agent)."""

    setup_agent_logger("min_agent_plan", subfolder="min_agent_plan")

    # 1) Create a Browser similar to harness usage
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
            user_data_dir=str(PROFILE_DIR),
            chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
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
            None,
            llm=llm,
            max_steps=10,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_context=context,
            controller=controller,
            start_urls=["http://147.79.78.153:3000/#/"],
            http_capture=True,
            cont_mode=False,
            challenge_client= PagedDiscoveryEvalClient(
                challenges={"/": JUICE_SHOP_ALL["/"]},
                async_client=httpx.AsyncClient()
            )
        )
        await agent.run()

        print("COST: ")
        print(llm.get_costs())

    except Exception as e:
        import traceback
        print(f"Playwright browser/context not available: {e}")
        print("Stacktrace:")
        traceback.print_exc()
    finally:
        # Cleanup resources like the harness
        if context is not None:
            await context.close()
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())