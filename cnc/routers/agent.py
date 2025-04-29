from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from uuid import UUID

from schemas.application import AgentRegister, AgentOut, PushMessages
from database.session import get_session
from services import agent as agent_service
from services.queue import queues
from database.models import Agent

router = APIRouter()


async def require_registered_agent(
    app_id: UUID,
    x_username: str = Header(...),
    x_role: str = Header(...),
    db: AsyncSession = Depends(get_session)
) -> Agent:
    """Dependency that ensures the agent is registered for the application."""
    agent = await agent_service.verify_agent(db, app_id, x_username, x_role)
    if not agent:
        raise HTTPException(
            status_code=401,
            detail=f"Agent with username {x_username} and role {x_role} not registered for this application",
        )
    return agent


@router.post("/application/{app_id}/agents/register", response_model=AgentOut)
async def register_agent(
    app_id: UUID, payload: AgentRegister, db: AsyncSession = Depends(get_session)
):
    """Register a new agent for an application."""
    try:
        agent = await agent_service.register(db, app_id, payload)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/application/{app_id}/agents/push", status_code=202)
async def push_messages(
    app_id: UUID,
    payload: PushMessages,
    agent: Agent = Depends(require_registered_agent),
    db: AsyncSession = Depends(get_session),
):
    """Push HTTP messages to the system for processing."""
    try:
        # Store messages in the database
        await agent_service.store_messages(db, agent.id, payload.messages)
        
        # Fan-out to queue for processing
        for msg in payload.messages:
            await queues.get("raw_http_msgs").publish(msg)
        
        return {"accepted": len(payload.messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))