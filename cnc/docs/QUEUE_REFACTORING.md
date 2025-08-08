# Queue Refactoring: From Global Singletons to Dependency Injection

This document describes the refactoring of the messaging system from using global singleton queues to a proper dependency injection pattern with explicit channels passed through constructors.

## Motivation & Design Goals

| Goal | Why it matters | How the new design achieves it |
|------|----------------|-------------------------------|
| Isolation | You may want multiple hubs in the same process (unit-tests, multi-tenant SaaS, embedded mode) | Each hub creates its own channel set and hands references to the components it spawns. No hidden cross-talk. |
| Testability | Workers that reference globals can't be instantiated in a test without monkey-patching. | A worker now only needs one argument (inbound, or in/outbound) → drop-in fake/stub queues. |
| Runtime Flexibility | You might hot-swap Redis/NATS later, or run some workers in another process. | The type of the channel is an injected dependency that only must expose subscribe() + publish(); anything that satisfies that protocol works. |
| Clear Dependency Graph | Static analysis & type checkers can't "see" globals. | Constructor parameters encode exact needs; DI frameworks (FastAPI, Pydantic, or your own factory) can wire them. |

## Core Primitive: BroadcastChannel

```python
class BroadcastChannel(Generic[T]):
    """
    A tiny pub/sub primitive:
      • publish(item): copies `item` into every subscriber queue
      • subscribe(): returns an asyncio.Queue from which the subscriber
                     continuously reads.
    """
    def __init__(self):
        self._subs: List[asyncio.Queue[T]] = []

    def subscribe(self) -> asyncio.Queue[T]:
        q: asyncio.Queue[T] = asyncio.Queue()
        self._subs.append(q)
        return q

    async def publish(self, item: T):
        for q in self._subs:
            await q.put(item)
```

Nothing else in the codebase "knows" what the queue implementation is - any implementation that satisfies the protocol could be used.

## Worker Interfaces After the Change

### EnrichmentWorker

```python
class RequestEnrichmentWorker:
    def __init__(
        self,
        *,
        inbound: BroadcastChannel[HTTPMessage],      # READ
        outbound: BroadcastChannel[EnrichedRequest]  # WRITE
    ):
        self._sub_q = inbound.subscribe()
        self._outbound = outbound

    async def run(self):
        while True:
            raw_msg = await self._sub_q.get()
            enr_msg = await self._enrich(raw_msg)
            await self._outbound.publish(enr_msg)
```

### AuthzAttacker

```python
class AuthzAttacker:
    def __init__(self, inbound: BroadcastChannel[EnrichedRequest]):
        self._sub_q = inbound.subscribe()

    async def run(self):
        while True:
            enr = await self._sub_q.get()
            await self.ingest(**self._explode(enr))
```

Notice there's no queue_id, no queues.get(…), no import-time side effects.

## Application Startup / Wiring

```python
# main.py (FastAPI factory)

def create_app() -> FastAPI:
    app = FastAPI()

    # --- Create hub-local channel instances
    raw_channel = BroadcastChannel[HTTPMessage]()
    enriched_channel = BroadcastChannel[EnrichedRequest]()

    # store them so routers & workers can access
    app.state.raw_channel = raw_channel
    app.state.enriched_channel = enriched_channel

    # Routers need raw_channel for publishing
    app.include_router(make_application_router(raw_channel))
    app.include_router(make_agent_router(raw_channel))

    return app
```

### workers_launcher.py

```python
async def start_workers(app: FastAPI):
    # reuse the *same* objects from FastAPI if you launch in-process
    raw_ch = app.state.raw_channel
    enriched_ch = app.state.enriched_channel

    worker_enr = RequestEnrichmentWorker(
        inbound=raw_ch, outbound=enriched_ch
    )
    worker_auth = AuthzAttacker(inbound=enriched_ch)

    await asyncio.gather(worker_enr.run(), worker_auth.run())
```

## Router Dependency Injection

```python
def make_agent_router(raw_channel: BroadcastChannel[HTTPMessage]) -> APIRouter:
    router = APIRouter()

    @router.post("/{app_id}/agents/push", status_code=202)
    async def push_messages(app_id: UUID, payload: PushMessages, agent=Depends(...)):
        ...
        for msg in payload.messages:
            await raw_channel.publish(msg)
        return {"accepted": len(payload.messages)}

    return router
```

A small factory (make_agent_router(raw_channel)) builds the router with the correct queue instance.

## Benefits to Testing

With this refactoring, you can now:

1. Test workers in isolation by injecting test channels
2. Create multiple independent hub instances in the same process
3. Mock or fake channels easily for testing
4. Run unit tests without any global state being shared

See the tests in `tests/test_queue_isolation.py` for examples.

## Legacy Support / Migration Strategy

Since refactoring everything at once would be disruptive, we've implemented a transition strategy:

1. The old queues.get(name) API still works through a legacy compatibility layer
2. Existing router endpoints continue to work through exported router instances
3. Legacy worker classes are preserved but marked as deprecated

As more code is migrated to the new pattern, these legacy support mechanisms can be removed.

## Next Steps

Future enhancements to the messaging system could include:

1. Implementing alternative channel types (Redis, NATS, etc.)
2. Adding message filtering or routing capabilities
3. Creating standardized patterns for error handling
4. Implementing message serialization/deserialization for cross-process messaging 