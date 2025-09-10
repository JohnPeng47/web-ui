from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from cnc.services.queue import BroadcastChannel
from cnc.schemas.agent import (
    AgentOut,
    DiscoveryAgentCreate,
    ExploitAgentCreate,
    UploadAgentSteps,
    UploadPageData,
)
from cnc.database.session import get_session
from cnc.database.crud import get_engagement_by_agent_id, list_agents_for_engagement
from cnc.database.agent.crud import (
    get_agent_by_id as get_agent_by_id_service,
    register_discovery_agent as register_discovery_agent_service,
    register_exploit_agent as register_exploit_agent_service,
    append_discovery_agent_steps as append_discovery_agent_steps_service,
    update_page_data as update_page_data_service,
    get_agent_steps as get_agent_steps_service,
)
from cnc.database.agent.models import ExploitAgentStep
from cnc.database.crud import get_engagement
from cnc.pools.pool import StartDiscoveryRequest, StartExploitRequest

from common.constants import API_SERVER_HOST, API_SERVER_PORT, NUM_SCHEDULED_ACTIONS

from src.agent.discovery.pages import PageObservations
from src.agent.agent_client import AgentClient
from src.agent.detection.prompts import DetectAndSchedule
from src.llm_models import LLMHub


async def detect_vulnerabilities(
    payload: PageObservations,
    llm_model: LLMHub,
):
    detect = DetectAndSchedule()
    actions = await detect.ainvoke(
        llm_model,
        prompt_args={"pages": payload}
    )
    return actions

def make_agent_router(
    discovery_agent_queue: BroadcastChannel[StartDiscoveryRequest],
    exploit_agent_queue: BroadcastChannel[StartExploitRequest],
    llm_hub: LLMHub,
) -> APIRouter:
    """
    Create the agent router with injected dependencies.
    
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
                    client=AgentClient(
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
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/engagement/{engagement_id}/agents", response_model=List[AgentOut])
    async def list_engagement_agents(
        engagement_id: UUID, db: AsyncSession = Depends(get_session)
    ):
        try:
            engagement = await get_engagement(db, engagement_id)
            if not engagement:
                raise HTTPException(status_code=404, detail="Engagement not found")
            agents = await list_agents_for_engagement(db, engagement_id)
            return agents
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/agents/{agent_id}/steps")
    async def upload_agent_steps(
        agent_id: str,
        payload: UploadAgentSteps,
        db: AsyncSession = Depends(get_session),
    ):
        """Upload discovery agent steps to be appended to the agent."""
        try:
            # Ensure agent exists
            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            await append_discovery_agent_steps_service(db, agent_id, payload.steps)
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
        
    @router.post("/agents/{agent_id}/page-data")
    async def upload_page_data(
        agent_id: str,
        payload: UploadPageData,
        db: AsyncSession = Depends(get_session),
    ):
        """Upload a PageObservations payload and store as page_data."""
        try:
            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
                
            engagement = await get_engagement_by_agent_id(db, agent_id)
            if not engagement:
                raise Exception("Engagement not found")
            
            # detect and schedule actions for the exploit agent
            actions: List[StartExploitRequest] = await DetectAndSchedule().ainvoke(
                llm_hub.get("detection"),
                prompt_args={
                    "pages": PageObservations.from_json(payload.page_data),
                    "num_actions": NUM_SCHEDULED_ACTIONS
                }
            )
            actions = actions[:1]
            for action in actions:
                # register and queue up exploit agent
                create_exploit_config = ExploitAgentCreate(
                    vulnerability_title=action.vulnerability_title,
                    max_steps=12,
                    model_name="gpt-4o-mini",
                    agent_status="active",
                )
                await register_exploit_agent_service(db, engagement.id, create_exploit_config)
                await exploit_agent_queue.publish(
                    StartExploitRequest(
                        page_item=action.page_item, 
                        vulnerability_description=action.vulnerability_description, 
                        vulnerability_title=action.vulnerability_title,
                        max_steps=12,
                        client=AgentClient(
                            agent_id=agent.id,
                            api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                        )
                    )
                )
            await update_page_data_service(db, agent_id, payload.page_data)
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Methods for getting agent work progress / status
    @router.get("/agents/{agent_id}/page-data")
    async def get_agent_page_data(
        agent_id: str,
        db: AsyncSession = Depends(get_session),
    ):
        """Get page data for a discovery agent."""
        try:
            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            return {"page_data": agent.page_data}
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/agents/{agent_id}/steps", response_model=List[ExploitAgentStep])
    async def get_agent_steps(
        agent_id: str,
        db: AsyncSession = Depends(get_session),
    ):
        try:
            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            steps = await get_agent_steps_service(db, agent_id)
            return steps
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return router