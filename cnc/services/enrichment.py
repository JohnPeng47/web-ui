from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from dataclasses import dataclass
from schemas.http import EnrichedRequest, EnrichAuthNZMessage
from cnc.services.queue import BroadcastChannel

from httplib import HTTPMessage
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
        inbound: BroadcastChannel[HTTPMessage],
        outbound: BroadcastChannel[EnrichedRequest],
        db_session: Optional[AsyncSession] = None
    ):
        print("Initlaiizing enrichment inbound broadcast: ", inbound.id)

        self._sub_q = inbound.subscribe()
        self._outbound = outbound
        self.db = db_session
        self.llm = LLMModel()
    
    # TODO: blocking async calls
    async def run(self):
        """Process incoming HTTP messages and publish enriched versions"""
        while True:
            log.info("Waiting for raw HTTP message...")

            raw_msg = await self._sub_q.get()
            enr_msg = await self._enrich(raw_msg)
            await self._outbound.publish(enr_msg)

    async def _enrich(self, message: HTTPMessage) -> EnrichedRequest:
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
            model_name="gpt-4o",
            prompt_args={"request": message.request.to_str()}
        )
        enriched = EnrichedRequest(request=request)        
        return enriched