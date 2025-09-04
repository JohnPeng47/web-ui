import asyncio
import concurrent.futures
import logging
import os
import signal
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple

stop_threads = threading.Event()  # cooperative stop for workers

class LaunchPentestBots:
    def __init__(self, lab_count: int = 5):
        self.lab_count = lab_count
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None

    def start_agent(self, thread_id: int) -> Tuple[int, Optional[Path]]:
        try:
            print(f"Thread {thread_id}: starting")
            # Simulate work but check for cooperative stop
            for _ in range(40):
                if stop_threads.is_set():
                    print(f"Thread {thread_id}: stopping")
                    return thread_id, None
                time.sleep(0.5)
            print(f"Thread {thread_id}: completed")
            return thread_id, Path(f"/tmp/log_{thread_id}.txt")
        except Exception:
            print(f"Thread {thread_id}: error")
            return thread_id, None

    async def start_labs(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor()
        futures = [
            self._executor.submit(self.start_agent, thread_id)
            for thread_id in range(1, self.lab_count + 1)
        ]
        # Optionally: poll completions on the asyncio side (not required to see signals)
        async def _poll():
            nonlocal futures
            lab_paths = defaultdict(list)
            while futures:
                done, pending = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: concurrent.futures.wait(futures, timeout=0.25, return_when=concurrent.futures.FIRST_COMPLETED)
                )
                futures = list(pending)
                for fut in done:
                    try:
                        tid, logp = fut.result()
                        if logp is not None:
                            lab_paths[tid].append(logp)
                    except Exception:
                        logging.getLogger("agentlog").exception("Future failed")
        # Fire and forget the polling task (optional)
        # asyncio.create_task(_poll())

    def shutdown(self) -> None:
        if self._executor:
            # Cancel queued futures; running ones must cooperate or you’ll need a hard kill
            self._executor.shutdown(wait=False, cancel_futures=True)

async def main():
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    bots = LaunchPentestBots()
    await bots.start_labs()

    # Register signal handlers at the loop boundary
    def on_signal() -> None:
        sys.stderr.write("\n[!] Signal received — shutting down…\n")
        stop_threads.set()
        stop.set()

    try:
        loop.add_signal_handler(signal.SIGINT, on_signal)
        loop.add_signal_handler(signal.SIGTERM, on_signal)
    except NotImplementedError:
        # Windows fallback: use sync handler + thread-safe callback
        def _sync_handler(signum, frame):
            loop.call_soon_threadsafe(on_signal)
        signal.signal(signal.SIGINT, _sync_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sync_handler)

    # Keep the loop alive so signals can be handled
    # await stop.wait()

    # Cleanup
    bots.shutdown()
    logging.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Fallback if something slips through
        sys.stderr.write("\n[!] KeyboardInterrupt — forcing exit\n")
        os._exit(1)
