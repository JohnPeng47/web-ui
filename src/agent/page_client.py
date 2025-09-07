import logging
from typing import Any, Dict, Optional

import httpx

from src.agent.pages import PageObservations

logger = logging.getLogger(__name__)

class PageUpdateClient:
    """
    HTTP client for interacting with the agent API endpoints defined in cnc/routers/agent.py.
    """
    def __init__(self,
                 agent_id: int,
                 api_url: str,
                 *,
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
        self.agent_id = agent_id
        self.timeout = timeout
        self.base_url = api_url
        self.client = client if client else httpx.AsyncClient(base_url=api_url, timeout=timeout)

        headers = {
            "Content-Type": "application/json",
        }
        self.client.headers.update(headers)
        self._shutdown = None
    
    async def update_page_data(self, pages: PageObservations) -> Dict[str, Any]:
        """
        Update page data for an agent.
        
        Args:
            agent_id: ID of the agent
            pages: List of page data to upload
            
        Returns:
            Agent data response
            
        Raises:
            httpx.HTTPStatusError: If the server returns an error response
        """
        path = f"/agents/{self.agent_id}/page-data"
        payload = {
            "agent_id": self.agent_id,
            "page_data": await pages.to_json()
        }
        response = await self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()