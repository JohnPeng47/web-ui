import asyncio
import threading
from collections import deque
from typing import Any, AsyncGenerator


class _ThreadSafeDeque:
    """Minimal blocking queue usable from both asyncio & threads."""
    def __init__(self):  # FIFO
        self._dq: deque = deque()
        self._cv = threading.Condition()

    def put(self, item: Any):
        with self._cv:
            self._dq.append(item)
            self._cv.notify()

    def get(self, timeout: float | None = None) -> Any:
        with self._cv:
            if not self._dq:
                self._cv.wait(timeout)
            return self._dq.popleft() if self._dq else None


class EventBus:
    """
    Drop-in replacement for the old Redis Streams API.
    • publish_raw / consume_raw  – traffic from agents
    • publish_enriched / consume_enriched – after enrichment
    """
    def __init__(self):
        self._raw = _ThreadSafeDeque()
        self._enriched = _ThreadSafeDeque()

    # ------------- public coroutine helpers -----------------
    async def publish_raw(self, item: dict):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._raw.put, item)

    async def publish_enriched(self, item: dict):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._enriched.put, item)

    async def consume_raw(self) -> AsyncGenerator[dict, None]:
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, self._raw.get, 1.0)
            if item is not None:
                yield item

    async def consume_enriched(self) -> AsyncGenerator[dict, None]:
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, self._enriched.get, 1.0)
            if item is not None:
                yield item