from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from cnc.schemas.agent import (
    AgentOut,
    DiscoveryAgentCreate,
    UploadAgentSteps,
)
from cnc.database.session import get_session
from cnc.database.agent.crud import (
    register_discovery_agent as register_discovery_agent_service,
    get_discovery_agent as get_discovery_agent_service,
    append_discovery_agent_steps as append_discovery_agent_steps_service,
)

def make_agent_router() -> APIRouter:
    """
    Create the agent router with injected dependencies.
    
    Args:
        raw_channel: Channel for publishing raw HTTP messages
        
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()
    # print("Initializing agent router")
    
    # TODO: test this format of request and see how well cascades
    # No header-based agent verification in this simplified route set
    
    @router.post("/engagement/{engagement_id}/agents/discovery/register", response_model=AgentOut)
    async def register_discovery_agent(
        engagement_id: UUID, payload: DiscoveryAgentCreate, db: AsyncSession = Depends(get_session)
    ):
        """Register a new discovery agent for an engagement."""
        try:
            agent = await register_discovery_agent_service(db, engagement_id, payload)
            return agent
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @router.post("/agents/{agent_id}/steps", response_model=AgentOut)
    async def upload_agent_steps(
        agent_id: int,
        payload: UploadAgentSteps,
        db: AsyncSession = Depends(get_session),
    ):
        """Upload discovery agent steps to be appended to the agent."""
        try:
            # Ensure agent exists
            agent = await get_discovery_agent_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            agent = await append_discovery_agent_steps_service(db, agent_id, payload.steps)
            return agent
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return router