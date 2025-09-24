import enum

from pydantic import BaseModel, UUID4, field_validator
from typing import Dict, Any, List, Optional, Literal, cast

from src.agent.discovery.pages import PageObservations, Page

from src.agent.base import AgentType
from cnc.schemas.base import DerivedJSONModel
# NOTE: we should make use and subclass this instead of redefining the fields in DiscoveryAgentStep
# from pentest_bot.models.steps import AgentStep as _DiscoveryAgentStep

class AgentStatus(str, enum.Enum):
    PENDING_AUTO = "pending_auto"
    PENDING_APPROVAL = "pending_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AgentOut(BaseModel):
    id: str
    agent_status: AgentStatus
    agent_type: AgentType
    agent_name: str

    class Config:
        from_attributes = True

class AgentMessage(BaseModel):
    agent_id: str

class AgentStep(DerivedJSONModel):
    def to_dict(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentStep":
        return cls(**data)

class DiscoveryAgentCreate(BaseModel):
    max_steps: int
    model_name: str
    model_costs: Optional[float] = None
    log_filepath: Optional[str] = None
    agent_type: Optional[AgentType] = AgentType.DISCOVERY

class ExploitAgentCreate(BaseModel):
    vulnerability_title: str
    max_steps: int
    model_name: str
    model_costs: Optional[float] = None
    log_filepath: Optional[str] = None
    agent_type: Optional[AgentType] = AgentType.EXPLOIT
    
# TODO: test uploading exploit agent steps first
class ExploitAgentStep(AgentStep):
    step_num: int
    reflection: str
    script: str
    execution_output: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_num": self.step_num,
            "reflection": self.reflection,
            "script": self.script,
            "execution_output": self.execution_output,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExploitAgentStep":
        return cls(**data)

class UploadAgentSteps(AgentMessage):
    steps: List[ExploitAgentStep]
    max_steps: int
    found_exploit: bool

class UploadPageData(AgentMessage):
    """Upload model for PageObservations coming from src.agent.discovery.pages.PageObservations.to_json().
    Accepts a list of page dicts as-is to keep schema flexible and aligned with runtime objects.
    """
    steps: int
    max_steps: int
    page_steps: int
    max_page_steps: int
    page_data: List[Dict[str, Any]]

    def to_page_observations(self) -> PageObservations:
        pages_list = [Page.from_json(page) for page in cast(List[dict], self.page_data)]
        pages_obj = PageObservations(pages=pages_list)
        return pages_obj
    
# TODO: ask chatGPT to implement this 
class AgentApproveData(DerivedJSONModel):
    """Model for structuring """
    agent_id: str
    approve_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentApproveData":
        return cls(**data)

class AgentApproveBinary(DerivedJSONModel):
    agent_id: str
    approve_data: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "decision": self.approve_data,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentApproveBinary":
        return cls(**data)

# # Attack Requests
# class 