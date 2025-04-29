import httpx
from typing import List, Dict, Any, Optional
from uuid import UUID


class AgentClient:
    """
    HTTP client for interacting with the agent API endpoints defined in cnc/routers/agent.py.
    """
    
    def __init__(self, base_url: str, username: str, role: str, timeout: int = 30):
        """
        Initialize the agent client.
        
        Args:
            base_url: Base URL of the API server
            username: Username to identify the agent
            role: Role of the agent
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.role = role
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self.headers = {
            "Content-Type": "application/json",
            "X-Username": username,
            "X-Role": role
        }
    
    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()
    
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
        url = f"{self.base_url}/application/"
        payload = {
            "name": name,
            "description": description
        }
        
        response = await self.client.post(url, json=payload)
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
        url = f"{self.base_url}/application/{app_id}/agents/register"
        payload = {
            "user_name": self.username,
            "role": self.role
        }
        
        response = await self.client.post(url, json=payload)
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
            messages: List of HTTP messages to push
            
        Returns:
            Dictionary with number of accepted messages
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        url = f"{self.base_url}/application/{app_id}/agents/push"
        payload = {
            "agent_id": str(agent_id),
            "messages": messages
        }
        
        response = await self.client.post(
            url, 
            json=payload, 
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()


# Synchronous version of the client for simpler use cases
class SyncAgentClient:
    """
    Synchronous HTTP client for interacting with the agent API endpoints.
    """
    
    def __init__(self, base_url: str, username: str, role: str, timeout: int = 30):
        """
        Initialize the agent client.
        
        Args:
            base_url: Base URL of the API server
            username: Username to identify the agent
            role: Role of the agent
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.role = role
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self.headers = {
            "Content-Type": "application/json",
            "X-Username": username,
            "X-Role": role
        }
    
    def close(self):
        """Close the underlying HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def create_application(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
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
        url = f"{self.base_url}/application/"
        payload = {
            "name": name,
            "description": description
        }
        
        response = self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def register_agent(self, app_id: UUID) -> Dict[str, Any]:
        """
        Register a new agent for an application.
        
        Args:
            app_id: UUID of the application
            
        Returns:
            Agent information including id, username, role, and application_id
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        url = f"{self.base_url}/application/{app_id}/agents/register"
        payload = {
            "user_name": self.username,
            "role": self.role
        }
        
        response = self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def push_messages(self, app_id: UUID, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Push HTTP messages to the system for processing.
        
        Args:
            app_id: UUID of the application
            messages: List of HTTP messages to push
            
        Returns:
            Dictionary with number of accepted messages
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        url = f"{self.base_url}/application/{app_id}/agents/push"
        payload = {
            "messages": messages
        }
        
        response = self.client.post(
            url, 
            json=payload, 
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
