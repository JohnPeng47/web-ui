from typing import TypeVar, Generic, List, Any
import asyncio
from collections import defaultdict

T = TypeVar("T")

class Channel(Generic[T]):
    def __init__(self):
        self._subs: List[asyncio.Queue[T]] = []

    def subscribe(self) -> asyncio.Queue[T]:
        q: asyncio.Queue[T] = asyncio.Queue()
        self._subs.append(q)
        return q

    async def publish(self, item: T):
        for q in self._subs:
            await q.put(item)