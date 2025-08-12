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
from src.models import UserCredentials
from tests.server import PORT

# Initialize environment
load_dotenv()
sys.path.append(".")

# AGENT_PROMPT = """
# Navigate to the url {initial_url}. If you are faced with a login 

# """


# async def execute_browser_task(initial_url: str, 
#                                task_prompt: str, 
#                                credentials: List[UserCredentials]):

    
#     retries = 3
#     while retries > 0:
#         try:
#             from browser_use.browser.browser import Browser, BrowserConfig
#             from browser_use.browser.context import (
#                 BrowserContextConfig,
#                 BrowserContextWindowSize,
#             )

#             llm = LLMModel()
#             window_w, window_h = 1920, 1080
#             use_vision = False
#             browser = Browser(
#                 config=BrowserConfig(
#                     headless=False,
#                     disable_security=True,
#                     extra_chromium_args=[f"--window-size={window_w},{window_h}"],
#                     chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
#                 )
#             )
#             async with await browser.new_context(
#                     config=BrowserContextConfig(
#                         no_viewport=False,
#                         browser_window_size=BrowserContextWindowSize(
#                             width=window_w, height=window_h
#                         ),
#                     )
#             ) as browser_context:
#                 agent = CustomAgent(
#                     task=AGENT_PROMPT,
#                     llm=llm,
#                     browser_context=browser_context,
#                     use_vision=use_vision,
#                     tool_calling_method="function_calling",
#                     system_prompt_class=CustomSystemPrompt,
#                     agent_prompt_class=CustomAgentMessagePrompt,
#                 )
#                 history = await agent.run(max_steps=15)
                
#             await browser.close()
#             return history
#         except Exception as e:
#             retries -= 1
#             if retries == 0:
#                 raise e
#             print(f"Attempt failed, retrying... {3-retries}/3")

