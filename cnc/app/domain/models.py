import enum
import json
from uuid import uuid4, UUID
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import Optional, Dict, Any
from pydantic import ConfigDict

# We'll use a standard Dict for JSON data
Json = Dict[str, Any]


class Role(str, enum.Enum):
    REGULAR = "regular"
    COLLABORATOR = "collaborator"
    ADMIN = "admin"


class Application(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str


class AppUser(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="application.id")
    username: str
    role: Role
    session: Json = Field(sa_column=Column(JSON))


class Request(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="application.id")
    user_id: UUID = Field(foreign_key="appuser.id")
    method: str
    url: str
    headers: Json = Field(sa_column=Column(JSON))
    post_data: Optional[str] = None


class Finding(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    request_id: UUID = Field(foreign_key="request.id")
    finding_type: str
    severity: str
    description: str
    data: Json = Field(sa_column=Column(JSON))