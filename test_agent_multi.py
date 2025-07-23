import sys
import traceback
import httpx
from datetime import datetime
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContextConfig,
)
import asyncio
from pathlib import Path
from johnllm import LLMModel

from src.agent.harness import AgentHarness
from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt
from src.agent.client import AgentClient, VulnAppClient

from cnc.tests.challenges.data import (
    USERS,
    JUICESHOP_AUTHNZ_CHALLENGES_FULL, 
    JUICESHOP_AUTHNZ_CHALLENGES_TEST, 
    get_challenges
)

ALL_VULNS = get_challenges(JUICESHOP_AUTHNZ_CHALLENGES_FULL)
TARGETED_VULNS = get_challenges(JUICESHOP_AUTHNZ_CHALLENGES_TEST)
VULN_APP_URL = "http://localhost:3000"
CNC_URL = "http://localhost:8000"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

async def main():
    try:
        # Create the client
        main_client = AgentClient(
            client=httpx.AsyncClient(base_url=CNC_URL), 
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_name = f"AgentIntruderTest_{timestamp}"
        app_description = f"Automated test application created at {timestamp}"
        
        print(f"Creating application: {app_name}")
        app_id = await main_client.create_application(app_name, app_description)
        print(f"Application created successfully:")
        print(f"  ID: {app_id}")
        
        # Setup browser
        llm = LLMModel()
        use_vision = False
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

There are 3 parts to this task:
<part1>
1. Check if you are logged in
if logged_in == True:
    logout()

2. Then login with the following credentials    
{creds}
</part1>

<part2>
Complete the following task:
1. Add 3 items to your basket
2. Then view your basket
3. For one item try to increase its count
4. For another item try to decrease its count
5. For the last item try to remove it from the basket
</part2>

<part3>
Log out
</part3>

Here is some extra info:
- the login page is found at http://localhost:3000/#/login
- the logout button is found under accounts

Exit after you have successfully completed the above steps. You must complete the parts in order:
part1 -> part2 -> part3
"""
        # horiztonal testing on customers
        window_w, window_h = 1920, 1080
        agent_config = [
            {
                "task": AGENT_PROMPT.format(url=VULN_APP_URL, creds=str(user)),
                "agent_client": VulnAppClient(
                    username=user["username"],
                    role=user["role"],
                    client=httpx.AsyncClient(base_url=CNC_URL),
                    vuln_client=httpx.AsyncClient(base_url=VULN_APP_URL),
                    targeted_vulns=TARGETED_VULNS,
                    all_vulns=ALL_VULNS
                ),
                "browser": Browser(
                    config=BrowserConfig(
                        headless=False,
                        disable_security=True,
                        user_data_dir=str(DATA_DIR_PATH / user["username"]),
                        extra_chromium_args=[f"--window-size={window_w},{window_h}"],
                        chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
                    )
                )
            # TODO: in factory we just pass in users wihtout having to apply the filter
            } for user in USERS if user["role"] == "customer"
        ]
        harness = AgentHarness(
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
            # await browser_context.close()
            # await browser.close()
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nTraceback (most recent call last):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    from logger import init_root_logger

    init_root_logger()
    sys.exit(asyncio.run(main()))
