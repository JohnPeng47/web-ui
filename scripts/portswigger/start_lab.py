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


PORTSWIGGER_JSON = "scripts/portswigger/port_swigger_labs.json"
PORTSWIGGER_CREDS = {
    "email": "johnpeng47@gmail.com",
    "password": "i;CZTW8x6p4CTWqL!N8}x~J@9iMbTxyZ"
}
PORTSWIGGER_URL = "https://portswigger.net"
CNC_URL = "http://localhost:8000"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

class LabURLObservation(ObservationModel):
    lab_url: str
    
    def to_msg(self):
        return self.lab_url

async def portswigger_labstart_agent(lab_url):
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
            "llm": llm,
            "use_vision": use_vision,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "controller": ObservationController(LabURLObservation),
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
<important>
After being redirected, use the record_observation tool to record the post-redirect lab URL
</important>
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

async def start_lab(vuln_category, lab_num, labs):
    labs = labs.get(vuln_category)
    if not labs:
        print(f"{vuln_category} is not a valid category")
        return
    
    if len(labs) < lab_num:
        print(f"{lab_num} is not a valid lab number")
        return
    
    lab_url_match = await portswigger_labstart_agent(labs[lab_num])
    return lab_url_match

def check_lab_url(lab_url_match):
    """Check if the lab URL is accessible"""
    if not lab_url_match:
        print("Failed to get lab URL", file=sys.stderr)
        sys.exit(1)
        
    try:
        response = requests.get(lab_url_match)
        if response.status_code != 200:
            print(f"Lab URL returned status code {response.status_code}", file=sys.stderr)
            sys.exit(1)
    except requests.RequestException as e:
        print(f"Error accessing lab URL: {e}", file=sys.stderr)
        sys.exit(1)
    
    return True

if __name__ == "__main__":
    from logger import init_file_logger
    
    parser = argparse.ArgumentParser(description="Start PortSwigger lab")
    parser.add_argument("vuln_category", nargs="?", help="Vulnerability category")
    parser.add_argument("lab_num", type=int, nargs="?", help="Lab number (0-indexed)")
    args = parser.parse_args()

    with open(PORTSWIGGER_JSON, "r") as f:
        labs = json.load(f)

    if not args.vuln_category:
        print("Available vulnerability categories:")
        for category in labs.keys():
            print(f"- {category}")
        sys.exit(0)

    if args.vuln_category not in labs:
        print(f"Error: {args.vuln_category} is not a valid category", file=sys.stderr)
        sys.exit(1)

    if args.lab_num is None:
        print(f"Labs in category '{args.vuln_category}':")
        for i, lab in enumerate(labs[args.vuln_category]):
            print(f"[{i}] {lab['name']}")
        sys.exit(0)

    init_file_logger("test_agent", log_name="navigation")
    lab_url_match = asyncio.run(start_lab(args.vuln_category, args.lab_num, labs))
    check_lab_url(lab_url_match)   