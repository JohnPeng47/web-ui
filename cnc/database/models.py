from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON, Column, Relationship
from uuid import UUID

# from cnc.schemas.application import UserRole
from cnc.schemas.auth import PasswordCredentials

from cnc.database.agent.models import ExploitAgent, DiscoveryAgent

# Junction tables for many-to-many relationships
class PentestEngagementExploitAgent(SQLModel, table=True):
    """Junction table for PentestEngagement to ExploitAgent many-to-many relationship"""
    pentest_engagement_id: UUID = Field(foreign_key="pentestengagement.id", primary_key=True)
    exploit_agent_id: int = Field(foreign_key="exploitagent.id", primary_key=True)


class PentestEngagementDiscoveryAgent(SQLModel, table=True):
    """Junction table for PentestEngagement to DiscoveryAgent many-to-many relationship"""
    pentest_engagement_id: UUID = Field(foreign_key="pentestengagement.id", primary_key=True)
    discovery_agent_id: int = Field(foreign_key="discoveryagent.id", primary_key=True)


class PentestEngagement(SQLModel, table=True):
    """
    The highest-level domain model, which represents a pentest engagement on a (multiple?) web application(s)
    """
    id: UUID = Field(primary_key=True)
    name: str
    base_url: str
    domain_ownership_verified: bool = False
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    findings: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    
    # JSON fields stored with suffix _data
    user_roles_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        sa_column=Column(JSON),
        description="JSON array of user role objects with credentials"
    )
    
    # Many-to-many relationships to different agent types
    exploit_agents: List["ExploitAgent"] = Relationship(
        link_model=PentestEngagementExploitAgent,
        back_populates="pentest_engagements"
    )
    discovery_agents: List["DiscoveryAgent"] = Relationship(
        link_model=PentestEngagementDiscoveryAgent,
        back_populates="pentest_engagements"
    )
    
    @property
    def user_roles(self) -> List["PasswordCredentials"]:
        """Get user roles as PasswordCredentials objects"""
        if not self.user_roles_data:
            return []

        # NOTE: need dynamic serializer here
        return [
            PasswordCredentials.from_dict(role_data) for role_data in self.user_roles_data
        ]
    
    @property
    def agents(self) -> List[Union["ExploitAgent", "DiscoveryAgent"]]:
        """Get all associated agents as a heterogeneous list"""
        all_agents = []
        all_agents.extend(self.exploit_agents)
        all_agents.extend(self.discovery_agents)
        return all_agents
    
    def add_agent(self, agent: Union["ExploitAgent", "DiscoveryAgent"]) -> None:
        """Add an agent of any supported type"""
        if isinstance(agent, ExploitAgent):
            if agent not in self.exploit_agents:
                self.exploit_agents.append(agent)
        elif isinstance(agent, DiscoveryAgent):
            if agent not in self.discovery_agents:
                self.discovery_agents.append(agent)
        else:
            raise ValueError(f"Unsupported agent type: {type(agent)}")

class AuthSession(SQLModel, table=True):
    # Tell SQLModel to use our specific metadata
    # metadata = db_metadata

    id: UUID = Field(primary_key=True)
    session_id: str
    username: str
    role: str
    engagement_id: UUID = Field(foreign_key="pentestengagement.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)