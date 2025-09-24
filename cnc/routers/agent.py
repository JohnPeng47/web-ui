from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Any, cast, Literal

from src.llm_models import BaseChatModel
from cnc.services.detection import DetectionScheduler
from cnc.services.queue import BroadcastChannel
from cnc.schemas.agent import (
    AgentOut,
    DiscoveryAgentCreate,
    ExploitAgentCreate,
    UploadAgentSteps,
    UploadPageData,
    AgentStatus,
    AgentApproveBinary
)
from cnc.database.session import get_session
from cnc.database.crud import (
    get_engagement_by_agent_id, 
    list_agents_for_engagement,
    get_engagement
)
from cnc.database.agent.crud import (
    get_agent_by_id as get_agent_by_id_service,
    register_discovery_agent as register_discovery_agent_service,
    register_exploit_agent as register_exploit_agent_service,
    append_discovery_agent_steps as append_discovery_agent_steps_service,
    get_agent_steps as get_agent_steps_service,
    set_exploit_approval_payload as set_exploit_approval_payload_service,
    clear_exploit_approval_payload as clear_exploit_approval_payload_service,
    update_agent_status as update_agent_status_service,
)
from cnc.database.agent.models import ExploitAgentStep
from cnc.pools.pool import StartDiscoveryRequest, StartExploitRequest
from common.constants import (
    API_SERVER_HOST, 
    API_SERVER_PORT, 
    NUM_SCHEDULED_ACTIONS,
    MAX_DISCOVERY_AGENT_STEPS,
    MAX_DISCOVERY_PAGE_STEPS,
    MAX_EXPLOIT_AGENT_STEPS,
    SERVER_LOG_DIR,
    MANUAL_APPROVAL_EXPLOIT_AGENT,
    DISCOVERY_MODEL_CONFIG,
    EXPLOIT_MODEL_CONFIG,
)

from src.agent.discovery.pages import PageObservations, Page
from httplib import HTTPMessage
from src.agent.base import AgentType
from src.agent.agent_client import AgentClient
from src.llm_models import LLMHub
from cnc.services.engagement import merge_page_data as merge_page_data_service

from logger import get_server_logger, get_agent_loggers, get_server_log_factory

