from johnllm import LMP
from pydantic import BaseModel
from typing import List

# TODO: should we register a complete plan action?
TASK_PROMPT_WITH_PLAN = """
Your task is to execute each action in the following plan that aims to exhaustively cover all possible
interactions with the current webpage:

{plan}
"""

class PlanItem(BaseModel):
    action: str
    description: str

class Plan(BaseModel):
    plan_items: List[PlanItem]

class CreatePlan(LMP):
    prompt = """
You are tasked with creating a plan for navigating a webpage. The plan should be exhaustive in covering steps for every 
possible interaction with the current webpage. Here is the current webpage:
{{curr_page_contents}}

Now generate your plan
"""
    response_format = Plan

## new page

class NewPage(BaseModel):
	is_new_page: bool
		
class IsNewPage(LMP):
	prompt = """
You are tasked with determining if the current DOM state of a browser is the same or different page from the previous one,
indicating that the browser has executed a navigational action between the two states. Be careful to differentiate between
different webpages and the same webpage with a slightly changed view (ie. popup, menu dropdown, etc.)

Here is the new page:
{{new_page}}

Here is the previous page:
{{old_page}}

You are tasked with determining if the current DOM state of a browser is the same or different page from the previous one,
indicating that the browser has executed a navigational action between the two states. Be careful to differentiate between
different webpages and the same weebpage with a slightly changed view (ie. popup, menu dropdown, etc.)

Now answer, has the page changed?
"""
	response_format = NewPage
