from typing import List, Optional, Dict, Any
from pydantic import BaseModel, UUID4
from datetime import datetime
from httplib import HTTPMessage
from uuid import UUID


class ApplicationBase(BaseModel):
    name: str
    description: Optional[str] = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationOut(ApplicationBase):
    id: UUID
    created_at: datetime
    findings: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class AgentRegister(BaseModel):
    user_name: str
    role: str


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
    messages: List[HTTPMessage]

class Finding(BaseModel):
    user: str
    resource_id: str
    action: str
    additional_info: Optional[Dict[str, Any]] = None

class AddFindingRequest(BaseModel):
    finding: Finding