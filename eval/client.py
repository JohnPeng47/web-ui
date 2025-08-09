from typing import Any, Dict, List, Optional, Callable, Tuple

import httpx
from abc import ABC, abstractmethod

from httplib import HTTPMessage
from pentest_bot.logger import get_agent_loggers
from pentest_bot.discovery.url import Route

agent_log, _ = get_agent_loggers()

class AgentEvalClient(ABC):
    def __init__(
        self, 
        challenges: List[Route],
        async_client: httpx.AsyncClient
    ):
        self._shutdown: Optional[Callable] = None
        self._solved = [(challenge, False) for challenge in challenges]
        self._async_client = async_client

    def set_shutdown(self, shutdown):
        pass

    @abstractmethod
    def update_status(self, http_msgs: List[HTTPMessage]) -> None:
        pass

    @abstractmethod
    def report_progress(self) -> Tuple[Dict, str]:
        pass

class DiscoveryEvalClient(AgentEvalClient):
    def update_status(self, http_msgs: List[HTTPMessage]) -> None:
        for msg in http_msgs:
            for idx, (challenge, solved) in enumerate(self._solved):
                if challenge.match(msg.request.url, method=msg.request.method):
                    agent_log.info(f"Discovered {challenge}!")
                    self._solved[idx] = (challenge, True)

    def report_progress(self) -> Tuple[Dict, str]:
        progress = {
            "solved": [challenge for challenge, solved in self._solved if solved],
            "total": len(self._solved),
        }
        solved_count = len(progress["solved"])
        total_count = progress["total"]
        progress_str = f'Solved {solved_count} out of {total_count} challenges: {progress["solved"]}'
        return progress, progress_str