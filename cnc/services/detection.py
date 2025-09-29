import enum
from pydantic import BaseModel
from typing import List, Optional

from src.agent.discovery.pages import PageObservations, Page
from src.llm_provider import LMP
from src.llm_models import BaseChatModel

from httplib import HTTPMessage
from cnc.database.agent.models import ExploitAgentModel

# TODO: potentially change to being able to specify multiple page items
class ScheduledActionLM(BaseModel):
    page_item_id: str
    vulnerability_description: str
    vulnerability_title: str

class ScheduledActionsLM(BaseModel):
    actions: List[ScheduledActionLM]

class StartExploitRequestData(BaseModel):
    page_item: Optional[HTTPMessage]
    vulnerability_description: str
    vulnerability_title: str

    class Config:
        arbitrary_types_allowed = True

    async def to_dict(self):
        return {
            "page_item": await self.page_item.to_json() if self.page_item else None,
            "vulnerability_description": self.vulnerability_description,
            "vulnerability_title": self.vulnerability_title
        }

    @classmethod
    def from_dict(cls, data: dict):
        return StartExploitRequestData(
            page_item=HTTPMessage.from_json(data["page_item"]) if data["page_item"] else None,
            vulnerability_description=data["vulnerability_description"],
            vulnerability_title=data["vulnerability_title"]
        )

class DetectAndSchedule(LMP):
    prompt = """
{% if selected_id %}
Target scope: {{selected_id}}
{{pages_subset}}
{% else %}
Target scope: ALL
{{pages}}
{% endif %}

You are given the above notes collected during the recon phase of a pentest. Reflect on the info collected above and come up with a prioritized list of actions to take that might help you uncover more vulnerabilities. These actions should contain:
1. One of items mentioned in the recon report
2. The targeted vulnerability to search for in that item

Come up with a list of {{num_actions}} actions, prioritized by likelihood/impact.

Notes:
- If Target scope is not ALL, only consider the subset of notes related to that id and its contents.
- Every identifiable page item is prefixed with an id string in the format "a.b".
- While each page item covers a lot of content, tailor your vulnerability description to the specific aspect most relevant to the vulnerability.
"""
    response_format = ScheduledActionsLM

    def _process_result(self, res: ScheduledActionsLM, **prompt_args) -> List[StartExploitRequestData]:
        pages: PageObservations = prompt_args["pages"]
        scheduled_actions = []

        for action in res.actions:
            scheduled_actions.append(
                StartExploitRequestData(
                    page_item=pages.get_page_item(action.page_item_id), 
                    vulnerability_description=action.vulnerability_description,
                    vulnerability_title=action.vulnerability_title
                )
            )
            
        return scheduled_actions    


class DetectionMode(str, enum.Enum):
    PAGESTEP_TRIGGER = "page_step_trigger"

class DetectionScheduler:
    """Detects suspicious items on the page and schedules actions for the exploit agent"""
    def __init__(
        self,
        prev_agents: Optional[List[ExploitAgentModel]] = None,
        trigger_mode: DetectionMode = DetectionMode.PAGESTEP_TRIGGER
    ):
        self.prev_agents = prev_agents
        self.trigger_mode = trigger_mode

    def trigger(self, page_steps: int, max_page_steps: int) -> bool:
        if self.trigger_mode == DetectionMode.PAGESTEP_TRIGGER:
            return page_steps >= max_page_steps
        return False

    async def generate_actions(
        self,
        model: BaseChatModel,
        pages: PageObservations,
        page_steps: int,
        max_page_steps: int,
        num_actions: int
    ) -> List[StartExploitRequestData]:
        if not self.trigger(page_steps, max_page_steps):
            return []

        return await DetectAndSchedule().ainvoke(
            model,
            prompt_args={
                "pages": pages,
                "pages_subset": None,
                "num_actions": num_actions,
                "selected_id": None,
            }
        )
    
    async def generate_actions_no_trigger(
        self,
        model: BaseChatModel,
        pages: PageObservations,
        num_actions: int
    ) -> List[StartExploitRequestData]:
        return await DetectAndSchedule().ainvoke(
            model,
            prompt_args={
                "pages": pages,
                "pages_subset": None,
                "num_actions": num_actions,
                "selected_id": None,
            }
        )

    def _build_pages_prompt(self, pages: PageObservations, page_item_id: Optional[str]) -> str:
        if not page_item_id:
            return str(pages)

        try:
            parts = page_item_id.split(".")
            page_id = parts[0]
            page = next((p for p in pages.pages if getattr(p, "id", "") == page_id), None)
            if not page:
                return str(pages)

            # If only page-level id is provided, restrict to that page
            if len(parts) == 1 or not parts[1].isdigit():
                subset = PageObservations([page])
                return str(subset)

            section_idx = int(parts[1])
            if section_idx <= 0 or section_idx > len(page._group_order):
                subset = PageObservations([page])
                return str(subset)

            key = page._group_order[section_idx - 1]
            msgs = [m for m in page._groups.get(key, [])]
            new_page = Page(url=page.url, http_msgs=list(msgs), item_id=page.id)
            subset = PageObservations([new_page])
            return str(subset)
        except Exception:
            # Fallback to full
            return str(pages)

    async def generate_actions_for_item(
        self,
        model: BaseChatModel,
        pages: PageObservations,
        page_steps: int,
        max_page_steps: int,
        num_actions: int,
        page_item_id: Optional[str] = None,
    ) -> List[StartExploitRequestData]:
        if not self.trigger(page_steps, max_page_steps):
            return []

        pages_text = self._build_pages_prompt(pages, None)
        pages_subset_text = self._build_pages_prompt(pages, page_item_id) if page_item_id else None
        return await DetectAndSchedule().ainvoke(
            model,
            prompt_args={
                "pages": pages_text,
                "pages_subset": pages_subset_text,
                "num_actions": num_actions,
                "selected_id": page_item_id,
            }
        )

    async def generate_actions_no_trigger_for_item(
        self,
        model: BaseChatModel,
        pages: PageObservations,
        num_actions: int,
        page_item_id: Optional[str] = None,
    ) -> List[StartExploitRequestData]:
        pages_text = self._build_pages_prompt(pages, None)
        pages_subset_text = self._build_pages_prompt(pages, page_item_id) if page_item_id else None
        return await DetectAndSchedule().ainvoke(
            model,
            prompt_args={
                "pages": pages_text,
                "pages_subset": pages_subset_text,
                "num_actions": num_actions,
                "selected_id": page_item_id,
            }
        )