log = get_server_logger()

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
        agent = await register_discovery_agent_service(db, engagement_id, MAX_DISCOVERY_AGENT_STEPS, AgentType.DISCOVERY)
        engagement = await get_engagement(db, engagement_id)            
        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")

        # Engagement-scoped server logger and agent loggers
        log_factory = get_server_log_factory(base_dir=SERVER_LOG_DIR)
        engagement_logger = log_factory.ensure_server_logger(str(engagement.id))
        agent_logger, full_logger = log_factory.get_discovery_agent_loggers(str(engagement.id))

        start_urls = payload.start_urls if payload.start_urls else [engagement.base_url]
        engagement_logger.info(f"Starting discovery agent {agent.id} with {start_urls}")
        try:
            await discovery_agent_queue.publish(
                StartDiscoveryRequest(
                    start_urls=payload.start_urls if payload.start_urls else [engagement.base_url], 
                    max_steps=MAX_DISCOVERY_AGENT_STEPS,
                    max_page_steps=MAX_DISCOVERY_PAGE_STEPS,
                    model_config=DISCOVERY_MODEL_CONFIG,
                    scopes=engagement.scopes_data, 
                    init_task=None,
                    client=AgentClient(
                        agent_id=agent.id,
                        api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                    ),  
                    agent_log=agent_logger,
                    full_log=full_logger,
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
            log_factory = get_server_log_factory(base_dir=SERVER_LOG_DIR)
            engagement = await get_engagement_by_agent_id(db, agent_id)
            if not engagement:
                raise Exception("Engagement not found")

            log = log_factory.ensure_server_logger(str(engagement.id))
            log.info(f"Uploading agent steps for {agent_id}")
            log.info(f"Payload: {payload}")

            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            # we are actually only just receiving a single step per update
            agent_finished = payload.max_steps == payload.steps[0].step_num + 1 and payload.found_exploit
            await append_discovery_agent_steps_service(db, agent_id, payload.steps, agent_finished, log)
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
        engagement = await get_engagement_by_agent_id(db, agent_id)
        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")
            
        agent = await get_agent_by_id_service(db, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        log_factory = get_server_log_factory(base_dir=SERVER_LOG_DIR)
        log = log_factory.ensure_server_logger(str(engagement.id))
        detection_scheduler = DetectionScheduler()

        trigger_detection = False
        max_steps = payload.max_steps
        max_page_steps = payload.max_page_steps
        steps = payload.steps
        page_steps = payload.page_steps

        try:
            # NOTE: not actually merging rn just overwriting
            log.info(f"Merging page data for {agent_id}")
            await merge_page_data_service(db, engagement.id, payload.page_data, merge=False)

            log.info(f"Progress: {steps}/{max_steps} | Page steps: {page_steps}/{max_page_steps}")

            actions = await detection_scheduler.generate_actions(
                cast(BaseChatModel, llm_hub.get("detection")),
                payload.to_page_observations(),
                page_steps,
                max_page_steps,
                NUM_SCHEDULED_ACTIONS
            )
            if actions:
                log.info(f"Triggering detection for: {agent_id}")
                log.info("Page steps received; evaluating detection trigger")
                actions = actions[:1]
                for action in actions:
                    log.info(f"Scheduling exploit agent for {action.vulnerability_title}")
                    # register and conditionally queue exploit agent
                    exploit_agent = await register_exploit_agent_service(db, engagement.id, MAX_EXPLOIT_AGENT_STEPS, AgentType.EXPLOIT, action.vulnerability_title)
                    agent_logger, full_logger = log_factory.get_exploit_agent_loggers(str(engagement.id))

                    start_request = StartExploitRequest(
                        page_item=action.page_item,
                        vulnerability_description=action.vulnerability_description,
                        vulnerability_title=action.vulnerability_title,
                        max_steps=MAX_EXPLOIT_AGENT_STEPS,
                        model_config=EXPLOIT_MODEL_CONFIG,
                        client=AgentClient(
                            agent_id=exploit_agent.id,
                            api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                        ),
                        agent_log=agent_logger,
                        full_log=full_logger,
                    )
                    if MANUAL_APPROVAL_EXPLOIT_AGENT:
                        # store minimal JSON-safe payload for approval
                        page_item = getattr(action, "page_item", None)
                        if page_item is not None:
                            page_item_json = page_item.model_dump(mode="json")  # type: ignore[attr-defined]
                        else:
                            page_item_json = {}
                        approval_payload = {
                            "page_item": page_item_json,
                            "vulnerability_description": action.vulnerability_description,
                            "vulnerability_title": action.vulnerability_title,
                            "max_steps": MAX_EXPLOIT_AGENT_STEPS,
                        }
                        await set_exploit_approval_payload_service(db, exploit_agent.id, approval_payload)
                        await update_agent_status_service(db, exploit_agent.id, AgentStatus.PENDING_APPROVAL)
                    else:
                        await exploit_agent_queue.publish(start_request)
                
            return {
                "page_skip": trigger_detection
            }
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/agents/{engagement_id}/page-data")
    async def get_agent_page_data(
        engagement_id: UUID,
        db: AsyncSession = Depends(get_session),
    ):
        """Get page data for a discovery agent."""
        try:
            engagement = await get_engagement(db, engagement_id)
            if not engagement:
                raise Exception("Engagement not found")
            return {"page_data": engagement.page_data or []}
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

    @router.post("/agents/{agent_id}/approval")
    async def approve_or_deny_agent(
        agent_id: str,
        approval_data: AgentApproveBinary,
        db: AsyncSession = Depends(get_session),
    ):
        try:
            agent = await get_agent_by_id_service(db, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            if agent.agent_status != AgentStatus.PENDING_APPROVAL:
                # Idempotent: if already processed, return current state
                return {"agent_id": agent_id, "status": agent.agent_status}

            if approval_data.approve_data == False:
                agent = await update_agent_status_service(db, agent_id, AgentStatus.CANCELLED)
                await clear_exploit_approval_payload_service(db, agent_id)
                return {"agent_id": agent_id, "status": agent.agent_status}

            # Approve flow: publish stored request, transition to RUNNING
            payload = getattr(agent, "approval_payload_data", None)
            if not payload:
                raise HTTPException(status_code=409, detail="No approval payload stored for this agent")

            # Rehydrate StartExploitRequest and attach runtime-only fields
            try:
                # get engagement and loggers
                engagement = await get_engagement_by_agent_id(db, agent_id)
                if not engagement:
                    raise Exception("Engagement not found for agent")
                log_factory = get_server_log_factory(base_dir=SERVER_LOG_DIR)
                agent_logger, full_logger = log_factory.get_exploit_agent_loggers(str(engagement.id))

                start_request = StartExploitRequest(
                    page_item=HTTPMessage.from_json(payload.get("page_item", {})),
                    vulnerability_description=payload.get("vulnerability_description", ""),
                    vulnerability_title=payload.get("vulnerability_title", ""),
                    max_steps=payload.get("max_steps", MAX_EXPLOIT_AGENT_STEPS),
                    model_config=EXPLOIT_MODEL_CONFIG,
                    client=AgentClient(
                        agent_id=agent_id,
                        api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                    ),
                    agent_log=agent_logger,
                    full_log=full_logger,
                )
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to reconstruct approval payload")

            await exploit_agent_queue.publish(start_request)
            await update_agent_status_service(db, agent_id, AgentStatus.RUNNING)
            await clear_exploit_approval_payload_service(db, agent_id)
            return {"agent_id": agent_id, "status": AgentStatus.RUNNING}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return router