from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, List, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from schemas.http import EnrichedRequest
from services.queue import queues
from database.models import AuthSession

from intruder import AuthzTester, HTTPClient
from httplib import HTTPRequest


class BaseAttackWorker(ABC):
    def __init__(self, queue_id: str, db_session: AsyncSession):
        self.queue_id = queue_id
        self.db = db_session
    
    @abstractmethod
    async def run(self):
        pass
    
    @abstractmethod
    async def ingest(
        self,
        request: HTTPRequest,
        username: Optional[str] = None,
        role: Optional[str] = None,
        session: Optional[AuthSession] = None,
    ):
        pass
    
    def _explode(self, enriched: EnrichedRequest) -> Dict[str, Any]:
        """Convert EnrichedRequest into kwargs for ingest method."""
        return {
            "request": enriched.request,
            "username": enriched.username,
            "role": enriched.role,
            # Session would be fetched separately if needed
            "session": None
        }


class AuthzAttacker(BaseAttackWorker):
    """
    Worker that analyzes requests for authorization vulnerabilities.
    
    It detects:
    1. URL patterns that suggest resource access that might be protected
    2. Differences between requests from different roles
    3. Sequential access patterns that might indicate IDOR vulnerabilities
    """
    
    def __init__(self, queue_id: str = "enriched_requests_authz", db_session: AsyncSession = None):
        super().__init__(queue_id, db_session)
        # Track URLs accessed by each role
        self.role_access_map: Dict[str, Set[str]] = {}
        # Track sequential ID access patterns
        self._authz_tester = AuthzTester(http_client=HTTPClient(timeout=5))
  
    async def run(self):
        sub_q = queues.get(self.queue_id).subscribe()
        while True:
            enr: EnrichedRequest = await sub_q.get()
            self.ingest(**self._explode(enr))

    def ingest(self,
               request: HTTPRequest,
               username: Optional[str] = None,
               role: Optional[str] = None,
               session: Optional[AuthSession] = None,
               ):
        # self._authz_tester.ingest(
        #     request=request,

        # )
        print("ATTACKER INGESTING")
        print(request)