import httpx
from typing import List, Dict, Any, Optional, Union, Protocol
from uuid import UUID

class AgentClient:
    """
    HTTP client for interacting with the agent API endpoints defined in cnc/routers/agent.py.
    """
    def __init__(self, 
                 *,
                 username: str = "test", 
                 role: str = "Tester", 
                 timeout: int = 30, 
                 client: httpx.AsyncClient = None):
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

        headers ={
            "Content-Type": "application/json",
            "X-Username": username,
            "X-Role": role
        }
        self.client = client
        self.client.headers.update(headers)
    
    async def create_application(self, name: str, description: Optional[str] = None) -> UUID:
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
        return response.json()["id"]
    
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
        path = f"/application/{app_id}/agents/push"
        payload = {
            "agent_id": str(agent_id),
            "messages": messages
        }
        
        response = await self.client.post(path, json=payload)
        response.raise_for_status()
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
        return await self.push_messages(app_id, agent_id, messages)