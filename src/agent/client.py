import httpx
from typing import List, Dict, Any, Optional, Union, Protocol
from uuid import UUID


class HTTPClientProtocol(Protocol):
    """Protocol for HTTP clients to ensure compatibility."""
    
    async def post(self, url: str, **kwargs) -> Any:
        """Post request method."""
        ...
    
    async def aclose(self) -> None:
        """Close the client."""
        ...


class SyncHTTPClientProtocol(Protocol):
    """Protocol for synchronous HTTP clients."""
    
    def post(self, url: str, **kwargs) -> Any:
        """Post request method."""
        ...
    
    def close(self) -> None:
        """Close the client."""
        ...


class AppClient:
    """
    Base client that wraps httpx.AsyncClient.
    Provides a common interface for API interactions.
    """
    
    def __init__(self, 
                 client: Any,
                 headers: Optional[Dict[str, str]] = None):
        """
        Initialize the app client.
        
        Args:
            client: httpx.AsyncClient instance
            headers: Default headers to use for all requests
        """
        self.client = client
        self.headers = headers or {}
    
    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()
    
    async def post(self, path: str, **kwargs) -> Any:
        """
        Make a POST request.
        
        Args:
            path: URL path
            **kwargs: Additional arguments to pass to the client
            
        Returns:
            Response from the client
        """
        # Merge headers if provided
        if "headers" in kwargs:
            headers = {**self.headers, **kwargs["headers"]}
            kwargs["headers"] = headers
        else:
            kwargs["headers"] = self.headers
            
        return await self.client.post(path, **kwargs)


class SyncAppClient:
    """
    Synchronous version of AppClient.
    """
    
    def __init__(self, 
                 client: Any,
                 headers: Optional[Dict[str, str]] = None):
        """
        Initialize the app client.
        
        Args:
            client: httpx.Client instance
            headers: Default headers to use for all requests
        """
        self.client = client
        self.headers = headers or {}
    
    def close(self):
        """Close the underlying HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def post(self, path: str, **kwargs) -> Any:
        """
        Make a POST request.
        
        Args:
            path: URL path
            **kwargs: Additional arguments to pass to the client
            
        Returns:
            Response from the client
        """
        # Merge headers if provided
        if "headers" in kwargs:
            headers = {**self.headers, **kwargs["headers"]}
            kwargs["headers"] = headers
        else:
            kwargs["headers"] = self.headers
            
        return self.client.post(path, **kwargs)


class AgentClient:
    """
    HTTP client for interacting with the agent API endpoints defined in cnc/routers/agent.py.
    """
    
    def __init__(self, 
                 username: str = "test", 
                 role: str = "Tester", 
                 timeout: int = 30, 
                 client: Optional[Any] = None):
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
        
        headers = {
            "Content-Type": "application/json",
            "X-Username": username,
            "X-Role": role
        }
        
        http_client = client if client else httpx.AsyncClient(timeout=timeout)
        self.client = AppClient(http_client, headers)
    
    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.close()
    
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
        print(response.text)
        response.raise_for_status()
        return response.json()