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

Execute this plan:
[   ] [1] HomePage
  [  ] [1.1] Click the “menu” icon (aria-labelled ‘Open Sidenav’) to open the side navigation; click it again to close it, confirming the toggle behaviour.
    [   ] [1.1.1] Within the opened side navigation, click the “Contact” accordion/header once to expand its panel (revealing the “Customer Feedback” link), then click it again to collapse the panel, confirming the toggle behaviour without following the link inside.
  [   ] [1.2] Click the magnifying-glass “search” icon to focus the search bar, type “juice”, press Enter to execute the in-page search, then press Escape to clear/dismiss the results.
  [   ] [1.3] Click the “Account” button (labelled “Account”) to open its drop-down; click once more outside the menu area to collapse it again.
  [   ] [1.4] Click the “language” button (labelled “EN”) to open the language selection menu, press Arrow-Down once and hit Enter to pick the next language, then reopen the menu and re-select “EN” to restore the original setting.
  [   ] [1.5] Click on the product tile labelled “Apple Juice (1000ml)” (or its product image) to open its detail panel.
  [   ] [1.6] Inside the “Apple Juice (1000ml)” detail panel: click the “+” quantity stepper twice, the “–” once, then click the “Add to Basket” button, and finally hit the “×” close button to return to the product list.
  [   ] [1.7] Repeat the previous detail-panel interaction for another item, e.g. “Fruit Press”, to cover a non-drink product.
  [   ] [1.8] Click the basket/cart icon in the top bar (now showing an item count) to open the basket sidebar; change an item’s quantity with its “+”/“–” steppers, click the trash-bin icon to remove it, then click “Continue Shopping” (or close) to hide the sidebar again.
  [   ] [1.9] Open any product detail panel again, click different stars in its rating widget to set several ratings, type a short comment in the “Write a review” field, and press the “Submit” button to exercise the review flow; close the panel afterwards.
  [   ] [1.10] Click on a tile that shows a stock alert such as “Only 1 left” or “Sold Out” to confirm these labels are non-interactive (no action should fire).
  [   ] [1.11] Scroll the page all the way to the bottom and back to the top to trigger any lazy-loaded images, infinite-scroll logic, or scroll-based event handlers.
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
            max_steps=10,
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