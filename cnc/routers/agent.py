from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from cnc.schemas.agent import AgentRegister, AgentOut, PushMessages
from cnc.database.session import get_session
from cnc.database.models import Agent

from cnc.services.agent import crud as agent_service
from cnc.services.queue import BroadcastChannel
from cnc.schemas.http import EnrichAuthNZMessage

def make_agent_router(raw_channel: BroadcastChannel[EnrichAuthNZMessage]) -> APIRouter:
    """
    Create the agent router with injected dependencies.
    
    Args:
        raw_channel: Channel for publishing raw HTTP messages
        
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()
    print("Initializing agent router with raw channel: ", raw_channel.id)
    
    # TODO: test this format of request and see how well cascades
    async def require_registered_agent(
        app_id: UUID,
        x_username: str = Header(None),
        x_role: str = Header(None),
        db: AsyncSession = Depends(get_session)
    ) -> Agent:
        """Dependency that ensures the agent is registered for the application."""
        if not x_username or not x_role:
            raise HTTPException(
                status_code=400,
                detail="Both X-Username and X-Role headers are required"
            )
            
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
            # Verify agent exists
            agent = await agent_service.get_agent(db, payload.agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            
            # Fan-out to channel for processing
            for msg in payload.http_msgs:
                print(f"[Route] received {msg.request.url}")

                # Publish directly to the injected channel
                # await raw_channel.publish(
                #     EnrichAuthNZMessage(
                #         http_msg=msg, 
                #         username=agent.user_name, 
                #         role=agent.role
                #     )
                # )
            
            # for action in payload.browser_actions:
            #     print(f"Received action: {action}")

            return {"accepted": len(payload.http_msgs)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return router