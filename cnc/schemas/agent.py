from typing import List, Optional
from pydantic import BaseModel, UUID4
from datetime import datetime
from httplib import HTTPMessage

from common.agent import BrowserActions

# REFACTOR: deprecating this model
# class AgentRegister(UserRoleCredentials):
#     pass

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

class PushMessages(AgentMessage):
    http_msgs: List[HTTPMessage]
    browser_actions: Optional[BrowserActions]

    class Config:
        arbitrary_types_allowed = True  # Allows non-Pydantic models
