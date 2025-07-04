import sys
import traceback
import httpx
from pathlib import Path
from datetime import datetime
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContextConfig,
)
import asyncio
from johnllm import LLMModel
from src.agent.harness import AgentHarness
from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt
from src.agent.client import VulnAppClient

from cnc.tests.challenges.data import (
    JUICESHOP_AUTHNZ_CHALLENGES_FULL, 
    JUICESHOP_AUTHNZ_CHALLENGES_TEST, 
    get_challenges
)

from logging import getLogger
logger = getLogger(__name__)

ALL_VULNS = get_challenges(JUICESHOP_AUTHNZ_CHALLENGES_FULL)
TARGETED_VULNS = get_challenges(JUICESHOP_AUTHNZ_CHALLENGES_TEST)
VULN_APP_URL = "http://localhost:3000"
CNC_URL = "http://localhost:8000"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

# CREATE REVIEW
CREATE_REVIEW_PROMPT = """
<task>
1. Navigate to the homepage
2. Click on a product and write a review
3. Submit the review 
</task>
"""

async def main(user, app_id):
    try:
        # Create the client
        vuln_test_client = VulnAppClient(
            username=user["username"],
            role=user["role"],
            client=httpx.AsyncClient(base_url=CNC_URL),
            vuln_client=httpx.AsyncClient(base_url=VULN_APP_URL),
            targeted_vulns=TARGETED_VULNS,
            all_vulns=ALL_VULNS
        )
        
        logger.info(f"Launching browser for [{user['username']}]")
        logger.info(f"User datadir: {str(DATA_DIR_PATH / user['username'])}")
        
        # Setup browser
        llm = LLMModel()
        window_w, window_h = 1920, 1080
        use_vision = False
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True,
                # user_data_dir=str(DATA_DIR_PATH / user["username"]),
                extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
                # chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
            )
        )
        shared_config = {
            "llm": llm,
            "use_vision": use_vision,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "app_id": app_id,
            "context_cfg": BrowserContextConfig(no_viewport=False),
        }

        AGENT_PROMPT = """
Navigate to the following URL:
{url}

There are 2 parts to this task:
<part1>
1. Dismiss the popup window by clicking on the "Dismiss" button
2. Then login with the following credentials at http://localhost:3000/#/login
{creds}
</part1>

<part2>
1. Once you are logged in, add the first item to your basket
2. Then view your basket 
3. Modify the quantity of an item in your basket
4. Make an observation about the state of your basket
</part2>

Exit after you have successfully completed the above steps. You must complete the parts in order:
part1 -> part2 -> EXIT
""".format(url=VULN_APP_URL, creds=str(user))
        
        agent_config = [
            {
                "task": AGENT_PROMPT,
                "agent_client": vuln_test_client,
            }
        ]
        harness = AgentHarness(
            browser=browser,
            agents_config=agent_config,
            common_kwargs=shared_config,
        )
        
        try:
            # Start agent
            print(f"\nLaunching agent for application ID: {app_id}")
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

    USERS = [
        # {
        #     "username": "bjoern@juice-sh.op",
        #     "email": "bjoern@juice-sh.op",
        #     "role": "admin",
        #     "password": "monkey summer birthday are all bad passwords but work just fine in a long passphrase"
        # },
        {
            "username": "john@juice-sh.op",
            "email": "john@juice-sh.op",
            "role": "customer",
            "password": "y&x5Z#f6W532Z4445#Ae2HkwZVyDb7&oCUaDzFU"
        },
        {
            "username": "jim@juice-sh.op",
            "email": "jim@juice-sh.op",
            "role": "customer",
            "password": "ncc-1701"
        }
    ]
    user = int(sys.argv[1])
    log_prefix = USERS[user]["username"] + "_" + "AGENT"
    
    init_file_logger(log_prefix)
    sys.exit(asyncio.run(main(USERS[user], "3cde654a-8754-4d6c-9f8c-6a491abe3ef6")))
