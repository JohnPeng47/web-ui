import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID

import httpx

from cnc.tests.challenges.vulnerability import Vulnerability
from common.agent import BrowserActions

logger = logging.getLogger(__name__)

class AgentTestComplete(Exception):
    def __init__(self, complete_status: Dict):
        super().__init__(complete_status)
        self.complete_status = complete_status

class AgentClient:
    """
    HTTP client for interacting with the agent API endpoints defined in cnc/routers/agent.py.
    """
    def __init__(self, 
                 *,
                 username: str = "test", 
                 role: str = "Tester", 
                 timeout: int = 45, 
                 client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the agent client.
        
        Args:
            username: Username to identify the agent
            role: Role of the agent
            timeout: Request timeout in seconds
            client: Optional client to use instead of creating a new one
        """
        self.username = username
        self.role = role
        self.timeout = timeout
        self.client = client if client else httpx.AsyncClient(timeout=timeout)

        headers ={
            "Content-Type": "application/json",
            "X-Username": username,
            "X-Role": role
        }
        self.client.headers.update(headers)
        self._shutdown = None

    def set_shutdown(self, shutdown: Callable) -> None:
        """
        Set a shutdown function to be called when the agent is done.
        """
        self._shutdown = shutdown

    async def create_application(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new application.
        
        Args:
            name: Name of the application
            description: Optional description of the application
            
        Returns:
            Application information including id, name, description, and created_at
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        path = "/application/"
        payload = {
            "name": name,
            "description": description
        }
        
        response = await self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()
    
    async def register_agent(self, app_id: UUID) -> Dict[str, Any]:
        """
        Register a new agent for an application.
        
        Args:
            app_id: UUID of the application
            
        Returns:
            Agent information including id, username, role, and application_id
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        path = f"/application/{app_id}/agents/register"
        payload = {
            "user_name": self.username,
            "role": self.role
        }
        
        response = await self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()
    
    async def push_messages(self, 
                            app_id: UUID, 
                            agent_id: UUID,
                            messages: List[Dict[str, Any]],
                            browser_actions: Optional[BrowserActions]) -> Dict[str, int]:
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
        path = f"/application/{app_id}/agents/push"
        payload = {
            "agent_id": str(agent_id),
            "http_msgs": messages,
            "browser_actions": browser_actions.model_dump() if browser_actions else None
        }

        response = await self.client.post(path, json=payload, timeout=None)
        response.raise_for_status()
        return response.json()
    
    async def update_server_state(self, 
                                  app_id: UUID, 
                                  agent_id: UUID,
                                  messages: List[Dict[str, Any]],
                                  browser_actions: Optional[BrowserActions]) -> None:
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
        asyncio.create_task(self.push_messages(app_id, agent_id, messages, browser_actions))