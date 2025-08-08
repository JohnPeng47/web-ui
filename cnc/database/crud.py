from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlmodel import select

from helpers.uuid import generate_uuid
from schemas.application import ApplicationCreate, AgentRegister
from cnc.database.models import Application, Agent, HTTPMessageDB, AuthSession

from httplib import HTTPMessage


async def create_application(
    db: AsyncSession, app_data: ApplicationCreate
) -> Application:
    app = Application(
        id=generate_uuid(),
        name=app_data.name,
        description=app_data.description,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def get_application(db: AsyncSession, app_id: UUID) -> Optional[Application]:
    result = await db.execute(select(Application).where(Application.id == app_id))
    return result.scalars().first()


async def update_application(db: AsyncSession, app: Application) -> Application:
    """Update an application with new data."""
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


async def register_agent(
    db: AsyncSession, app_id: UUID, agent_data: AgentRegister
) -> Agent:
    agent = Agent(
        id=generate_uuid(),
        user_name=agent_data.user_name,
        role=agent_data.role,
        application_id=app_id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(db: AsyncSession, agent_id: UUID) -> Optional[Agent]:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalars().first()


async def get_agent_by_credentials(
    db: AsyncSession, app_id: UUID, username: str, role: str
) -> Optional[Agent]:
    result = await db.execute(
        select(Agent).where(
            Agent.application_id == app_id,
            Agent.user_name == username,
            Agent.role == role
        )
    )
    return result.scalars().first()


async def store_http_messages(
    db: AsyncSession, agent_id: UUID, app_id: UUID, messages: List[HTTPMessage]
) -> List[HTTPMessageDB]:
    db_messages = []
    
    for msg in messages:
        db_msg = HTTPMessageDB(
            id=generate_uuid(),
            agent_id=agent_id,
            application_id=app_id,
            
            # Request data
            method=msg.request.method,
            url=str(msg.request.url),
            headers=msg.request.headers,
            post_data=msg.request.post_data if isinstance(msg.request.post_data, dict) else None,
            redirected_from_url=str(msg.request.redirected_from) if msg.request.redirected_from else None,
            redirected_to_url=str(msg.request.redirected_to) if msg.request.redirected_to else None,
            is_iframe_request=msg.request.is_iframe,
        )
        
        if msg.response:
            db_msg.response_status = msg.response.status
            db_msg.response_headers = msg.response.headers
            db_msg.response_is_iframe = msg.response.is_iframe
            # db_msg.response_body_b64 = msg.response.body_b64
            # db_msg.response_body_error = msg.response.body_error
        
        db_messages.append(db_msg)
        db.add(db_msg)
    
    await db.commit()
    for msg in db_messages:
        await db.refresh(msg)
    
    return db_messages


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
            AuthSession.application_id == app_id,
            AuthSession.session_id == session_id
        )
    )
    session = result.scalars().first()
    
    if not session:
        # Create new session
        session = AuthSession(
            id=generate_uuid(),
            application_id=app_id,
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
            AuthSession.application_id == app_id,
            AuthSession.session_id == session_id
        )
    )
    return result.scalars().first()