import time
import concurrent.futures
import logging
import sys
from collections import defaultdict
from typing import Optional, Tuple
import concurrent.futures
import logging
import os
import signal
import sys
from abc import ABC
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Type, TypeVar, cast

from pydantic import BaseModel
from pentest_bot.web_exploit.agent import PentestSession
from pentest_bot.db import get_session
from pentest_bot.db.tables.exploit_agent import (
    AgentStepORM as AgentStepORM
)
import asyncio

class LaunchPentestBots:
    """
    Simplified version for testing multithreaded pool behavior.
    Removes most logic but keeps start_labs intact.
    """

    def __init__(self, lab_count: int = 5):
        self.lab_count = lab_count
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def _sigint(self, signum, frame):
        print("\n[!] SIGINT received – terminating thread pool …", file=sys.stderr)
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

        logging.shutdown()
        os._exit(1)

    def _install_sigint_handler(self) -> None:
        def _sigint(signum, frame):
            print("\n[!] SIGINT received – terminating thread pool …", file=sys.stderr)
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)

            logging.shutdown()
            os._exit(1)

        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGINT, _sigint)
            loop.add_signal_handler(signal.SIGTERM, _sigint)
        except NotImplementedError:
            print("Falling back to windows")
            # Windows fallback: use sync handler + thread-safe callback
            def _sync_handler(signum, frame):
                loop.call_soon_threadsafe(_sigint)
            signal.signal(signal.SIGINT, _sync_handler)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _sync_handler)

        # signal.signal(signal.SIGINT, _sigint)

    def start_agent(self, thread_id: int) -> Tuple[int, Optional[Path]]:
        try:
            print(f"Thread {thread_id}: starting")
            # Simulate work but check for cooperative stop
            for _ in range(40):
                # if stop_threads.is_set():
                #     print(f"Thread {thread_id}: stopping")
                #     return thread_id, None
                time.sleep(0.5)
            print(f"Thread {thread_id}: completed")
            return thread_id, Path(f"/tmp/log_{thread_id}.txt")
        except Exception:
            print(f"Thread {thread_id}: error")
            return thread_id, None

    async def start_labs(self) -> None:
        print("starting labs")
        # self._install_sigint_handler()
        self._executor = concurrent.futures.ThreadPoolExecutor()

        await asyncio.sleep(1)

        lab_paths = defaultdict(list)
        futures = [
            self._executor.submit(self.start_agent, thread_id)
            for thread_id in range(1, self.lab_count + 1)
        ]
        
async def run_asyncio_loop_with_sigint_handling():
    loop = asyncio.get_running_loop()
    launch_pentest_bots = LaunchPentestBots()

    await launch_pentest_bots.start_labs()

    def on_signal():
        print("SIGINT received")
        launch_pentest_bots._sigint(None, None)

    try:
        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)
        loop.add_signal_handler(signal.SIGINT, on_signal)
        loop.add_signal_handler(signal.SIGTERM, on_signal)
    except NotImplementedError:
        # Windows fallback: use sync handler + thread-safe callback
        def _sync_handler(signum, frame):
            loop.call_soon_threadsafe(on_signal)

        signal.signal(signal.SIGINT, _sync_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sync_handler)

    # - first the signal handlers registered on the event loop will not trigger since loop returned
    # - second, after asyncio.run() finishes, the main thread enters shutdown process
    # > while it waits for non-daemon threads to join (ThreadPoolExecutor threads)
    # > during this process no signal handlers are active to catch the signals
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_asyncio_loop_with_sigint_handling())
