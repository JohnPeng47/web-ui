from typing import Optional, Union
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
    db: AsyncSession, agent_id: int
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