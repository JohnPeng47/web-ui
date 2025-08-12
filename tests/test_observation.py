import sys
import traceback
from pathlib import Path
import asyncio
import re
import argparse
import json
import requests
import pytest

from logger import init_file_logger

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


PORTSWIGGER_JSON = "../scripts/portswigger/port_swigger_labs.json"
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

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def browser_instance():
    """Provides a Browser instance for tests."""
    llm = LLMModel()
    window_w, window_h = 1920, 1080
    use_vision = False
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
            user_data_dir=str(DATA_DIR_PATH / "browser_test_observation"),
            extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
            chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
        )
    )

    yield browser

    await browser.close()

@pytest.fixture(scope="session")
def shared_agent_config(llm_instance):
    """Shared configuration for AgentHarness."""
    return {
        "llm": llm_instance,
        "use_vision": False,
        "tool_calling_method": "function_calling",
        "system_prompt_class": CustomSystemPrompt,
        "agent_prompt_class": CustomAgentMessagePrompt,
        "controller": ObservationController(LabURLObservation),
        "app_id": None,
        "context_cfg": BrowserContextConfig(no_viewport=False),
    }

@pytest.fixture(scope="session")
def llm_instance():
    """Provides an LLMModel instance."""
    return LLMModel()


async def portswigger_labstart_agent(browser: Browser, shared_config: dict, lab_href: str):
    """Launches portswigger agent to start the lab."""
    
    print("Starting lab: ", PORTSWIGGER_URL + lab_href)

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
""".format(url=PORTSWIGGER_URL + lab_href, creds=str(PORTSWIGGER_CREDS))
    
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
        await harness.start_all(max_steps=15)
        await harness.wait()

        history_str = str(harness.get_history())
        lab_url_match = re.search(r"https://[0-9a-f]{32}\.web-security-academy\.net/", history_str)
        return lab_url_match.group(0) if lab_url_match else None
    finally:
        await harness.kill_all("Test completed")

async def start_lab(browser: Browser, shared_config: dict, vuln_category: str, lab_num: int, labs_data: dict):
    print("Starting lab...", vuln_category, lab_num)

    category_labs = labs_data.get(vuln_category)
    if not category_labs:
        pytest.fail(f"{vuln_category} is not a valid category")
        return
    
    if len(category_labs) <= lab_num:
        pytest.fail(f"{lab_num} is not a valid lab number for category {vuln_category}")
        return
    
    lab_url_match = await portswigger_labstart_agent(browser, shared_config, category_labs[lab_num]["link"])

    print("Lab URL: ", lab_url_match)
    return lab_url_match

async def check_lab_url(lab_url_match: str):
    """Check if the lab URL is accessible."""
    if not lab_url_match:
        pytest.fail("Failed to get lab URL")
        
    try:
        response = requests.get(lab_url_match)
        assert response.status_code == 200, f"Lab URL returned status code {response.status_code}"
    except requests.RequestException as e:
        pytest.fail(f"Error accessing lab URL: {e}")
    
    return True

@pytest.mark.asyncio
async def test_specific_lab_start(browser_instance, shared_agent_config, llm_instance):
    init_file_logger("test_observation_pytest", log_name="navigation")

    try:
        with open(PORTSWIGGER_JSON, "r") as f:
            labs_data = json.load(f)
    except FileNotFoundError:
        pytest.fail(f"Could not find PortSwigger labs JSON: {PORTSWIGGER_JSON}")
        return
    except json.JSONDecodeError:
        pytest.fail(f"Could not decode PortSwigger labs JSON: {PORTSWIGGER_JSON}")
        return

    if not labs_data:
        pytest.skip("No labs data found in JSON.")
        return

    vuln_category = "SQL injection"
    lab_num = 0

    if vuln_category not in labs_data:
        pytest.fail(f"Test setup error: Vulnerability category '{vuln_category}' not found in labs data.")
        return
    if not labs_data[vuln_category] or lab_num >= len(labs_data[vuln_category]):
         pytest.fail(f"Test setup error: Lab number {lab_num} not found for category '{vuln_category}'.")
         return


    print(f"Testing lab: Category='{vuln_category}', Lab Number={lab_num}")
    
    lab_url_match = await start_lab(browser_instance, shared_agent_config, vuln_category, lab_num, labs_data)
    assert lab_url_match is not None, "Failed to obtain lab URL from agent."
    
    await check_lab_url(lab_url_match)
    
    print(f"Successfully started and accessed lab: {lab_url_match}")