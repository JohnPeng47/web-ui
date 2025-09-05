from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

from .auth import UserCredentialsBase

class UserRole(BaseModel):
    role: str
    credentials: UserCredentialsBase

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "credentials": self.credentials.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserRole":
        return cls(role=data["role"], credentials=UserCredentialsBase.from_dict(data["credentials"]))

class EngagementBase(BaseModel):
    name: str
    base_url: str
    scopes: Optional[List[str]] = None
    description: Optional[str] = None

class EngagementCreate(EngagementBase):
    pass

class EngagementOut(EngagementBase):
    id: UUID
    created_at: datetime
    findings: Optional[List[Dict[str, Any]]] = None
    domain_ownership_verified: bool = False

    class Config:
        from_attributes = True

class Finding(BaseModel):
    user: str
    resource_id: str
    action: str
    additional_info: Optional[Dict[str, Any]] = None

class AddFindingRequest(BaseModel):
    finding: Finding