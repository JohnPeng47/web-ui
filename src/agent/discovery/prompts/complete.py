from src.llm_provider import LMP
from pydantic import BaseModel
from typing import List, Type
import enum

from .planv1 import Plan, PlanItem, CreatePlan as CreatePlan
from ..planv2 import CreatePlanNested

from pentest_bot.logger import get_agent_loggers

agent_log, _ = get_agent_loggers()

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
            plan.plan_items[compl - 1].completed = True
            agent_log.info(f"Completed plan item: {plan.plan_items[compl - 1].description}")
        return plan

class CheckPlanCompletionV2(LMP):
    prompt = """
Here is a plan used by an agent to map out all the interactive components of a webpage:
{{plan}}

Here is the current webpage:
{{curr_page_contents}}

Here is the previous webpage:
{{prev_page_contents}}

Here is the previous goal that resulted in a transition to the current webpage:
{{prev_goal}}

Now try to determine which *new* plan items have been completed by the agent
"""
    response_format: Type[CompletedPlans] = CompletedPlans

    def _process_result(self, res: CompletedPlans, **prompt_args):        
        plan: Plan = prompt_args["plan"]
        for compl in res.completed_plans:
            # +1 because plan items are 1-indexed
            plan.plan_items[compl - 1].completed = True
            agent_log.info(f"Completed plan item: {plan.plan_items[compl - 1].description}")
        return plan
