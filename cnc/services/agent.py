from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from cnc.database import crud
from cnc.schemas.application import AgentRegister
from cnc.database.models import Agent

from httplib import HTTPMessage

async def register(db: AsyncSession, app_id: UUID, agent_data: AgentRegister) -> Agent:
    """Register a new agent for an application."""
    # Verify application exists
    app = await crud.get_application(db, app_id)
    if not app:
        raise ValueError(f"Application with ID {app_id} not found")
    
    return await crud.register_agent(db, app_id, agent_data)


async def get_agent(db: AsyncSession, agent_id: UUID) -> Agent:
    """Get an agent by ID."""
    agent = await crud.get_agent(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    return agent


async def verify_agent(
    db: AsyncSession, app_id: UUID, username: str, role: str
) -> Optional[Agent]:
    """Verify if an agent exists with the given credentials."""
    return await crud.get_agent_by_credentials(db, app_id, username, role)


async def store_messages(
    db: AsyncSession, agent_id: UUID, messages: List[HTTPMessage]
) -> None:
    """Store HTTP messages sent by an agent."""
    agent = await crud.get_agent(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    
    await crud.store_http_messages(db, agent_id, agent.application_id, messages)