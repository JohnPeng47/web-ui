import concurrent.futures
import asyncio
import logging
import os
import signal
import sys
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Type, TypeVar, Generic, Callable, Coroutine


from enum import Enum
from bubus.models import Any
from pydantic import BaseModel

from pentest_bot.web_exploit.agent import PentestSession
from pentest_bot.db.tables.exploit_agent import AgentStepORM as AgentStepORM, PentestResultORM

# interpreter and tools
from pentest_bot.web_exploit.tools import PythonInterpreter
from pentest_bot.web_exploit.tools.browser_tools import create_browser_check_xss_tool, create_browser_fetch_tool
from pentest_bot.web_exploit.tools.browser import BrowserClient
from pentest_bot.models.steps import AgentStep, StepState as LLMStep

from logger import (
    create_log_dir_or_noop,
    get_agent_loggers,
    run_id_dir,
    setup_agent_logger,
)
from src.llm_models import LLMHub
from src.utils import set_ctxt_id

agent_log, full_log = get_agent_loggers()

# Optional request type for your agents. Replace or specialize as needed.
T = TypeVar("T")

LOGGER_NAME = "agentlog"
MAX_OUTPUT_LOG_LEN = 8192  # characters
DEFAULT_MAX_AGENT_STEPS = 12

class AgentRunState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class AgentRunResult(BaseModel):
    """
    What a finished agent returns. Adjust fields if your PentestSession exposes more.
    """
    success: bool
    steps: int
    max_steps: int
    model_name: str
    agent_steps: List[AgentStep]
    log_filepath: Optional[Path] = None


class AgentStatus(BaseModel):
    """
    Public status surface for a run ID.
    - state shows lifecycle
    - result appears once COMPLETED
    - error is set if FAILED
    """
    state: AgentRunState
    result: Optional[AgentRunResult] = None
    error: Optional[str] = None    

