import asyncio
import signal
from typing import Dict, List, Optional, Type, Union

from common.constants import (
    SCREENSHOTS,
    DISCOVERY_MODEL_CONFIG
)
from eval.datasets.detection import DISCOVERY_QUEUE_JSON
from src.agent.discovery.prompts.sys_prompt import CUSTOM_SYSTEM_PROMPT
from src.llm_models import LLMHub
from cnc.pools.pool import LiveQueuePool
from cnc.services.queue import BroadcastChannel

# supported agents
from src.agent.discovery.agent import DiscoveryAgent
from src.agent.discovery.min_agent_single_page import MinimalAgentSinglePage

# local connections
from cnc.pools.pool import StartDiscoveryRequest
from cnc.workers.agent.browser import get_browser_session
from src.agent.discovery.proxy import MitmProxyHTTPHandler
from common.http_handler import HTTPHandler

# browser-use imports
from browser_use.browser import BrowserSession
from browser_use.controller.service import Controller

from logger import AGENT_POOL_LOGGER_NAME
from logging import getLogger

pool_log = getLogger(AGENT_POOL_LOGGER_NAME)

MAX_WORKERS = 3 # 1 for testing
MAX_STEPS = 3

class DiscoveryAgentPool(LiveQueuePool[StartDiscoveryRequest]):
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
        agent_cls: Type[Union[DiscoveryAgent, MinimalAgentSinglePage]],
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

    async def start_agent_session(self, queue_item: StartDiscoveryRequest):
        """
        Build and run a MinimalAgent session for a single discovery request.
        """
        # cdp_handler = CDPHTTPHandler(
        #     handler=HTTPHandler(scopes=queue_item.scopes),
        #     cdp_host=BROWSER_CDP_HOST,
        #     cdp_port=BROWSER_CDP_PORT
        # )
        # await cdp_handler.connect()
        
        proxy_handler = MitmProxyHTTPHandler(
            handler=HTTPHandler(scopes=queue_item.scopes),
            listen_host=self._proxy_host,
            listen_port=self._proxy_port,
        )
        await proxy_handler.connect()

        # LLM and Controller
        llm = LLMHub(queue_item.model_config["model_config"])
        controller = Controller(exclude_actions=self._exclude_actions)

        agent = self._agent_cls(
            start_urls=list(queue_item.start_urls),
            llm=llm,
            max_steps=queue_item.max_steps,
            max_page_steps=queue_item.max_page_steps,
            agent_sys_prompt=CUSTOM_SYSTEM_PROMPT,
            browser_session=self._browser_session,
            controller=controller,
            cdp_handler=proxy_handler,
            agent_dir=None,
            init_task=queue_item.init_task,
            server_client=queue_item.client,
            screenshots=SCREENSHOTS,
            agent_log=queue_item.agent_log,
            full_log=queue_item.full_log,
        )
        await agent.run()

        pool_log.info("Agent successfully completed!")
        
        # dun matter
        return True


async def start_discovery_agent(
    channel: BroadcastChannel,
    agent_cls: Type[Union[DiscoveryAgent, MinimalAgentSinglePage]] = DiscoveryAgent,
):
    loop = asyncio.get_running_loop()
    browser_session = await get_browser_session()

    agent_pool = DiscoveryAgentPool(
        channel=channel,
        browser_session=browser_session,
        max_workers=MAX_WORKERS,
        item_cls=StartDiscoveryRequest,
        agent_cls=agent_cls,
    )

    await agent_pool.start_channel_consumer()
    print("Started channel consumer")

    try:
        # https://chatgpt.com/c/68b8db0e-0910-832e-b8d7-972204f79797
        # Does not explain why signal.signal handler does not fire though
        signal.signal(signal.SIGINT, agent_pool._sigint)
        signal.signal(signal.SIGTERM, agent_pool._sigint)
        loop.add_signal_handler(signal.SIGINT, agent_pool._sigint)
        loop.add_signal_handler(signal.SIGTERM, agent_pool._sigint)
    except NotImplementedError:
        # Windows fallback: use sync handler + thread-safe callback
        def _sync_handler(signum, frame):
            loop.call_soon_threadsafe(agent_pool._sigint)

        signal.signal(signal.SIGINT, _sync_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sync_handler)

    # - first the signal handlers registered on the event loop will not trigger since loop returned
    # - second, after asyncio.run() finishes, the main thread enters shutdown process
    # > while it waits for non-daemon threads to join (ThreadPoolExecutor threads)
    # > during this process no signal handlers are active to catch the signals
    while True:
        await asyncio.sleep(1)