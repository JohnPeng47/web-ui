from typing import TypeVar, Generic, List
import asyncio


T = TypeVar("T")

class BroadcastChannel(Generic[T]):
    """
    A tiny pub/sub primitive:
      • publish(item): copies `item` into every subscriber queue
      • subscribe(): returns an asyncio.Queue from which the subscriber
                     continuously reads.
    """
    def __init__(self):
        self._id = id(self)
        self._subs: List[asyncio.Queue[T]] = []

    @property
    def id(self) -> int:
        return self._id

    def subscribe(self) -> asyncio.Queue[T]:
        q: asyncio.Queue[T] = asyncio.Queue()
        self._subs.append(q)
        return q

    async def publish(self, item: T):
        for q in self._subs:
            await q.put(item)

    # Helpers
    async def get_all(self) -> List[T]:
        return [await q.get() for q in self._subs]