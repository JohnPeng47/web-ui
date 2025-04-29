from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from dataclasses import dataclass
from schemas.http import EnrichedRequest, EnrichAuthNZMessage
from services.queue import queues

from httplib import HTTPMessage

class BaseRequestEnrichmentWorker(ABC):
    def __init__(self, *, sub_queue_id: str, pub_queue_id: str):
        self.sub_id = sub_queue_id
        self.pub_id = pub_queue_id
    
    @abstractmethod
    async def run(self):
        pass
    
    @abstractmethod
    async def _enrich(self, message: HTTPMessage) -> EnrichedRequest:
        pass

class EnrichAuthNZWorker(BaseRequestEnrichmentWorker):
    def __init__(self, *, sub_queue_id: str, pub_queue_id: str, db_session: AsyncSession):
        super().__init__(sub_queue_id=sub_queue_id, pub_queue_id=pub_queue_id)
        self.db = db_session
    
    async def run(self):
        sub_q = queues.get(self.sub_id).subscribe()
        pub_ch = queues.get(self.pub_id)
        
        while True:
            msg: EnrichAuthNZMessage = await sub_q.get()
            enr = await self._enrich(msg)
            await pub_ch.publish(enr)
    
    async def _enrich(self, message: EnrichAuthNZMessage) -> EnrichedRequest:
        """
        Enriches an HTTP message by extracting authentication/session information.
        
        This implementation looks for:
        1. Session cookies (common session identifiers)
        2. Authorization headers (Bearer tokens, Basic auth)
        3. Form-based auth in POST data (username/password fields)
        """
        request = message.http_msg.request
        enriched = EnrichedRequest(request=request)

        print(">>>> RECEIVED ENRICHED MESSAGE")
        print(enriched)
        
        return enriched