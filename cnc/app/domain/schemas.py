from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel

from .models import Role


class AuthSession(BaseModel):
    token: str
    expires_at: int


class UserCtx(BaseModel):
    id: UUID
    role: Role
    username: str
    session: Optional[AuthSession] = None