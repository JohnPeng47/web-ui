from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from .auth import UserRoleCredentials

class UserRole(BaseModel):
    role: str
    credentials: UserRoleCredentials

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

class Finding(BaseModel):
    user: str
    resource_id: str
    action: str
    additional_info: Optional[Dict[str, Any]] = None

class AddFindingRequest(BaseModel):
    finding: Finding