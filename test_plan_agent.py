import asyncio
from itertools import filterfalse
from pathlib import Path
import httpx

from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller

from src.agent.min_agent_plan import MinimalAgent
from src.llm_models import LLMHub
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT

from eval.client import PagedDiscoveryEvalClient
from eval.discovery import JUICE_SHOP_ALL

from pentest_bot.logger import setup_agent_logger

MODEL_DICT = {
    "browser_use": "gpt-4.1",
    "create_plan": "o3",
    "update_plan": "o3",
    "check_plan_completion": "gemini-2.5-flash",
    "determine_new_page": "gemini-2.5-flash",
}
PROFILE_DIR = Path(
    r"C:\Users\jpeng\AppData\Local\Google\Chrome\User Data\Profile 2"
)

async def main():
    """Initialize MinimalAgent using the new BrowserSession-based API."""

    setup_agent_logger("min_agent_plan", subfolder="min_agent_plan")

    browser_session = BrowserSession(
        browser_profile=BrowserProfile(
            keep_alive=False,
            disable_security=True,
            user_data_dir=str(PROFILE_DIR),
            chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
        )
    )
    await browser_session.start()

    try:
        llm = LLMHub(MODEL_DICT)
        # TODO: test fileupload later
        controller = Controller(
            exclude_actions=[
                "extract_structured_data", 
                "write_file", 
                "read_file", 
                "upload_file_to_element"
            ],
        )

        # MinimalAgent now uses browser_session instead of browser_context
        agent = MinimalAgent(
            None,
            llm=llm,
            max_steps=10,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=browser_session,
            controller=controller,
            start_urls=["http://147.79.78.153:3000/#/"],
            http_capture=True,
            cont_mode=False,
            challenge_client=PagedDiscoveryEvalClient(
                challenges={"/": JUICE_SHOP_ALL["/"]},
                async_client=httpx.AsyncClient()
            )
        )
        await agent.run()
    except Exception as e:
        import traceback
        print(f"Browser session failed: {e}")
        print("Stacktrace:")
        traceback.print_exc()
    finally:
        await browser_session.kill()

if __name__ == "__main__":
    asyncio.run(main())