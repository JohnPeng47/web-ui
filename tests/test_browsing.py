import pdb

from dotenv import load_dotenv

load_dotenv()
import sys

sys.path.append(".")
import asyncio
import os
import sys
from pprint import pprint
import subprocess
import time
import pytest

from browser_use import Agent
from browser_use.agent.views import AgentHistoryList

from logger import init_root_logger
from src.utils import utils

@pytest.mark.asyncio
async def test_browser_login():
    # Start the Flask server in a subprocess
    server_process = subprocess.Popen(["python", "tests/server.py"])
    # Give the server a moment to start
    time.sleep(2)   

    try:
        from browser_use.browser.browser import Browser, BrowserConfig
        from browser_use.browser.context import (
            BrowserContextConfig,
            BrowserContextWindowSize,
        )

        llm = utils.get_llm_model(
            provider="openai",
            model_name="gpt-4o",
            temperature=0.8,
            base_url=os.getenv("OPENAI_ENDPOINT", ""),
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )
        # llm = utils.get_llm_model(
        #     provider="ollama", model_name="deepseek-r1:14b", temperature=0.5
        # )

        window_w, window_h = 1920, 1080
        use_vision = False

        browser = Browser(
            config=BrowserConfig(
                headless=True,
                disable_security=True,
                extra_chromium_args=[f"--window-size={window_w},{window_h}"],
            )
        )
        async with await browser.new_context(
                config=BrowserContextConfig(
                    trace_path="./tmp/traces",
                    save_recording_path="./tmp/record_videos",
                    no_viewport=False,
                    browser_window_size=BrowserContextWindowSize(
                        width=window_w, height=window_h
                    ),
                )
        ) as browser_context:
            agent = Agent(
                task="Go to http://localhost:5000/login, login with username 'admin' and password 'admin', then read and return the text displayed on the page after login",
                llm=llm,
                browser_context=browser_context,
                use_vision=use_vision,
                tool_calling_method="function_calling"
            )
            history = await agent.run(max_steps=10)

            print("Final Result:")
            pprint(history.final_result(), indent=4)

            # Verify that "Hello World" is in the history
            success = any("Hello World" in str(action) for action in history.model_actions())
            print(f"\nTest {'passed' if success else 'failed'}: Found 'Hello World' in history")

            print("\nErrors:")
            pprint(history.errors(), indent=4)

            print("\nModel Outputs:")
            pprint(history.model_actions(), indent=4)

            print("\nThoughts:")
            pprint(history.model_thoughts(), indent=4)
        
        await browser.close()
    finally:
        # Terminate the Flask server
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    # asyncio.run(test_browser_use_org())
    # asyncio.run(test_browser_use_parallel())
    # asyncio.run(test_browser_use_custom())
    
    init_root_logger()
    asyncio.run(test_browser_login())