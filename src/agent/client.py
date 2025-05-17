import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID

import httpx
from httpx import AsyncClient

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
        print(payload)

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

class VulnAppClient(AgentClient):
    """
    Thin wrapper around `AgentClient` that knows how to:

      • keep a catalogue of *all* vulnerabilities exposed by the target app
      • track which subset we care about (`_targeted_vulns`)
      • poll the target app's `/api/Challenges` endpoint and mark completion
    """

    # --------------------------- life‑cycle --------------------------------

    def __init__(
        self,
        *,
        vuln_client: AsyncClient,
        targeted_vulns: List[Vulnerability] = None,
        all_vulns: List[Vulnerability] = None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        vuln_client
            Pre‑configured httpx.AsyncClient that speaks to the vulnerable app
            (e.g. OWASP Juice Shop running at http://127.0.0.1:3000).
        targeted_vulns
            Subset of `all_vulns` the pentest run should try to exploit.
            If empty or None, no completion checking will occur.
        all_vulns
            Full list of vulnerabilities the app *could* expose.
        kwargs
            Forwarded verbatim to the parent `AgentClient`.
        """
        super().__init__(**kwargs)

        self._vuln_client = vuln_client
        self._steps = 0

        # Handle empty lists
        targeted_vulns = targeted_vulns or []
        all_vulns = all_vulns or []

        # Dict[int, Vulnerability] for O(1) lookups by ID
        self._all_vulns: Dict[int, Vulnerability] = {v.id: v for v in all_vulns}

        # Keep *objects* for the subset we target
        self._targeted_vulns: List[Vulnerability] = targeted_vulns

        # Internal solved flags — initially False
        self._completed: Dict[int, bool] = {v.id: False for v in targeted_vulns}
        self._shutdown: Callable = None
    
        # Sanity check: every target must exist in the global list
        # Skip check if no targets are specified
        if targeted_vulns:
            non_exist = self._check_target_vulns()
            if non_exist:
                raise ValueError(f"Targeted vulns do not exist: {non_exist}")
            logger.info("Target set: %s", [v.id for v in targeted_vulns])
        else:
            logger.info("No targets specified - completion checking disabled")

    # ---------------------------------------------------------------------

    def _check_target_vulns(self) -> List[int]:
        """Return IDs that are in `_targeted_vulns` but not in `_all_vulns`."""
        return [v.id for v in self._targeted_vulns if v.id not in self._all_vulns]

    # ---------------------------------------------------------------------
    # Remote helpers
    # ---------------------------------------------------------------------

    async def get_challenges(self) -> Dict[str, Any]:
        """
        GET /api/Challenges from the vulnerable application.
        The Juice Shop flavour returns `{"status": "success", "data": [...]}`.
        """
        resp = await self._vuln_client.get("/api/Challenges")
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------------
    # Completion tracking
    # ---------------------------------------------------------------------

    def _update_completion_flags(self, challenges: Dict[str, Any]) -> List[Vulnerability]:
        # If no targets specified, return empty list
        if not self._targeted_vulns:
            return []
            
        solved_by_id = {item["id"]: item["solved"]
                        for item in challenges.get("data", [])}

        newly_solved: List[Vulnerability] = []
        for vuln in self._targeted_vulns:
            if solved_by_id.get(vuln.id) and not self._completed[vuln.id]:
                self._completed[vuln.id] = True
                newly_solved.append(vuln)          # collect delta
        return newly_solved

    def all_targets_solved(self) -> bool:
        """True iff every targeted vulnerability has `completed == True`."""
        # If no targets specified, always return False
        if not self._targeted_vulns:
            return False
        return all(self._completed.values())

    # ---------------------------------------------------------------------
    # Public API used by test harness / ageents
    # ---------------------------------------------------------------------
    async def update_server_state(self,
                                app_id: UUID,
                                agent_id: UUID,
                                messages: List[Dict[str, Any]],
                                browser_actions: Optional[List[BrowserActions]] ) -> Dict[str, int]:
        # 1. fire‑and‑forget – don't wait for the push
        asyncio.create_task(self.push_messages(app_id, agent_id, messages, browser_actions))

        # 2. pull latest challenge data
        challenges = await self.get_challenges()

        # 3. refresh flags and get the *new* ones
        newly_solved = self._update_completion_flags(challenges)

        # --- progress & highlight logs --------------------------------------
        for vuln in newly_solved:
            logger.info("### NEWLY SOLVED TARGET %s – %s ###", vuln.id, vuln.name)

        # If no targets specified, return empty status
        if not self._targeted_vulns:
            return {"solved_targets": 0, "remaining": 0}
            
        solved     = sum(self._completed.values())
        remaining  = len(self._completed) - solved
        logger.info("Progress: %d / %d targets solved (%d remaining)",
                    solved, len(self._completed), remaining)

        # 4. graceful shutdown when done
        if remaining == 0:
            logger.info("All targeted vulnerabilities solved – shutting down.")
            if callable(self._shutdown):
                await self._shutdown()

        # 5. short status dict for callers
        return {"solved_targets": solved, "remaining": remaining}
