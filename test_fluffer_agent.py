import sys
import traceback
from pathlib import Path
import re

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


PORTSWIGGER_JSON = "scripts/portswigger/port_swigger_labs.json"
PORTSWIGGER_CREDS = {
    "email": "johnpeng47@gmail.com",
    "password": "i;CZTW8x6p4CTWqL!N8}x~J@9iMbTxyZ"
}
PORTSWIGGER_URL = "https://portswigger.net"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

class LabURLObservation(ObservationModel):
    lab_url: str
    
    def to_msg(self):
        return self.lab_url

async def portswigger_labstart_agent(lab_url, instructions):
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
                user_data_dir=str(DATA_DIR_PATH / "browser"),
                extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
                chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
            )
        )
        shared_config = {
            "agent_name": "fluffer",
            "llm": llm,
            "use_vision": use_vision,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "controller": ObservationController(LabURLObservation),
            "app_id": None,
            "context_cfg": BrowserContextConfig(no_viewport=False),
        }

        AGENT_PROMPT = """
Navigate to the following URL:
{url}

Your goal is to identify the location of the vulnerability as described here:
{description}

Once you have found vulnerability *and* triggered the HTTP request associated with it, then *EXIT*
""".format(url=lab_url, description=instructions)
        
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
            lab_url_match = re.search(r"https://[0-9a-f]{32}\.web-security-academy\.net/", history_str)
            return lab_url_match.group(0) if lab_url_match else None
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

if __name__ == "__main__":
    import asyncio

    LAB_URL = "https://0a8b003703dcd08282b7a10d00ac00f8.web-security-academy.net"
    INSTRUCTIONS = """
Lab: File path traversal, traversal sequences stripped non-recursively   This lab contains a path traversal vulnerability in the display of product images. The application strips path traversal sequences from the user-supplied filename before using it. To solve the lab, retrieve the contents of the /etc/passwd file.    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>
"""
    asyncio.run(portswigger_labstart_agent(LAB_URL, INSTRUCTIONS))