from typing import List, Optional
from pydantic import BaseModel, UUID4
from datetime import datetime
from .http import HTTPMessage


class ApplicationBase(BaseModel):
    name: str
    description: Optional[str] = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationOut(ApplicationBase):
    id: UUID4
    created_at: datetime

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


class PushMessages(BaseModel):
    messages: List[HTTPMessage]