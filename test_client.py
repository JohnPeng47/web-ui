from httpx import AsyncClient
from typing import Any, Dict, List, Optional
from src.agent.client import AgentClient
from pydantic import BaseModel

from cnc.tests.challenges.vulnerability import Vulnerability
from uuid import UUID

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
        self.completed: Dict[int, str] = {}

        non_exist = self._check_target_vulns()
        if non_exist:
            raise ValueError(f"Targeted vulns do not exist: {non_exist}" )
        
        logger.info(f"Starting test for targets: {[vuln.id for vuln in self._targeted_vulns]}")

    def _check_target_vulns(self):
        return [
            vuln.id for vuln in self._targeted_vulns
            if vuln.id not in self._all_vulns
        ]

    def _check_complete(self, challenges_dict) -> List[bool]:
        """
        Check if all targeted vulnerabilities have been completed.
        
        Args:
            challenges_dict: Dictionary of challenges from the server
            
        Returns:
            Dictionary with completion status for each targeted vulnerability
        """
        results = {}
        
        # Extract the challenges data from the response
        challenges = challenges_dict.get("data", [])
        
        # Create a mapping of challenge IDs to their solved status
        challenge_status = {challenge["id"]: challenge["solved"] for challenge in challenges}
        
        # Check each targeted vulnerability
        for vuln in self._targeted_vulns:
            vuln_id = vuln.id
            if vuln_id in challenge_status:
                results[vuln_id] = {
                    "name": vuln.name,
                    "completed": challenge_status[vuln_id]
                }
            else:
                # If the vulnerability ID isn't found in the challenges
                results[vuln_id] = {
                    "name": vuln.name,
                    "completed": False,
                    "error": "Challenge not found in server response"
                }
        
        return results
            

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
        return response.json()
    
    async def update_server_state(self, 
                                  app_id: UUID, 
                                  agent_id: UUID,
                                  messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Push HTTP messages to the system for processing.
        
        Args:
            app_id: UUID of the application
            agent_id: UUID of the agent
            messages: List of HTTP messages to push
            
        Returns:
            Dictionary with number of accepted messages
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        challenges = await self.get_challenges()
        return await self.push_messages(app_id, agent_id, messages)