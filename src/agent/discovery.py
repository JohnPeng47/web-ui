from johnllm import LMP
from pydantic import BaseModel
from typing import List
import enum

# TODO: do we actually need to introduce a preamble to introduce the concept of web-crawling agent?
TASK_PROMPT_WITH_PLAN = """
Your task is to execute each action in the following plan that aims to exhaustively cover all possible
interactions with the current webpage:

{plan}
"""

class PlanItem(BaseModel):
    description: str
    completed: bool = False

class Plan(BaseModel):
    plan_items: List[PlanItem]

    def __str__(self) -> str:
        lines = []

        for i, item in enumerate(self.plan_items, start=1):
            status = "[ * ]" if item.completed else "[ ]"
            lines.append(f"{status} {i+1}. {item.description}")

        return "\n".join(lines)

class AddPlanItem(BaseModel):
    plan_item: PlanItem
    index: int

class CreatePlan(LMP):
    prompt = """
You are tasked with creating a plan for navigating a webpage. The plan should be exhaustive in covering steps for every 
possible interaction with the current webpage. Here is the current webpage:
{{curr_page_contents}}

Here are some things to watch for when creating the plan:
- always refer to interactive elements by their name / description rather than by their numeric label
- interactions that are more likely to lead to new functionalities should be ranked higher

Now generate your plan 
"""
    response_format = Plan

## update plan
class UpdatePlan(LMP):
    prompt = """
Here is the current plan:
{{plan}}
    
Here is the current webpage:
{{curr_page_contents}}

Here is the previous webpage:
{{prev_page_contents}}


"""

## check plan completion
## TODO: wonder if we should use another approach ie. more in-line with eval task
## TODO: should base browser-use prompt as checking completion of plan item?
class CompletedPlans(BaseModel):
    completed_plans: List[int]

class CheckPlanCompletion(LMP):
    prompt = """
Here is a plan used by an agent to map out all the interactive components of a webpage:
{{plan}}

Here is the current webpage:
{{curr_page_contents}}

Here is the previous webpage:
{{prev_page_contents}}

Here is the previous goal that resulted in a transition to the current webpage:
{{prev_goal}}

Now try to determine which plan items have been completed by the agent
"""
    response_format = CompletedPlans
    
    def _process_result(self, res: CompletedPlans, **prompt_args):
        plan: Plan = prompt_args["plan"]
        for compl in res.completed_plans:
            # +1 because plan items are 1-indexed
            plan.plan_items[compl + 1].completed = True

        return plan

## new page
# TODO: ask if current page is a child of the previous page
# TODO: we should detect OFFSITE by using a scope argument
class NewPageStatus(enum.Enum):
    NEW_PAGE = "new_page"
    NO_CHANGE = "no_change"
    SUBPAGE = "subpage"
    OUT_OF_SCOPE = "out_of_scope"

class DetermineNewPage(LMP):
    prompt = """
Here is the current page:
URL: {{curr_url}}
Contents:
{{curr_page_contents}}

Here is the previous page:
URL: {{prev_url}}
Contents:
{{prev_page_contents}}

Here is the previous goal that resulted in a transition to the current page:
{{prev_goal}}

Here is the homepage:
URL: {{homepage_url}}
Contents:
{{homepage_contents}}

Now try to determine if the current page is a:
- new_page: a completely different page from the *homepage* but still part of the same web application
- subpage: a different view of the homepage (ie. popup, menu dropdown, etc.)
- out_of_scope: a completely different website from the *homepage*

Now answer with the status of the current page
"""
    response_format = NewPageStatus

