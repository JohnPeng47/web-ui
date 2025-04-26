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

class Range(BaseModel):
    low: int
    high: Optional[int]

class SeverityRange(BaseModel):
    low: Range
    medium: Range
    high: Range
    critical: Range
    
class Payouts(BaseModel):
    payouts: Union[SeverityRange, Dict]

class CategorizeReports(LMP):
    prompt = """
{{agent_history}}

You are given the browsing history of a websearch agent as it tries to collect information on payouts 
for a bug bounty program. Determine if the information is present in the agent history. If it is not,
then leave payouts as an empty dict {}

If it does exist then fill out the payout ranges accordingly
"""
    response_format = Payouts

def extract_payout(model, history, company):
    history = extract_state_from_history(history)
    res = CategorizeReports().invoke(model,
                               model_name="deepseek/deepseek-chat", 
                               prompt_args={
                                   "agent_history": str(history)
                               })
    return res.payouts

async def get_bounty_payout(company):
    AGENT_PROMPT = """
Can you use google.com to find the hackerone company page for:
{company}
By searching with the query "hackerone {company}"
*Make sure that you actually navigate to "https://google.com" FIRST, even if the default page is google*
Then type in the query and click "Google Search" button
Find the company page in the search results; it should be the first one that pops up
Navigate to the page
Then after it loads, determine if the page contains payout information segmented by the severity of the bugs discovered
ie. LOW ($100 - $200), MEDIUM ($500-1000) ... 
<critical_step>
If it does, then capture this payout structure and make a note of this information in your thoughts
If not, then also make a note of its absence in your thoughts
</critical_step>
Once the above critical_step has been accomplished, terminate
""".format(company=company)
    
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
                    extra_chromium_args=[f"--window-size={window_w},{window_h}"],
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
                )
                history = await agent.run(max_steps=15)
                
            await browser.close()
            return history
        except Exception as e:
            retries -= 1
            if retries == 0:
                raise e
            print(f"Attempt failed, retrying... {3-retries}/3")


if __name__ == "__main__":
    import os
    # asyncio.run(test_browser_use_org())
    # asyncio.run(test_browser_use_parallel())
    # asyncio.run(test_browser_use_custom())
    
    init_root_logger()

    model = LLMModel()
    payouts = {}
    
    # Check if payouts.json exists and load existing data
    payouts_path = "scripts/bounty_payouts/payouts.json"
    if os.path.exists(payouts_path):
        with open(payouts_path, "r") as payouts_file:
            payouts = json.loads(payouts_file.read())
            print(f"Loaded {len(payouts)} existing payouts")
    
    # Find companies with empty values in payouts.json
    companies_to_process = [company for company, data in payouts.items() if not data]
    for company in companies_to_process:
        print(company)
    print(f"Processing {len(companies_to_process)} companies with empty data")
    
    for i, company in enumerate(companies_to_process, start=1):
        print(f"Getting payouts for company {i}/{len(companies_to_process)} ({company})")

        history = asyncio.run(get_bounty_payout(company))
        if history:
            payout = extract_payout(model, history.model_dump(), company)
            if payout:
                payouts[company] = payout.model_dump()
        
        with open(payouts_path, "w") as payouts_file:
            payouts_file.write(json.dumps(payouts, indent=4))

    print(model.cost)
