from pydantic import BaseModel, UUID4
from datetime import datetime
from enum import Enum
from typing import Dict, Any

from src.agent.base import AgentType
from cnc.schemas.base import JSONModel
# NOTE: we should make use and subclass this instead of redefining the fields in DiscoveryAgentStep
# from pentest_bot.models.steps import AgentStep as _DiscoveryAgentStep

class AgentOut(BaseModel):
    id: UUID4
    user_name: str
    role: str
    application_id: UUID4
    created_at: datetime

    class Config:
        from_attributes = True

class AgentMessage(BaseModel):
    agent_id: UUID4

class AgentStep(JSONModel):
    def to_dict(self) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentStep":
        return cls(**data)

class DiscoveryAgentStep(AgentStep):
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
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveryAgentStep":
        return cls(**data)


# class PushMessages(AgentMessage):
#     http_msgs: List[HTTPMessage]
#     browser_actions: Optional[BrowserActions]

#     class Config:
#         arbitrary_types_allowed = True  # Allows non-Pydantic models
