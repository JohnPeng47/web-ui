from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlmodel import select

from cnc.database.models import (
    DiscoveryAgent,
    ExploitAgent,
    PentestEngagementDiscoveryAgent,
    PentestEngagementExploitAgent,
)
from cnc.schemas.agent import DiscoveryAgentCreate, ExploitAgentCreate, ExploitAgentStep
from cnc.database.crud import get_engagement


async def register_discovery_agent(db: AsyncSession, engagement_id: UUID, payload: DiscoveryAgentCreate) -> DiscoveryAgent:
    """Create a new DiscoveryAgent under an engagement."""
    engagement = await get_engagement(db, engagement_id)
    if not engagement:
        raise ValueError(f"Engagement with ID {engagement_id} not found")

    agent = DiscoveryAgent(
        max_steps=payload.max_steps,
        model_name=payload.model_name,
        model_costs=payload.model_costs or 0.0,
        log_filepath=payload.log_filepath or "",
        agent_status=payload.agent_status or "active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Link agent to engagement via junction table
    link = PentestEngagementDiscoveryAgent(
        pentest_engagement_id=engagement_id,
        discovery_agent_id=agent.id,
    )
    db.add(link)
    await db.commit()
    return agent

async def register_exploit_agent(db: AsyncSession, engagement_id: UUID, payload: ExploitAgentCreate) -> ExploitAgent:
    """Create a new ExploitAgent under an engagement."""
    engagement = await get_engagement(db, engagement_id)
    if not engagement:
        raise ValueError(f"Engagement with ID {engagement_id} not found")

    agent = ExploitAgent(
        max_steps=payload.max_steps,
        model_name=payload.model_name,
        model_costs=payload.model_costs or 0.0,
        log_filepath=payload.log_filepath or "",
        agent_status=payload.agent_status or "active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Link agent to engagement via junction table
    link = PentestEngagementExploitAgent(
        pentest_engagement_id=engagement_id,
        exploit_agent_id=agent.id,
    )
    db.add(link)
    await db.commit()
    return agent

async def get_discovery_agent(db: AsyncSession, agent_id: int) -> Optional[DiscoveryAgent]:
    result = await db.execute(select(DiscoveryAgent).where(DiscoveryAgent.id == agent_id))
    return result.scalars().first()

async def get_agent_steps(db: AsyncSession, agent_id: int) -> List[ExploitAgentStep]:
    agent = await get_discovery_agent(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")

    steps_data = agent.agent_steps_data or []
    return [ExploitAgentStep.from_dict(sd) for sd in steps_data]

async def append_discovery_agent_steps(
    db: AsyncSession, agent_id: int, steps: List[ExploitAgentStep]
) -> DiscoveryAgent:
    agent = await get_discovery_agent(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")

    current_steps = list(agent.agent_steps_data or [])
    for step in steps:
        current_steps.append(step.to_dict())
    agent.agent_steps_data = current_steps

    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def update_page_data(
    db: AsyncSession, agent_id: int, pages: List[Dict[str, Any]]
) -> DiscoveryAgent:
    """Replace the discovery agent's page_data with the provided pages list."""
    agent = await get_discovery_agent(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")

    agent.page_data = pages
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent