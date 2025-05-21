import sys
import traceback
from pathlib import Path
import asyncio
import re
import argparse
import json
import requests

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContextConfig,
)
from src.agent.harness import AgentHarness
from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt
from src.agent.controllers.observation_contoller import ObservationController, ObservationModel

from johnllm import LLMModel
from logging import getLogger
logger = getLogger(__name__)

class ObservePageOwner(ObservationModel):
    page_owner: str
    
    def to_msg(self):
        return self.page_owner

async def start_observation_agent():
    """Launches portswigger agent to start the lab"""
    try:                
        # Setup browser
        llm = LLMModel()
        window_w, window_h = 1920, 1080
        use_vision = False
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True,
                extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
            )
        )
        shared_config = {
            "llm": llm,
            "use_vision": use_vision,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "controller": ObservationController(ObservePageOwner),
            "app_id": None,
            "context_cfg": BrowserContextConfig(no_viewport=False),
        }

        AGENT_PROMPT = """
Navigate to localhost:5000

Use the thet 
Once this is done, exit
"""
        agent_config = [
            {
                "task": AGENT_PROMPT,
                "agent_client": None,
            }
        ]
        harness = AgentHarness(
            browser=browser,
            agents_config=agent_config,
            common_kwargs=shared_config,
        )
        
        try:
            # Start agent
            await harness.start_all(max_steps=15)
            await harness.wait()

            history_str = str(harness.get_history())
        finally:
            # Clean up
            await harness.kill_all("Test completed")
            await browser.close()
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nTraceback (most recent call last):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0

async def main():
    import subprocess
    import time
    # Start the Flask server in a subprocess
    # server_process = subprocess.Popen([sys.executable, "tests/server.py"])
    # # Give the server a moment to start
    # time.sleep(2)   

    await start_observation_agent()

if __name__ == "__main__":
    asyncio.run(main())   