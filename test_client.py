from httpx import AsyncClient
from typing import Dict, List, Optional
from src.agent.client import AgentClient
from pydantic import BaseModel

from cnc.tests.challenges.vulnerability import Vulnerability

from logging import getLogger
logger = getLogger(__name__)

class VulnAppClient(AgentClient):
    def __init__(self, 
                 vuln_client: AsyncClient = None,
                 targeted_vulns: List[Vulnerability] = [],
                 all_vulns: List[Vulnerability] = [],
                 **kwargs):
        super().__init__(**kwargs)
        
        self._vuln_client = vuln_client
        self._all_vulns: Dict[int, Vulnerability] = {vuln.id: vuln for vuln in all_vulns}
        self._targeted_vulns = targeted_vulns

        non_exist = self._check_target_vulns()
        if non_exist:
            raise ValueError(f"Targeted vulns do not exist: {non_exist}" )
        
        logger.info(f"Starting test for targets: {[vuln.id for vuln in self._targeted_vulns]}")

    def _check_target_vulns(self):
        return [
            vuln.id for vuln in self._targeted_vulns
            if vuln.id not in self._all_vulns
        ]

    async def get_challenges(self):
        """
        Get challenges from the vulnerable application.
        
        Args:
            app_id: UUID of the application
            agent_id: UUID of the agent
            
        Returns:
            Dictionary with challenges data
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        # Create the HTTP message to be sent
        response = await self._vuln_client.get(f"/api/Challenges")
        return [ 
            Vulnerability(**vuln) for vuln in response.json()["data"]
        ]