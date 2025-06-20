from src.llm_provider import LMP
from pydantic import BaseModel
from typing import List, Type
import enum

from .planv1 import Plan, PlanItem, CreatePlan as CreatePlan
from .planv2 import CreatePlanNested

from pentest_bot.logger import get_agent_loggers

agent_log, _ = get_agent_loggers()

# TODO: do we actually need to introduce a preamble to introduce the concept of web-crawling agent?
TASK_PROMPT_WITH_PLAN = """
Your task is to execute each action in the following plan that aims to exhaustively cover all possible
interactions with the current webpage:

{plan}
"""

## update plan
class AddPlanItem(BaseModel):
    plan_item: PlanItem
    index: int

class AddPlanItemList(BaseModel):
    plan_items: List[AddPlanItem]

    def apply(self, plan: Plan):
        for item in self.plan_items:
            plan.plan_items.insert(item.index, item.plan_item)
        return plan

class UpdatePlan(LMP):
    prompt = """
Here is the current plan:
{{plan}}
    
Here is the current webpage:
{{curr_page_contents}}

Here is the previous webpage:
{{prev_page_contents}}

Here is the evaluation of the previous goal that led to a transition to the current webpage:
{{prev_goal_eval}}

Now determine if the plan needs to be updated. This should happen in the following cases:
- some new UI elements have been discovered adding an area to explore that is not covered by a previous plan item

Now return your response as a list of plan items that will get added to the plan. 
This list should be empty if the plan does not need to be updated
"""
    response_format: Type[AddPlanItemList] = AddPlanItemList

    def _process_result(self, res: AddPlanItemList, **prompt_args):
        plan: Plan = prompt_args["plan"]
        res.apply(plan)

        new_plan_items = '\n'.join([str(item) for item in res.plan_items])
        agent_log.info(f"Added plan items:\n{new_plan_items}")
        return plan

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
    response_format: Type[CompletedPlans] = CompletedPlans

    def _process_result(self, res: CompletedPlans, **prompt_args):        
        plan: Plan = prompt_args["plan"]
        for compl in res.completed_plans:
            # +1 because plan items are 1-indexed
            plan.plan_items[compl + 1].completed = True
            agent_log.info(f"Completed plan item: {plan.plan_items[compl + 1].description}")
        return plan
    
## new page
# TODO: ask if current page is a child of the previous page
# TODO: we should detect OFFSITE by using a scope argument
class NewPageStatus(enum.Enum):
    NEW_PAGE = "new_page"
    NO_CHANGE = "no_change"
    SUBPAGE = "subpage"
    OUT_OF_SCOPE = "out_of_scope"

class NavPage(BaseModel):
    name: str
    status: NewPageStatus

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
    response_format: Type[NavPage] = NavPage