class AgentPool(ABC, Generic[T]):
    """
    A pool that accepts requests to launch abstract agents, tracks their status,
    and exposes a simple status/result API.

    Usage:
        class MyPool(AgentPool[LabInfo]):
            def start_agent_session(self, request: LabInfo) -> PentestSession:
                return PentestSession(... build from request ...)

        pool = MyPool(llm_config=..., max_workers=8)
        run_id = pool.start_agent(LabInfo(url=..., name=..., lab_ind=0))
        status = pool.get_agent_status(run_id)
    """
    def __init__(
        self,
        *,
        max_workers: Optional[int] = None,
        log_subfolder: str = "pentest_bot",
        label_steps: bool = False,
    ):
        self.label_steps = label_steps

        # TODO: we probably need 
        parent_dir = create_log_dir_or_noop(log_dir=log_subfolder)
        self.parent_dir = run_id_dir(parent_dir)
        self.parent_dir.mkdir(parents=True, exist_ok=True)

        self._executor: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        )

        # Tracking
        self._lock = threading.Lock()
        self._futures: Dict[str, concurrent.futures.Future[AgentRunResult]] = {}
        self._statuses: Dict[str, AgentStatus] = {}
        self._logs: Dict[str, Optional[Path]] = {}

    # ----------------------- Public API -----------------------

    def update_status(self, run_id: str, state: AgentRunState, result: Optional[AgentRunResult] = None, error: Optional[str] = None) -> None:
        """
        Update the status of a specific agent run.
        """
        self._statuses[run_id] = AgentStatus(
            state=state,
            result=result,
            error=error,
        )

    def start_agent(self, request: T) -> str:
        """
        Queue a single agent run based on `request`.
        Returns a run_id you can use with get_agent_status.
        """
        run_id = str(uuid.uuid4())

        self.update_status(run_id, AgentRunState.PENDING)

        # Submit work
        future = self._executor.submit(self._run_agent, run_id, request)

        # REFACTOR: keep default done_cb but allow done_db specified via args
        def _done_cb(fut: concurrent.futures.Future[AgentRunResult]) -> None:
            try:
                result = fut.result()
                self.update_status(run_id, AgentRunState.COMPLETED, result=result)
            except Exception as e:
                logging.getLogger(LOGGER_NAME).exception("Run %s failed", run_id)
                self.update_status(run_id, AgentRunState.FAILED, error=str(e))

        future.add_done_callback(_done_cb)
        with self._lock:
            self._futures[run_id] = future
            # Mark RUNNING immediately after submission
            self.update_status(run_id, AgentRunState.RUNNING)

        return run_id

    def get_agent_status(self, run_id: str) -> AgentStatus:
        """
        Returns the status and, if completed, the AgentRunResult.
        Raises KeyError if run_id is unknown.
        """
        with self._lock:
            if run_id not in self._statuses:
                raise KeyError(f"Unknown run_id: {run_id}")
            status = self._statuses[run_id]

        # If still running, reflect live state without blocking
        if status.state in {AgentRunState.RUNNING, AgentRunState.PENDING}:
            # Optionally, you can enrich with partial logs or heartbeat here
            return status

        return status

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """
        Shut down the underlying executor. Call this when you are done with the pool.
        """
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        logging.shutdown()

    @abstractmethod
    async def start_agent_session(
        self, 
        queue_item: T
    ) -> Coroutine[Any, Any, AgentRunResult]:
        """Starts a pentest session for a single lab"""
        raise NotImplementedError("Subclass must implement this method")

    # -------------------- Internal machinery ------------------
    def _sigint(self):
        print("\n[!] SIGINT received – terminating thread pool …", file=sys.stderr)
        self._executor.shutdown(wait=False, cancel_futures=True)
        logging.shutdown()

        os._exit(1)

    def _install_sigint_handler(self, shutdown_cb: Callable[[], None]) -> None:
        def _sigint(signum, frame):
            print("\n[!] SIGINT received – terminating thread pool …", file=sys.stderr)
            self._executor.shutdown(wait=False, cancel_futures=True)
            shutdown_cb()
            logging.shutdown()

            os._exit(1)
        signal.signal(signal.SIGINT, _sigint)

    # NOTE: we probbaly do want to keep these two methods for thread specific 
    # routines that we want to perform for each run 
    def _run_agent(self, run_id: str, request: T) -> AgentRunResult:
        """
        Worker that configures per-run logging, builds the session, executes it,
        and returns a structured result.
        """
        return asyncio.run(self._run_agent_async(run_id, request))

    async def _run_agent_async(self, run_id: str, request: T) -> AgentRunResult:
        """
        Async worker variant that supports an async start_pentest_session while
        preserving the external synchronous API.
        """
        set_ctxt_id(run_id)

        _, log_filepath = setup_agent_logger(
            LOGGER_NAME,
            parent_dir=self.parent_dir,
        )
        run_logger = logging.getLogger("agentlog")
        run_logger.info("agent started: run_id %s", run_id)

        session = await self.start_agent_session(request)

        # NOTE: placeholder for now
        return AgentRunResult(
            success=True,
            steps=0,
            max_steps=0,
            model_name="",
            agent_steps=[],
            log_filepath=log_filepath,
        )
        
        # # Support async start_pentest_session
        # session_or_coro = 
        # if inspect.isawaitable(session_or_coro):
        #     session = await session_or_coro
        # else:
        #     session = session_or_coro

        # # session.result() may be sync or async; support both
        # result_or_awaitable = session.result()
        # if inspect.isawaitable(result_or_awaitable):
        #     success, steps, max_steps, model_name = await result_or_awaitable
        # else:
        #     success, steps, max_steps, model_name = result_or_awaitable

        # # session.steps() may be sync or async; support both
        # steps_value = session.steps()
        # if inspect.isawaitable(steps_value):
        #     agent_steps = await steps_value
        # else:
        #     agent_steps = steps_value

        # # Persist if subclass implements it
        # try:
        #     self.persist_results(
        #         run_id=run_id,
        #         log_filepath=log_filepath,
        #         success=success,
        #         steps=steps,
        #         max_steps=max_steps,
        #         model_name=model_name,
        #         agent_steps=agent_steps,
        #         session=session,
        #         model_router=model_router,
        #     )
        # except Exception:
        #     run_logger.exception("persist_results failed for run_id %s", run_id)

        # result = AgentRunResult(
        #     success=success,
        #     steps=steps,
        #     max_steps=max_steps,
        #     model_name=model_name,
        #     agent_steps=agent_steps,
        #     log_filepath=log_filepath,
        # )
        # return result