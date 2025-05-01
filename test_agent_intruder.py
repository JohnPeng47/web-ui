from typing import List
import sys
import asyncio
import traceback
from datetime import datetime

from src.agent.client import AgentClient
from httplib import parse_burp_xml
import asyncio
import sys
from typing import Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
from pydantic import BaseModel
import json

from johnllm import LLMModel, LMP
from logger import init_root_logger
from src.agent.custom_agent import CustomAgent
from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt
from src.utils import extract_state_from_history, utils
from tests.server import PORT

# Initialize environment
load_dotenv()
sys.path.append(".")

# Create the client - replace with actual server URL in productionc
agent_clients = [
    (
        AgentClient(
            base_url="http://localhost:8001",  # Replace with actual server URL
            username="tenant1",
            role="scanner"
        ), 
        {
            "credentials": {
                "username": "evil_corp-store_admin1",
                "password": "password123"
            }
        }
    ), 
    (
        AgentClient(
            base_url="http://localhost:8001",  # Replace with actual server URL
            username="tenant2",
            role="scanner"
        ),
        {
            "credentials": {
                "username": "good_corp-store_admin1",
                "password": "password123"
            }
        }
    ),
]
main_client = AgentClient(
    base_url="http://localhost:8001",  # Replace with actual server URL
    username="admin",
    role="scanner"
)

async def launch_agent(agent_client_creds, app_id):
    agent_client, creds = agent_client_creds
    AGENT_PROMPT = """
Navigate to the following URL:
http://localhost:8000/products/

Find an existing product and edit its descriptions
If you are faced with a login screen, use these credentials:
{creds}

Exit after you have successfully edited the product and redirected
""".format(creds=str(creds))
    
    retries = 3
    while retries > 0:
        try:
            from browser_use.browser.browser import Browser, BrowserConfig
            from browser_use.browser.context import (
                BrowserContextConfig,
                BrowserContextWindowSize,
            )

            llm = LLMModel()
            window_w, window_h = 1920, 1080
            use_vision = False
            browser = Browser(
                config=BrowserConfig(
                    headless=False,
                    disable_security=True,
                    extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
                    chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
                )
            )
            async with await browser.new_context(
                    config=BrowserContextConfig(
                        no_viewport=False,
                        browser_window_size=BrowserContextWindowSize(
                            width=window_w, height=window_h
                        ),
                    )
            ) as browser_context:
                agent = CustomAgent(
                    task=AGENT_PROMPT,
                    llm=llm,
                    browser_context=browser_context,
                    use_vision=use_vision,
                    tool_calling_method="function_calling",
                    system_prompt_class=CustomSystemPrompt,
                    agent_prompt_class=CustomAgentMessagePrompt,
                    agent_client=agent_client,
                    app_id=app_id
                )
                history = await agent.run(max_steps=15)
                
            await browser.close()
            return history
        except Exception as e:
            retries -= 1
            if retries == 0:
                raise e
            print(f"Attempt failed, retrying... {3-retries}/3")

async def main():
    try:
        # Create a new application
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_name = f"AgentIntruderTest_{timestamp}"
        app_description = f"Automated test application created at {timestamp}"
        
        print(f"Creating application: {app_name}")
        app_info = await main_client.create_application(app_name, app_description)
        app_id = app_info["id"]
        print(f"Application created successfully:")
        print(f"  ID: {app_id}")
        print(f"  Name: {app_info['name']}")
        print(f"  Description: {app_info['description']}")
        print(f"  Created at: {app_info['created_at']}")
        
        # Launch both agents
        for i, agent_client_creds in enumerate(agent_clients[:1]):
            print(f"\nLaunching agent {i+1} for application ID: {app_id}")
            history = await launch_agent(agent_client_creds, app_id)
            print(f"Agent {i+1} completed successfully")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nTraceback (most recent call last):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
