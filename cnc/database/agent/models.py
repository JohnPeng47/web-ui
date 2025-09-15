from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, JSON
import uuid

from cnc.schemas.agent import ExploitAgentStep
from cnc.schemas.agent import AgentStatus
from src.agent.base import AgentType

class AgentBase(SQLModel, table=False):    
    # sqlite won't accept UUID4 for some reason
    # 2**61 half of UUID4 key space
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    agent_status: AgentStatus = Field(default=AgentStatus.PENDING, nullable=False)
    max_steps: int = Field(nullable=False)
    model_name: str = Field(nullable=False)
    model_costs: float = Field(nullable=True)
    log_filepath: str = Field(nullable=True) # add this later
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent_type: str = Field(nullable=False)
    
    # Opik metadata fields
    opik_prompt_name: Optional[str] = None
    opik_prompt_commit: Optional[str] = None

    @property
    def agent_name(self) -> str:
        raise NotImplementedError("Subclasses must implement this method")
        
class ExploitAgentModel(AgentBase, table=True):
    __tablename__ = "exploitagent"

    vulnerability_title: str = Field(nullable=False)
    agent_steps_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of agent"
    )    
    @property
    def agent_name(self) -> str:
        return self.vulnerability_title

    @property
    def agent_steps(self) -> List[ExploitAgentStep]:
        if not self.agent_steps_data:
            return []

        return [
            ExploitAgentStep.from_dict(step_data) for step_data in self.agent_steps_data
        ]

class DiscoveryAgentModel(AgentBase, table=True):
    __tablename__ = "discoveryagent"

    agent_steps_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of agent"
    )
    page_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of pages"
    )
    @property
    def agent_name(self) -> str:
        return "Discovery Agent"