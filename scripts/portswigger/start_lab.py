import sys
import traceback
import httpx
from pathlib import Path
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContextConfig,
)
import asyncio
from johnllm import LLMModel, LMP
from src.agent.harness import AgentHarness
from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt
from src.agent.client import AgentClient

from logging import getLogger
logger = getLogger(__name__)


PORTSWIGGER_CREDS = {
    "email": "johnpeng47@gmail.com",
    "password": "i;CZTW8x6p4CTWqL!N8}x~J@9iMbTxyZ"
}
PORTSWIGGER_URL = "https://portswigger.net"
CNC_URL = "http://localhost:8000"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

async def start_lab(lab_url):
    try:
        # Create the client
        vuln_test_client = AgentClient(
            client=httpx.AsyncClient(base_url=CNC_URL),
        )
                
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
            "llm": llm,
            "use_vision": use_vision,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "app_id": None,
            "context_cfg": BrowserContextConfig(no_viewport=False),
        }

        print("Starting lab: ", PORTSWIGGER_URL + lab_url)

        AGENT_PROMPT = """
Navigate to the following URL:
{url}

Click on "Access THE LAB" to start the lab
If redirected to a login page, use the following creds to login;
{creds}

After logging in successfully, confirm that you have been redirected to the lab page
Make a note of the URL in your memory
Once this is done, you can exit 
""".format(url=PORTSWIGGER_URL + lab_url, creds=str(PORTSWIGGER_CREDS))
        
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

            print("Agent completed successfully")
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
    from logger import init_file_logger
    import sys

    init_file_logger("test_agent", log_name="navigation")
    sys.exit(asyncio.run(start_lab("/web-security/llm-attacks/lab-indirect-prompt-injection")))
