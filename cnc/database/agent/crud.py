from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from sqlmodel import select

from cnc.database.models import (
    DiscoveryAgentModel,
    ExploitAgentModel,
    PentestEngagementDiscoveryAgent,
    PentestEngagementExploitAgent,
)
from cnc.schemas.agent import (
    DiscoveryAgentCreate, 
    ExploitAgentCreate, 
    ExploitAgentStep, 
    AgentStatus
)
from cnc.database.crud import get_engagement

async def register_discovery_agent(db: AsyncSession, engagement_id: UUID, payload: DiscoveryAgentCreate) -> DiscoveryAgentModel:
    """Create a new DiscoveryAgent under an engagement."""
    engagement = await get_engagement(db, engagement_id)
    if not engagement:
        raise ValueError(f"Engagement with ID {engagement_id} not found")

    agent = DiscoveryAgentModel(
        max_steps=payload.max_steps,
        model_name=payload.model_name,
        model_costs=payload.model_costs or 0.0,
        log_filepath=payload.log_filepath or "",
        agent_status=AgentStatus.RUNNING,
        agent_type=payload.agent_type.value if payload.agent_type else "discovery",
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

async def register_exploit_agent(db: AsyncSession, engagement_id: UUID, payload: ExploitAgentCreate) -> ExploitAgentModel:
    """Create a new ExploitAgent under an engagement."""
    engagement = await get_engagement(db, engagement_id)
    if not engagement:
        raise ValueError(f"Engagement with ID {engagement_id} not found")

    # Default status depends on manual approval mode (read dynamically)
    try:
        from common import constants as _constants  # local import to pick up test-time changes
        manual_flag = getattr(_constants, "MANUAL_APPROVAL_EXPLOIT_AGENT", False)
    except Exception:
        manual_flag = False
    default_status = AgentStatus.PENDING_APPROVAL if manual_flag else AgentStatus.PENDING_AUTO

    agent = ExploitAgentModel(
        vulnerability_title=payload.vulnerability_title,
        max_steps=payload.max_steps,
        model_name=payload.model_name,
        model_costs=payload.model_costs or 0.0,
        log_filepath=payload.log_filepath or "",
        agent_status=default_status,
        agent_type=payload.agent_type.value if payload.agent_type else "exploit",
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

async def set_exploit_approval_payload(
    db: AsyncSession, agent_id: str, payload: Dict[str, Any]
) -> ExploitAgentModel:
    agent = await get_agent_by_id(db, agent_id)
    if not agent or not isinstance(agent, ExploitAgentModel):
        raise ValueError(f"Exploit agent with ID {agent_id} not found")

    agent.approval_payload_data = payload
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent

async def clear_exploit_approval_payload(
    db: AsyncSession, agent_id: str
) -> ExploitAgentModel:
    agent = await get_agent_by_id(db, agent_id)
    if not agent or not isinstance(agent, ExploitAgentModel):
        raise ValueError(f"Exploit agent with ID {agent_id} not found")

    agent.approval_payload_data = None
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent

async def update_agent_status(
    db: AsyncSession, agent_id: str, status: AgentStatus
) -> Union[DiscoveryAgentModel, ExploitAgentModel]:
    agent = await get_agent_by_id(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    agent.agent_status = status
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent

async def get_agent_by_id(db: AsyncSession, agent_id: str) -> Optional[Union[DiscoveryAgentModel, ExploitAgentModel]]:
    # Try to find DiscoveryAgent first
    result = await db.execute(select(DiscoveryAgentModel).where(DiscoveryAgentModel.id == agent_id))
    discovery_agent = result.scalars().first()
    if discovery_agent:
        return discovery_agent
    
    # If not found, try ExploitAgent
    result = await db.execute(select(ExploitAgentModel).where(ExploitAgentModel.id == agent_id))
    exploit_agent = result.scalars().first()
    return exploit_agent

async def get_agent_steps(db: AsyncSession, agent_id: str) -> List[ExploitAgentStep]:
    agent = await get_agent_by_id(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")

    steps_data = agent.agent_steps_data or []
    return [ExploitAgentStep.from_dict(sd) for sd in steps_data]

async def append_discovery_agent_steps(
    db: AsyncSession, agent_id: str, steps: List[ExploitAgentStep], agent_finished: bool, logger
) -> Union[DiscoveryAgentModel, ExploitAgentModel]:
    agent = await get_agent_by_id(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    
    current_steps = list(agent.agent_steps_data or [])
    for step in steps:
        current_steps.append(step.to_dict())
        logger.info(f"Appending step: {step.to_dict()}")
    
    agent.agent_steps_data = current_steps
    agent.agent_status = AgentStatus.COMPLETED if agent_finished else agent.agent_status

    db.add(agent)   
    await db.commit()
    await db.refresh(agent)
    return agent

async def update_page_data(
    db: AsyncSession, agent_id: str, pages: List[Dict[str, Any]]
) -> DiscoveryAgentModel:
    """Replace the discovery agent's page_data with the provided pages list."""
    agent = await get_agent_by_id(db, agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")
    
    if not isinstance(agent, DiscoveryAgentModel):
        raise ValueError(f"Agent {agent_id} is not a DiscoveryAgent")

    agent.page_data = pages
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent