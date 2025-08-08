from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON, Column, Relationship
from uuid import UUID
import json

class Application(SQLModel, table=True):
    # Tell SQLModel to use our specific metadata
    # metadata = db_metadata

    id: UUID = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    findings: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    
    agents: List["Agent"] = Relationship(back_populates="application")


class Agent(SQLModel, table=True):
    # Tell SQLModel to use our specific metadata
    # metadata = db_metadata

    id: UUID = Field(primary_key=True)
    user_name: str
    role: str
    application_id: UUID = Field(foreign_key="application.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    application: "Application" = Relationship(back_populates="agents")
    http_messages: List["HTTPMessageDB"] = Relationship(back_populates="agent")


class AuthSession(SQLModel, table=True):
    # Tell SQLModel to use our specific metadata
    # metadata = db_metadata

    id: UUID = Field(primary_key=True)
    session_id: str
    username: str
    role: str
    application_id: UUID = Field(foreign_key="application.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class HTTPMessageDB(SQLModel, table=True):
    # Tell SQLModel to use our specific metadata
    # metadata = db_metadata

    id: UUID = Field(primary_key=True)
    agent_id: UUID = Field(foreign_key="agent.id")
    application_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Request data
    method: str
    url: str
    headers: Dict[str, str] = Field(sa_column=Column(JSON))
    post_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    redirected_from_url: Optional[str] = None
    redirected_to_url: Optional[str] = None
    is_iframe_request: bool = False
    
    # Response data (optional)
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    response_is_iframe: Optional[bool] = None
    response_body_b64: Optional[str] = None
    response_body_error: Optional[str] = None
    
    agent: "Agent" = Relationship(back_populates="http_messages")