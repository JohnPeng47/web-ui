from pydantic import BaseModel

from typing import List, Optional

from src.agent.discovery.pages import PageObservations
from src.llm_provider import LMP
from common.constants import NUM_SCHEDULED_ACTIONS

from httplib import HTTPMessage

# TMRW: 
# - add a vulnerability title along with description to display the data

# TODO: potentially change to being able to specify multiple page items
class ScheduledActionLM(BaseModel):
    page_item_id: str
    vulnerability_description: str
    vulnerability_title: str

class ScheduledActionsLM(BaseModel):
    actions: List[ScheduledActionLM]

class StartExploitRequest(BaseModel):
    page_item: Optional[HTTPMessage]
    vulnerability_description: str
    vulnerability_title: str

    class Config:
        arbitrary_types_allowed = True

class DetectAndSchedule(LMP):
    prompt = """
{{pages}}

You are given the above notes collected during the recond phase of a pentest. Reflect on the info collected above and come up with a prioritized list of actions to take that might help you uncover more vulnerabilities. These actions should contain:
1. One of items mentioned in the recon report
2. The targeted vulnerability to search for in that item

Come up with a list of {{num_actions}} actions, prioritized by likelihood/impact

Some guidance for the response format:
- return a short, descriptive vulnerability title
- every identifiable page item is prefixed with a id string in the format "a.b"
- while each page item covers alot of content, you can tailor your vulnerability description to the specific aspect of the page item that is most relevant to the vulnerability you are looking for
"""
    response_format = ScheduledActionsLM

    def _process_result(self, res: ScheduledActionsLM, **prompt_args) -> List[StartExploitRequest]:
        pages: PageObservations = prompt_args["pages"]
        scheduled_actions = []

        for action in res.actions:
            scheduled_actions.append(
                StartExploitRequest(
                    page_item=pages.get_page_item(action.page_item_id), 
                    vulnerability_description=action.vulnerability_description,
                    vulnerability_title=action.vulnerability_title
                )
            )
            
        return scheduled_actions