from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Any, cast, Literal, Optional

from src.llm_models import BaseChatModel
from cnc.services.detection import DetectionScheduler, StartExploitRequestData
from cnc.services.queue import BroadcastChannel
from cnc.schemas.agent import (
    AgentOut,
    DiscoveryAgentCreate,
    ExploitAgentCreate,
    UploadAgentSteps,
    UploadPageData,
    AgentStatus,
    AgentApproveBinary,
    ExploitAgentObservation
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
    update_exploit_approval_data,
    update_exploit_agent_status as update_agent_status_service,
)
from cnc.database.agent.models import ExploitAgentStep, ExploitAgentModel
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

from src.agent.exploit.observations import GatherObservations
from src.agent.discovery.pages import PageObservations, Page
from src.agent.base import AgentType
from src.agent.agent_client import AgentClient
from src.llm_models import LLMHub
from cnc.services.engagement import merge_page_data as merge_page_data_service

from logging import getLogger
from logger import get_or_init_log_factory, SERVER_LOGGER_NAME

server_log = getLogger(SERVER_LOGGER_NAME)

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
        agent = await register_discovery_agent_service(db, engagement_id, MAX_DISCOVERY_AGENT_STEPS)
        engagement = await get_engagement(db, engagement_id)            
        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")

        # Engagement-scoped server logger and agent loggers
        log_factory = get_or_init_log_factory(base_dir=SERVER_LOG_DIR)
        agent_logger, full_logger = log_factory.get_discovery_agent_loggers()
        server_log.info(f"Starting discovery agent {agent.id} with for {engagement.id}")
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

    @router.post("/engagement/{engagement_id}/agents/exploit/register")
    async def register_exploit_agent(
        engagement_id: UUID, db: AsyncSession = Depends(get_session)
    ):
        """Register a new exploit agent for an engagement."""
        engagement = await get_engagement(db, engagement_id)
        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")
                    
        log_factory = get_or_init_log_factory(base_dir=SERVER_LOG_DIR)
        agent_logger, full_logger = log_factory.get_exploit_agent_loggers()
        detection_scheduler = DetectionScheduler()
        try:
            actions = await detection_scheduler.generate_actions_no_trigger(
                cast(BaseChatModel, llm_hub.get("detection")),
                PageObservations.from_json(engagement.page_data),
                NUM_SCHEDULED_ACTIONS
            )
            if actions:
                for action in actions:
                    server_log.info(f"Scheduling exploit agent for {action.vulnerability_title}")
                    server_log.info(f"-> {action.vulnerability_description}")
                    agent_status = AgentStatus.PENDING_APPROVAL if MANUAL_APPROVAL_EXPLOIT_AGENT else AgentStatus.RUNNING
                    exploit_agent = await register_exploit_agent_service(
                        db, 
                        engagement.id, 
                        MAX_EXPLOIT_AGENT_STEPS, 
                        action.vulnerability_title, 
                        action.vulnerability_description,
                        await action.to_dict(),
                        agent_status
                    )
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
                    # TODO: this logic should be placed inside DetectionScheduler
                    if not MANUAL_APPROVAL_EXPLOIT_AGENT:
                        await exploit_agent_queue.publish(start_request)
                
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
            agents_out = []
            for agent in agents:
                if isinstance(agent, ExploitAgentModel):
                    agents_out.append(AgentOut(
                        id=agent.id,
                        agent_status=agent.agent_status,
                        agent_type=AgentType(agent.agent_type),
                        agent_name=agent.vulnerability_title,
                        data={
                            "vulnerability_description": agent.vulnerability_description,
                            "complete_data": agent.complete_data if agent.complete_data else {}
                        }
                    )) 
            return agents_out
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
        engagement = await get_engagement_by_agent_id(db, agent_id)
        if not engagement:
            raise Exception("Engagement not found")
        agent = await get_agent_by_id_service(db, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        try:
            server_log.info(f"Uploading agent steps for {agent_id}")
            server_log.info(f"Payload: {payload}")

            # TODO: add agent result summary here
            res = GatherObservations().invoke(
                model=llm_hub.get("observations"), 
                prompt_args={"agent_trace": "\n".join([f"Step {i}: {step.reflection}" 
                    for i, step in enumerate(payload.steps, start=1)])}
            )
            await append_discovery_agent_steps_service(
                db, 
                agent_id, 
                payload.steps, 
                payload.completed, 
                finished_data=[obs.model_dump() for obs in res.observations]
            )
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

        log_factory = get_or_init_log_factory(base_dir=SERVER_LOG_DIR)
        detection_scheduler = DetectionScheduler()

        trigger_detection = False
        max_steps = payload.max_steps
        max_page_steps = payload.max_page_steps
        steps = payload.steps
        page_steps = payload.page_steps

        if page_steps >= max_page_steps:
            trigger_detection = True

        try:
            # NOTE: not actually merging rn just overwriting
            server_log.info(f"Merging page data for {agent_id}")
            await merge_page_data_service(db, engagement.id, payload.page_data, merge=False)

            server_log.info(f"Progress: {steps}/{max_steps} | Page steps: {page_steps}/{max_page_steps}")

            # actions = await detection_scheduler.generate_actions(
            #     cast(BaseChatModel, llm_hub.get("detection")),
            #     payload.to_page_observations(),
            #     page_steps,
            #     max_page_steps,
            #     NUM_SCHEDULED_ACTIONS
            # )
            # if actions:
            #     log.info(f"Triggering detection for: {agent_id}")
            #     log.info("Page steps received; evaluating detection trigger")
            #     actions = actions[:1]
            #     for action in actions:
            #         log.info(f"Scheduling exploit agent for {action.vulnerability_title}")
            #         # register and conditionally queue exploit agent
            #         exploit_agent = await register_exploit_agent_service(db, engagement.id, MAX_EXPLOIT_AGENT_STEPS, AgentType.EXPLOIT, action.vulnerability_title)
            #         agent_logger, full_logger = log_factory.get_exploit_agent_loggers()

            #         start_request = StartExploitRequest(
            #             page_item=action.page_item,
            #             vulnerability_description=action.vulnerability_description,
            #             vulnerability_title=action.vulnerability_title,
            #             max_steps=MAX_EXPLOIT_AGENT_STEPS,
            #             model_config=EXPLOIT_MODEL_CONFIG,
            #             client=AgentClient(
            #                 agent_id=exploit_agent.id,
            #                 api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
            #             ),
            #             agent_log=agent_logger,
            #             full_log=full_logger,
            #         )
            #         if MANUAL_APPROVAL_EXPLOIT_AGENT:
            #             # store minimal JSON-safe payload for approval
            #             page_item = getattr(action, "page_item", None)
            #             if page_item is not None:
            #                 page_item_json = page_item.model_dump(mode="json")  # type: ignore[attr-defined]
            #             else:
            #                 page_item_json = {}
            #             approval_payload = {
            #                 "page_item": page_item_json,
            #                 "vulnerability_description": action.vulnerability_description,
            #                 "vulnerability_title": action.vulnerability_title,
            #                 "max_steps": MAX_EXPLOIT_AGENT_STEPS,
            #             }
            #             await set_exploit_approval_payload_service(db, exploit_agent.id, approval_payload)
            #             await update_agent_status_service(db, exploit_agent.id, AgentStatus.PENDING_APPROVAL)
            #         else:
            #             await exploit_agent_queue.publish(start_request)
                
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
        log_factory = get_or_init_log_factory(base_dir=SERVER_LOG_DIR)
        agent_logger, full_logger = log_factory.get_exploit_agent_loggers(no_console=True)

        agent: Optional[ExploitAgentModel] = await get_agent_by_id_service(db, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        try:
            if agent.agent_status != AgentStatus.PENDING_APPROVAL:
                # Idempotent: if already processed, return current state
                return {"agent_id": agent_id, "status": agent.agent_status}

            if approval_data.approve_data == False:
                await update_agent_status_service(db, agent_id, AgentStatus.CANCELLED)
                return {"agent_id": agent_id, "status": agent.agent_status}

            action = StartExploitRequestData.from_dict(agent.start_exploit_request_data)
            start_request = StartExploitRequest(
                page_item=action.page_item,
                vulnerability_description=action.vulnerability_description,
                vulnerability_title=action.vulnerability_title,
                max_steps=MAX_EXPLOIT_AGENT_STEPS,
                model_config=EXPLOIT_MODEL_CONFIG,
                client=AgentClient(
                    agent_id=agent_id,
                    api_url=f"http://127.0.0.1:{API_SERVER_PORT}",
                ),
                agent_log=agent_logger,
                full_log=full_logger,
            )
            
            await exploit_agent_queue.publish(start_request)
            await update_exploit_approval_data(db, agent_id, approval_data.model_dump())
            await update_agent_status_service(db, agent_id, AgentStatus.RUNNING)
            return {"agent_id": agent_id, "status": AgentStatus.RUNNING}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"Exception: {e}")
            print(f"Stacktrace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return router