from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import Enum
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, Set, List, Tuple, Type, Iterable, Protocol, Sequence, Union
from uuid import UUID
import httpx
import json
import logging
import xml.etree.ElementTree as ET

from cnc.services.attack import (
    BaseAttackWorker, 
    ApplicationFindingsStore
)
from cnc.services.queue import BroadcastChannel
from httplib import HTTPRequest, HTTPRequestData, AuthSession, ResourceLocator
from playwright.sync_api import Request
from cnc.schemas.http import EnrichedRequest
from src.llm import RequestResources, Resource, ResourceType, RequestPart

from .intruder import AuthzTester, HTTPClient

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
        # NOTE:
        # rename findings to attacks 
        # enable this afterwards, should keep record of attacks
        
        # if app_id:
        #     findings_store = ApplicationFindingsStore(app_id)
        
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
            "request": enriched.request.data,
            "username": enriched.username,
            "role": enriched.role,
            # Session would be fetched separately if needed
            "resource_locators": enriched.resource_locators,
            "session": enriched.session
        }

    # TODO: tmrw -> should work..
    async def ingest(
        self,
        *,
        username: str,
        role: str,
        request: HTTPRequestData,
        resource_locators: Sequence[ResourceLocator],
        session: Optional[AuthSession] = None
    ) -> None:
        """Process a single request for authorization vulnerabilities"""        
        self._authz_tester.ingest(
            username=username,
            role=role,
            request=request,
            resource_locators=resource_locators,
            session=session
        )