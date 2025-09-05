from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, Column, JSON
from uuid import UUID

from cnc.schemas.agent import DiscoveryAgentStep

class AgentBase(SQLModel, table=False):    
    id: int = Field(primary_key=True, default=None)  # autoincrement is default
    agent_status: str = Field(default=False, nullable=False)
    max_steps: int = Field(nullable=False)
    model_name: str = Field(nullable=False)
    model_costs: float = Field(nullable=False)
    log_filepath: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Opik metadata fields
    opik_prompt_name: Optional[str] = None
    opik_prompt_commit: Optional[str] = None
        
class ExploitAgent(AgentBase, table=True):
    agent_steps_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of agent"
    )

class DiscoveryAgent(AgentBase, table=True):
    agent_steps_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of agent"
    )
    @property
    def agent_steps(self) -> List[DiscoveryAgentStep]:
        if not self.agent_steps_data:
            return []

        return [
            DiscoveryAgentStep.from_dict(step_data) for step_data in self.agent_steps_data
        ]
