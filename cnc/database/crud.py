from typing import Optional, Union, List, Any, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from cnc.helpers.uuid import generate_uuid
from cnc.schemas.engagement import EngagementCreate
from cnc.database.models import (
    PentestEngagement,
    AuthSession,
    PentestEngagementDiscoveryAgent,
    PentestEngagementExploitAgent,
)
from cnc.database.agent.models import AgentBase, ExploitAgentModel, DiscoveryAgentModel
from src.agent.base import AgentType

async def create_engagement(
    db: AsyncSession, engagement_data: EngagementCreate
) -> PentestEngagement:
    app = PentestEngagement(
        id=generate_uuid(),
        scopes_data=engagement_data.scopes_data,
        name=engagement_data.name,
        base_url=engagement_data.base_url,
        description=engagement_data.description,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def get_engagement(db: AsyncSession, engagement_id: UUID) -> Optional[PentestEngagement]:
    result = await db.execute(select(PentestEngagement).where(PentestEngagement.id == engagement_id))
    return result.scalars().first()


async def list_engagements(db: AsyncSession) -> List[PentestEngagement]:
    """Return all pentest engagements."""
    result = await db.execute(select(PentestEngagement))
    return list(result.scalars().all())


async def update_engagement(db: AsyncSession, app: PentestEngagement) -> PentestEngagement:
    """Update an engagement with new data."""
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def create_or_update_session(
    db: AsyncSession, 
    app_id: UUID, 
    session_id: str, 
    username: str, 
    role: str
) -> AuthSession:
    # Check if session exists
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.engagement_id == app_id,
            AuthSession.session_id == session_id
        )
    )
    session = result.scalars().first()
    
    if not session:
        # Create new session
        session = AuthSession(
            id=generate_uuid(),
            engagement_id=app_id,
            session_id=session_id,
            username=username,
            role=role
        )
        db.add(session)
    else:
        # Update existing session
        session.username = username
        session.role = role
    
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_id(
    db: AsyncSession, app_id: UUID, session_id: str
) -> Optional[AuthSession]:
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.engagement_id == app_id,
            AuthSession.session_id == session_id
        )
    )
    return result.scalars().first()


async def get_engagement_by_agent_id(
    db: AsyncSession, agent_id: str
) -> Optional[PentestEngagement]:
    """Return the engagement associated with a discovery or exploit agent id."""
    # Try discovery agent link first
    res = await db.execute(
        select(PentestEngagementDiscoveryAgent.pentest_engagement_id).where(
            PentestEngagementDiscoveryAgent.discovery_agent_id == agent_id
        )
    )
    engagement_id = res.scalars().first()
    if engagement_id is not None:
        engagement = await get_engagement(db, engagement_id)
        if engagement is not None:
            return engagement

    # Fallback to exploit agent link
    res = await db.execute(
        select(PentestEngagementExploitAgent.pentest_engagement_id).where(
            PentestEngagementExploitAgent.exploit_agent_id == agent_id
        )
    )
    engagement_id = res.scalars().first()
    if engagement_id is not None:
        return await get_engagement(db, engagement_id)
    return None

async def list_agents_for_engagement(
    db: AsyncSession, engagement_id: UUID, agent_type: Optional[str] = None
) -> List[Union[ExploitAgentModel, DiscoveryAgentModel]]:
    """Enumerate all agents attached to an engagement id.

    Returns list of AgentBase SQLModel ORM objects.
    
    Args:
        db: Database session
        engagement_id: ID of the engagement
        agent_type: Optional filter for agent type ("exploit" or "discovery")
    """
    agents = []
    
    # Get exploit agents if requested or no filter specified
    if agent_type is None or agent_type == "exploit":
        exploit_ids_subq = (
            select(PentestEngagementExploitAgent.exploit_agent_id)
            .where(PentestEngagementExploitAgent.pentest_engagement_id == engagement_id)
        )
        exploit_result = await db.execute(
            select(ExploitAgentModel).where(
                cast(Any, ExploitAgentModel.id).in_(exploit_ids_subq)  # type: ignore
            )
        )
        exploit_agents = exploit_result.scalars().all()
        agents.extend(exploit_agents)

    # Get discovery agents if requested or no filter specified
    if agent_type is None or agent_type == "discovery":
        discovery_ids_subq = (
            select(PentestEngagementDiscoveryAgent.discovery_agent_id)
            .where(PentestEngagementDiscoveryAgent.pentest_engagement_id == engagement_id)
        )
        discovery_result = await db.execute(
            select(DiscoveryAgentModel).where(
                cast(Any, DiscoveryAgentModel.id).in_(discovery_ids_subq)  # type: ignore
            )
        )
        discovery_agents = discovery_result.scalars().all()
        agents.extend(discovery_agents)
    
    return agents