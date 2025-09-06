import asyncio
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from common.constants import (
    MAX_DISCOVERY_AGENT_STEPS, 
    MAX_DISCOVERY_PAGE_STEPS, 
    SCREENSHOTS,
    BROWSER_CDP_PORT,
    BROWSER_CDP_HOST,
)
from eval.eval_pool import EvalAgentPool
from eval.harness.exploit.queue import PersistedQueue
from eval.datasets.detection import DISCOVERY_QUEUE_JSON
from logger import setup_agent_logger, get_agent_loggers
from src.agent.prompts import CUSTOM_SYSTEM_PROMPT
from src.llm_models import LLMHub

# local connections
from cnc.workers.agent.browser import get_browser_session
from cnc.workers.agent.cdp_handler import CDPHTTPHandler
from cnc.workers.agent.proxy_handler import MitmProxyHTTPHandler
from src.agent.http_history import HTTPHandler

# supported agents
from src.agent.min_agent import MinimalAgent
from src.agent.min_agent_single_page import MinimalAgentSinglePage

# browser-use imports
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.service import Controller
from playwright.async_api import async_playwright

agent_log, _ = get_agent_loggers()

MAX_WORKERS = 3 # 1 for testing
MAX_STEPS = 3
MODEL_CONFIG = {
    "model_config": {
        "browser_use": "gpt-4.1",
        "update_plan": "o3-mini",
        "create_plan": "o3-mini",
        "check_plan_completion": "gpt-4.1",
    }
}

class StartDiscoveryRequest(BaseModel):
    start_urls: List[str]
    scopes: Optional[List[str]] = None
    init_task: Optional[str] = None


class DiscoveryAgentPool(EvalAgentPool[StartDiscoveryRequest]):
    """
    AgentPool for running the async MinimalAgent flow inside the pool's thread executor.

    It packages the initialization routine from start_agent.py (proxy, browser session,
    controller, eval client) and executes MinimalAgent.run().
    """
    def __init__(
        self,
        *,
        channel,
        item_cls,
        agent_cls: Type[Union[MinimalAgent, MinimalAgentSinglePage]],
        queue_fp: str,
        llm_config: Dict,
        browser_session: BrowserSession,
        cdp_port: int = 9899,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 8081,
        exclude_actions: Optional[List[str]] = None,
        chromium_executable_path: Optional[str] = None,
        log_subfolder: str = "min_agent",
        max_workers: Optional[int] = None,
    ) -> None:
        super().__init__(
            channel=channel,
            item_cls=item_cls,
            queue_fp=queue_fp,
            llm_config=llm_config,
            max_workers=max_workers,
            log_subfolder=log_subfolder,
        )
        self._agent_cls = agent_cls
        self._browser_session = browser_session
        self._cdp_port = cdp_port
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._exclude_actions = exclude_actions or ["extract_structured_data"]
        self._chromium_executable_path = chromium_executable_path
        self._agent_log, _ = get_agent_loggers()

    async def start_agent_session(self, queue_item: StartDiscoveryRequest):
        """
        Build and run a MinimalAgent session for a single discovery request.
        """
        cdp_handler = MitmProxyHTTPHandler(
            handler=HTTPHandler(scopes=queue_item.scopes),
            # listen_host=PROXY_HOST,
            # listen_port=PORT,
            start_browser=False,
        )
        await cdp_handler.connect()

        # cdp_handler = CDPHTTPHandler(
        #     handler=HTTPHandler(scopes=queue_item.scopes),
        #     cdp_host=BROWSER_CDP_HOST,
        #     cdp_port=BROWSER_CDP_PORT,
        # )
        # await cdp_handler.connect()

        # LLM and Controller
        llm = LLMHub(self.llm_config["model_config"])
        controller = Controller(exclude_actions=self._exclude_actions)
        agent = self._agent_cls(
            start_urls=list(queue_item.start_urls),
            llm=llm,
            max_steps=MAX_DISCOVERY_AGENT_STEPS,
            max_page_steps=MAX_DISCOVERY_PAGE_STEPS,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=self._browser_session,
            controller=controller,
            cdp_handler=cdp_handler,
            agent_dir=self.parent_dir,
            init_task=queue_item.init_task,
            screenshots=SCREENSHOTS,
        )
        await agent.run()

        # dun matter
        return True

async def run_asyncio_loop_with_sigint_handling():
    setup_agent_logger(log_dir=".min_agent/logs")
    loop = asyncio.get_running_loop()
    browser_session = await get_browser_session()

    vuln_queue = PersistedQueue()
    agent_pool = DiscoveryAgentPool(
        channel=vuln_queue,
        queue_fp=DISCOVERY_QUEUE_JSON,
        llm_config=MODEL_CONFIG,
        browser_session=browser_session,
        max_workers=MAX_WORKERS,
        item_cls=StartDiscoveryRequest,
        agent_cls=MinimalAgentSinglePage,
    )

    await agent_pool.start_channel_consumer()
    print("Started channel consumer")

    # try:
    #     # https://chatgpt.com/c/68b8db0e-0910-832e-b8d7-972204f79797
    #     # Does not explain why signal.signal handler does not fire though
    #     signal.signal(signal.SIGINT, agent_pool._sigint)
    #     signal.signal(signal.SIGTERM, agent_pool._sigint)
    #     loop.add_signal_handler(signal.SIGINT, agent_pool._sigint)
    #     loop.add_signal_handler(signal.SIGTERM, agent_pool._sigint)
    # except NotImplementedError:
    #     # Windows fallback: use sync handler + thread-safe callback
    #     def _sync_handler(signum, frame):
    #         loop.call_soon_threadsafe(agent_pool._sigint)

    #     signal.signal(signal.SIGINT, _sync_handler)
    #     if hasattr(signal, "SIGTERM"):
    #         signal.signal(signal.SIGTERM, _sync_handler)

    # # - first the signal handlers registered on the event loop will not trigger since loop returned
    # # - second, after asyncio.run() finishes, the main thread enters shutdown process
    # # > while it waits for non-daemon threads to join (ThreadPoolExecutor threads)
    # # > during this process no signal handlers are active to catch the signals
    # while True:
    #     await asyncio.sleep(1)

async def main():
    from cnc.workers.agent.browser import start_single_browser
    
    # TMRW:
    # - request time out for in-scope URLs; investigate
    # - this function does not terminate
    try:
        browser_task = asyncio.create_task(start_single_browser())
        await asyncio.sleep(2)
        await asyncio.gather(
            browser_task,
            run_asyncio_loop_with_sigint_handling()
        )
        
    except asyncio.CancelledError:
        print("Tasks were cancelled")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":    
    asyncio.run(main())