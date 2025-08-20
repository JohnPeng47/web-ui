from typing import Any, Dict, List, Optional, Callable, Tuple

import httpx
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from httplib import HTTPMessage
from pentest_bot.logger import get_agent_loggers
from pentest_bot.discovery.url import Route

agent_log, _ = get_agent_loggers()

# TODO: remove this when we 100% dont need old eval juiceshop anymore
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
        return progress

class PagedDiscoveryEvalClient:
    def __init__(
        self, 
        challenges: Dict,
        async_client: httpx.AsyncClient
    ):
        self._shutdown: Optional[Callable] = None
        self._solved = {path: [(api, False) for api in apis] for path, apis in challenges.items()}
        self._async_client = async_client
        self._last_solved_url = None

    def set_shutdown(self, shutdown):
        pass

    def update_status(self, http_msgs: List[HTTPMessage], page_url: str) -> Optional[float]:
        page_url = urlparse(page_url).fragment
        apis = self._solved.get(page_url, None)
        if not apis:
            return None

        for msg in http_msgs:
            for idx, (challenge, solved) in enumerate(apis):
                agent_log.info("[Matching]: ", msg.request.url, msg.request.method)
                if challenge.match(msg.request.url, method=msg.request.method):
                    agent_log.info(f"Discovered {challenge}!")
                    apis[idx] = (challenge, True)
                    self._last_solved_url = page_url

        return (sum([1 for api, solved in apis if solved]) / len(apis))

    def report_progress(self) -> Tuple[Dict, str]:
        progress = {
            "solved": {},
            "total": 0,
        }
        for path, apis in self._solved.items():
            solved_apis = [api for api, solved in apis if solved]
            progress["solved"][path] = solved_apis
            progress["total"] += len(apis)
                
        # Create solve rate string for each page
        page_rates = []
        for path, apis in self._solved.items():
            solved_count = sum(1 for api, solved in apis if solved)
            total_apis = len(apis)
            page_rates.append(f"{path}: {solved_count}/{total_apis}")
        
        progress_str = " | ".join(page_rates)
        
        return progress, progress_str

