from abc import ABC, abstractmethod
import asyncio
from contextlib import suppress
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from cnc.schemas.http import EnrichedRequest, EnrichAuthNZMessage
from cnc.services.queue import BroadcastChannel

from httplib import HTTPMessage, ResourceLocator
from johnllm import LMP, LLMModel
from src.llm import RequestResources, EXTRACT_REQUESTS_PROMPT

from logger import init_file_logger

log = init_file_logger(__name__)

class ExtractResources(LMP):
    prompt = EXTRACT_REQUESTS_PROMPT
    response_format = RequestResources

class BaseRequestEnrichmentWorker(ABC):
    """Base class for request enrichment workers"""
    
    @abstractmethod
    async def run(self):
        """Run the worker processing loop"""
        pass
    
    @abstractmethod
    async def _enrich(self, message: HTTPMessage) -> EnrichedRequest:
        """Enrich a raw HTTP message with additional metadata"""
        pass

class RequestEnrichmentWorker(BaseRequestEnrichmentWorker):
    """
    Worker that processes raw HTTP messages and enriches them with 
    metadata like authentication info, session data, etc.
    """
    def __init__(
        self,
        *,
        inbound: BroadcastChannel[EnrichAuthNZMessage],
        outbound: BroadcastChannel[EnrichedRequest],
        db_session: Optional[AsyncSession] = None
    ):
        print("Initlaiizing enrichment inbound broadcast: ", inbound.id)

        self._sub_q = inbound.subscribe()
        self._outbound = outbound
        self.db = db_session
        self.llm = LLMModel()
    
    # TODO: blocking async calls
    async def run(self) -> None:
        """
        Listen for raw messages forever.  Each message is handed off to its own
        asyncio.Task so the loop can keep listening immediately.
        """
        self._tasks: set[asyncio.Task] = set()
        while True:
            log.info("Waiting for raw HTTP message…")
            raw_msg = await self._sub_q.get()

            # Fire‑and‑forget, but keep a reference so we can introspect / cancel.
            task = asyncio.create_task(self._handle_message(raw_msg))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _handle_message(self, raw_msg) -> None:
        """
        Worker for a *single* HTTPMessage.  Runs in its own task.
        All exceptions are caught so they don’t kill the whole process.
        """
        try:
            enr_msg = await self._enrich(
                raw_msg.http_msg,
                raw_msg.username,
                role=raw_msg.role,
            )
            await self._outbound.publish(enr_msg)
        except asyncio.CancelledError:
            # Task was cancelled during shutdown; just propagate.
            raise
        except Exception as exc:
            log.exception("Enrichment task failed: %s", exc)
            # Decide: retry? drop? send to DLQ? For now we just log & swallow.

    async def shutdown(self) -> None:
        """
        Call this from your application’s shutdown hook to allow tasks to finish
        gracefully.
        """
        for task in self._tasks:
            task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _enrich(self, 
                      message: HTTPMessage,
                      username: str,
                      role: str | None = None) -> EnrichedRequest:
        """
        Enriches an HTTP message by extracting authentication/session information.
        
        This implementation looks for:
        1. Session cookies (common session identifiers)
        2. Authorization headers (Bearer tokens, Basic auth)
        3. Form-based auth in POST data (username/password fields)
        """
        request = message.request
        resources = ExtractResources().invoke(
            model=self.llm,
            model_name="gpt-4.1",
            prompt_args={"request": message.request.to_str()}
        )
        enriched = EnrichedRequest(
            request=request,
            username=username,
            role=role,
            session=request.auth_session,
            resource_locators=[
                ResourceLocator(
                    id=r.id,
                    request_part=r.request_part,
                    type_name=r.type.name
                ) for r in resources.resources
            ],
        ) 
        log.info(f"Enriched resources: {resources.resources}")
        print(f"Enriched resources: {resources.resources}")
        return enriched