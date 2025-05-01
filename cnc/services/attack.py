from abc import ABC, abstractmethod
from typing import Sequence, Dict, Any, Optional, Set, List, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from uuid import UUID
import asyncio

from schemas.http import EnrichedRequest
from schemas.application import Finding
from cnc.services.queue import BroadcastChannel
from database.models import AuthSession as DBAuthSession

from intruder import (
    AuthzTester, 
    HTTPClient, 
    FindingsStore, 
    TestResult,
    ResourceLocator, 
    RequestPart,
    AuthSession as IntruderAuthSession
)
from httplib import HTTPRequest, HTTPRequestData
from logger import init_file_logger

log = init_file_logger(__name__)

class BaseAttackWorker(ABC):
    """Base class for attack workers that analyze requests for vulnerabilities"""
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
    
    @abstractmethod
    async def run(self):
        """Run the worker processing loop"""
        pass
    
    @abstractmethod
    async def ingest(
        self,
        request: HTTPRequest,
        username: Optional[str] = None,
        role: Optional[str] = None,
        session: Optional[DBAuthSession] = None
    ):
        """Process a single request for attack analysis"""
        pass

class ApplicationFindingsStore(FindingsStore):
    """Store security findings in the Applications model via API."""
    
    def __init__(self, app_id: UUID, base_url: str = "http://localhost:8000"):
        self.app_id = app_id
        self.base_url = base_url
    
    def append(self, finding: Union[TestResult, str]):
        """Add a finding by sending it directly to the API."""
        if isinstance(finding, str):
            # Skip string findings for now, could log them separately
            return
        
        # Convert TestResult to Finding schema
        finding_data = Finding(
            user=finding.user,
            resource_id=finding.resource_id,
            action=finding.action
        )
        
        # Create and run the task to send the finding
        asyncio.create_task(self._send_finding(finding_data))
    
    async def _send_finding(self, finding: Finding):
        """Send a finding to the API."""
        try:
            # Send to the API
            url = f"{self.base_url}/application/{self.app_id}/findings"
            payload = {"finding": finding.dict()}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    log.info(f"Error sending finding: {response.text}")
        
        except Exception as e:
            log.info(f"Error processing finding: {e}")


class AuthzAttacker(BaseAttackWorker):
    """
    Worker that analyzes requests for authorization vulnerabilities.
    
    It detects:
    1. URL patterns that suggest resource access that might be protected
    2. Differences between requests from different roles
    3. Sequential access patterns that might indicate IDOR vulnerabilities
    """
    
    def __init__(self, 
                 inbound: BroadcastChannel[EnrichedRequest],
                 db_session: Optional[AsyncSession] = None,
                 app_id: Optional[UUID] = None):
        super().__init__(db_session)
        # Subscribe to inbound channel
        self._sub_q = inbound.subscribe()
        
        # Track URLs accessed by each role
        self.role_access_map: Dict[str, Set[str]] = {}
        
        # Set up findings store if app_id is provided
        findings_store = None
        if app_id:
            findings_store = ApplicationFindingsStore(app_id)
        
        # Initialize AuthzTester with findings store
        self._authz_tester = AuthzTester(
            http_client=HTTPClient(timeout=5),
            findings_log=findings_store
        )
  
    async def run(self):
        """Process incoming enriched requests for authz vulnerabilities"""
        while True:
            enr: EnrichedRequest = await self._sub_q.get()
            await self.ingest(**self._explode(enr))
    
    def _explode(self, enriched: EnrichedRequest) -> Dict[str, Any]:
        """Convert EnrichedRequest into kwargs for ingest method."""
        return {
            "request": enriched.request,
            "username": enriched.username,
            "role": enriched.role,
            # Session would be fetched separately if needed
            "session": None
        }

    def ingest(
        self,
        *,
        username: str,
        request: HTTPRequestData,
        resource_locators: Sequence[ResourceLocator]
    ) -> None:
        """Process a single request for authorization vulnerabilities"""        
        self._authz_tester.ingest(
            username=username,
            request=request,
            resource_locators=resource_locators
        )