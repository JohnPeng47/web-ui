from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID

from httpx import AsyncClient

from src.agent.client import AgentClient  # ↖ adjust if your path differs
from cnc.tests.challenges.vulnerability import Vulnerability

logger = logging.getLogger(__name__)

class AgentTestComplete(Exception):
    def __init__(self, complete_status: Dict):
        super().__init__(complete_status)
        self.complete_status = complete_status


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
        targeted_vulns: List[Vulnerability],
        all_vulns: List[Vulnerability],
        **kwargs,
    ):
        """
        Parameters
        ----------
        vuln_client
            Pre‑configured httpx.AsyncClient that speaks to the vulnerable app
            (e.g. OWASP Juice Shop running at http://127.0.0.1:3000).
        targeted_vulns
            Subset of `all_vulns` the pentest run should try to exploit.
        all_vulns
            Full list of vulnerabilities the app *could* expose.
        kwargs
            Forwarded verbatim to the parent `AgentClient`.
        """
        super().__init__(**kwargs)

        self._vuln_client = vuln_client
        self._steps = 0

        # Dict[int, Vulnerability] for O(1) lookups by ID
        self._all_vulns: Dict[int, Vulnerability] = {v.id: v for v in all_vulns}

        # Keep *objects* for the subset we target
        self._targeted_vulns: List[Vulnerability] = targeted_vulns

        # Internal solved flags — initially False
        self._completed: Dict[int, bool] = {v.id: False for v in targeted_vulns}

        self._shutdown: Callable = None
    
        # Sanity check: every target must exist in the global list
        non_exist = self._check_target_vulns()
        if non_exist:
            raise ValueError(f"Targeted vulns do not exist: {non_exist}")

        logger.info("Target set: %s", [v.id for v in targeted_vulns])

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
        The Juice Shop flavour returns `{"status": "success", "data": [...]}`.
        """
        resp = await self._vuln_client.get("/api/Challenges")
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------------
    # Completion tracking
    # ---------------------------------------------------------------------

    def _update_completion_flags(self, challenges: Dict[str, Any]) -> None:
        """
        Inspect the JSON returned from `/api/Challenges` and set
        `self._completed[id] = True` for every solved target.
        """
        solved_by_id = {
            item["id"]: item["solved"] for item in challenges.get("data", [])
        }
        for vuln in self._targeted_vulns:
            if solved_by_id.get(vuln.id):
                if not self._completed[vuln.id]:
                    logger.info("✓ Challenge %s (%s) solved", vuln.id, vuln.name)
                self._completed[vuln.id] = True

    def all_targets_solved(self) -> bool:
        """True iff every targeted vulnerability has `completed == True`."""
        return all(self._completed.values())

    # ---------------------------------------------------------------------
    # Public API used by test harness / agents
    # ---------------------------------------------------------------------

    async def update_server_state(
        self,
        app_id: UUID,
        agent_id: UUID,
        messages: List[Dict[str, Any]],
    ) -> None:
        """
        1. Push collected HTTP messages to the central pentest server
           (via the inherited `push_messages()`).
        2. Pull `/api/Challenges` from the vulnerable app.
        3. Update completion flags & return a short status dict.

        Returns
        -------
        {"accepted": int, "solved_targets": int, "remaining": int}
        """
        # Step 1 — push messages to the pentest orchestrator
        push_res = await self.push_messages(app_id, agent_id, messages)

        # Step 2 — fetch latest challenge statuses from the vulnerable app
        challenges = await self.get_challenges()

        # Step 3 — refresh local state
        self._update_completion_flags(challenges)

        solved = sum(self._completed.values())
        remaining = len(self._completed) - solved

        test_status = {
            "solved_targets": solved,
            "remaining": remaining,
        }

        logger.info(f"##### Vuln test status: {test_status}")

        if remaining == 0:
            await self._shutdown(reason=f"All tests passed: {test_status}")