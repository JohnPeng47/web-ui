from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from cnc.services.queue import BroadcastChannel
from cnc.schemas.agent import (
    AgentOut,
    DiscoveryAgentCreate,
    UploadAgentSteps,
    UploadPageData,
)
from cnc.database.session import get_session
from cnc.database.agent.crud import (
    register_discovery_agent as register_discovery_agent_service,
    get_discovery_agent as get_discovery_agent_service,
    append_discovery_agent_steps as append_discovery_agent_steps_service,
    update_page_data as update_page_data_service,
)
from cnc.database.crud import get_engagement
from cnc.pools.pool import StartDiscoveryRequest

from common.constants import API_SERVER_HOST, API_SERVER_PORT

from src.agent.page_client import PageUpdateClient

def make_agent_router(discovery_agent_queue: BroadcastChannel[StartDiscoveryRequest]) -> APIRouter:
    """
    Create the agent router with injected   dependencies.
    
    Args:
        raw_channel: Channel for publishing raw HTTP messages
        
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()
    
    # TODO: test this format of request and se how well cascades
    # No header-based agent verification in this simplified route set
    @router.post("/engagement/{engagement_id}/agents/discovery/register", response_model=AgentOut)
    async def register_discovery_agent(
        engagement_id: UUID, payload: DiscoveryAgentCreate, db: AsyncSession = Depends(get_session)
    ):
        """Register a new discovery agent for an engagement."""
        try:
            agent = await register_discovery_agent_service(db, engagement_id, payload)
            engagement = await get_engagement(db, engagement_id)
            if not engagement:
                raise HTTPException(status_code=404, detail="Engagement not found")

            await discovery_agent_queue.publish(
                StartDiscoveryRequest(
                    start_urls=[engagement.base_url], 
                    scopes=engagement.scopes_data, 
                    init_task=None,
                    client=PageUpdateClient(
                        agent_id=agent.id,
                        # TODO: FOR testing only
                        api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                    )
                )
            )
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
    
    @router.post("/agents/{agent_id}/page-data", response_model=AgentOut)
    async def update_page_data(
        agent_id: int,
        payload: UploadPageData,
        db: AsyncSession = Depends(get_session),
    ):
        """Upload a PageObservations payload and store as page_data."""
        try:
            agent = await get_discovery_agent_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            agent = await update_page_data_service(db, agent_id, payload.page_data)
            return agent
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/agents/{agent_id}/page-data")
    async def get_agent_page_data(
        agent_id: int,
        db: AsyncSession = Depends(get_session),
    ):
        """Get page data for a discovery agent."""
        try:
            agent = await get_discovery_agent_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            return {"page_data": agent.page_data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return router