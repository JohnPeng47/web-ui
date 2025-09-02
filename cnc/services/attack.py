from abc import ABC, abstractmethod
from typing import Sequence, Dict, Any, Optional, Set, List, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from uuid import UUID
from pydantic import BaseModel
import asyncio

from cnc.schemas.http import EnrichedRequest
from cnc.schemas.application import Finding
from cnc.services.queue import BroadcastChannel
from cnc.database.models import AuthSession as DBAuthSession
from httplib import HTTPRequest, HTTPRequestData
from logger import get_server_logger


class AttackResult(BaseModel):
    success: bool
    result: Optional[str]
    description: Optional[str]

# TODO: check during ingestion later that result is set
class Attack(BaseModel):
    type: str
    description: str
    attack_info: BaseModel
    sub_type: Optional[str] = None
    result: Optional[AttackResult] = None

class FindingsStore(ABC):
    @abstractmethod
    def append(self, finding: Union[Attack, str]):
        pass

log = get_server_logger()

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
    
    def append(self, finding: Union[Attack, str]):
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