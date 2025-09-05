from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.agent.base import AgentType
from cnc.schemas.base import JSONModel
# NOTE: we should make use and subclass this instead of redefining the fields in DiscoveryAgentStep
# from pentest_bot.models.steps import AgentStep as _DiscoveryAgentStep

class AgentOut(BaseModel):
    id: int
    agent_status: str
    max_steps: int
    model_name: str
    model_costs: float
    log_filepath: str
    created_at: datetime

    class Config:
        from_attributes = True

class AgentMessage(BaseModel):
    agent_id: int

class AgentStep(JSONModel):
    def to_dict(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentStep":
        return cls(**data)

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


class ExploitAgentCreate(BaseModel):
    max_steps: int
    model_name: str
    model_costs: Optional[float] = None
    log_filepath: Optional[str] = None
    agent_status: Optional[str] = "active"


class UploadAgentSteps(AgentMessage):
    steps: List[ExploitAgentStep]


# class PushMessages(AgentMessage):
#     http_msgs: List[HTTPMessage]
#     browser_actions: Optional[BrowserActions]

#     class Config:
#         arbitrary_types_allowed = True  # Allows non-Pydantic models
