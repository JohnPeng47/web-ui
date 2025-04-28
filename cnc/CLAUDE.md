Below is a step-by-step implementation guide for a FastAPI-based “central command” that coordinates pentesting browser agents, processes the traffic they produce, enriches it, and finally drives attack workers.

1 . High-level design choices

Concern	Option A	Option B	Option C	Recommendation (why)
North-bound API	REST (FastAPI)	GraphQL (Strawberry)	gRPC (grpcio)	FastAPI keeps the learning curve low, is async-friendly, integrates naturally with Pydantic and background tasks.
Agent control & lifecycle	Pull — agents poll commands	Push — WebSocket/Server-Sent Events	Side-channel (Redis Pub/Sub)	Pull is simpler, works through proxies & firewalls, and allows elastic scaling.
Request queue	asyncio.Queue in-process	Redis Streams	RabbitMQ / Kafka	Redis Streams give durability, replay, and support for multiple consumer groups without operating Kafka’s footprint.
Worker execution	FastAPI background tasks (threads)	Celery / Dramatiq processes	Arq / RQ async workers	Arq (async, Redis) keeps a single broker (Redis) and fits well with FastAPI’s async story.
Plug-in mechanism for workers	importlib.metadata entry-points	Yaml-listed paths auto-imported	Pydantic-based configuration objects	Entry-points let any pip install-ed package register a worker without touching central code.
State store	In-memory	PostgreSQL	MongoDB	PostgreSQL (async driver asyncpg) to persist applications, users, correlation between requests & findings.
Observability	logging only	OpenTelemetry traces + metrics	Prometheus + Grafana + Loki	Start with structured logging and OpenTelemetry stubs; upgrade to Prometheus once load grows.
The remaining guide follows the A-B-A-B path (FastAPI + Redis Streams + Arq + entry-points + PostgreSQL).

2 . Project layout
pgsql
Copy
Edit
pentest-hub/
├─ app/
│  ├─ main.py              # FastAPI bootstrap
│  ├─ api/                 # REST routes & Pydantic schemas
│  │   ├─ v1.py
│  │   └─ deps.py          # auth & DI helpers
│  ├─ core/
│  │   ├─ config.py        # Pydantic-settings, env loading
│  │   ├─ logging.py
│  │   └─ registry.py      # dynamic worker/plugin registry
│  ├─ domain/
│  │   ├─ models.py        # SQLAlchemy (async) ORM – Application, AppUser, Request, Finding
│  │   └─ schemas.py       # external ⇆ internal DTOs
│  ├─ services/
│  │   ├─ agent_manager.py # start/stop agents, track heartbeats
│  │   ├─ queues.py        # thin Redis Stream wrapper
│  │   ├─ enrichment.py    # RequestEnrichmentWorker base
│  │   └─ attack.py        # AttackWorker base & built-ins
│  ├─ workers/
│  │   ├─ enricher_default.py
│  │   └─ attack_authz.py  # wraps the long AuthzTester from the prompt
│  └─ tests/
│      ├─ unit/
│      └─ integration/
└─ pyproject.toml
3 . Core domain primitives
3.1 AppUser
python
Copy
Edit
# app/domain/models.py
class Role(str, enum.Enum):
    REGULAR = "regular"
    COLLABORATOR = "collaborator"
    ADMIN = "admin"

class AppUser(SQLModel, table=True):                 # persisted
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="application.id")
    username: str
    role: Role
    session: Json                            # serialized AuthSession
AppUser is passed to workers without ORM baggage by a light DTO:

python
Copy
Edit
# app/domain/schemas.py
class UserCtx(BaseModel):
    id: UUID
    role: Role
    username: str
    session: AuthSession | None = None
3.2 Base worker interfaces
python
Copy
Edit
# app/services/enrichment.py
class RequestEnrichmentWorker(abc.ABC):
    name: str

    @abc.abstractmethod
    async def enrich(
        self, request: HTTPRequest, user: UserCtx
    ) -> tuple[HTTPRequest, list[ResourceLocator]]:
        ...

# app/services/attack.py
class AttackWorker(abc.ABC):
    name: str
    consumes: set[str]               # names of enrichment workers whose output you can handle

    @abc.abstractmethod
    async def ingest(
        self,
        *,
        user: UserCtx,
        request: HTTPRequestData,
        resource_locators: Sequence[ResourceLocator],
    ) -> None:
        ...
Dynamic registration
python
Copy
Edit
# app/core/registry.py
_WORKERS: dict[str, type[AttackWorker]] = {}
_ENRICHERS: dict[str, type[RequestEnrichmentWorker]] = {}

def register_enricher(cls: type[RequestEnrichmentWorker]):
    _ENRICHERS[cls.name] = cls
    return cls

def register_attacker(cls: type[AttackWorker]):
    _WORKERS[cls.name] = cls
    return cls

def sanity_check():
    #  ensure every enricher has ≥1 consumer
    all_consumed = {n for w in _WORKERS.values() for n in w.consumes}
    missing = set(_ENRICHERS) - all_consumed
    if missing:
        raise RuntimeError(
            f"No AttackWorker declared for EnrichmentWorker(s): {', '.join(missing)}"
        )
Plugins simply decorate themselves:

python
Copy
Edit
# app/workers/attack_authz.py
@registry.register_attacker
class AuthzAttackWorker(AttackWorker):
    name = "authz"
    consumes = {"default-enricher"}

    async def ingest(...):
        ...
The sanity check is executed once in app/main.py before the API starts accepting traffic.

4 . Queues & background execution
python
Copy
Edit
# app/services/queues.py
class Stream(str, enum.Enum):
    RAW = "http_raw"
    ENRICHED = "http_enriched"

class Queue:
    def __init__(self, redis: redis.asyncio.Redis):
        self.redis = redis

    async def publish(self, stream: Stream, data: dict):
        await self.redis.xadd(stream.value, data)

    async def listen(self, stream: Stream, group: str, consumer: str):
        # simplified: create group if absent, then loop forever
        await self.redis.xgroup_create(stream.value, group, id="$", mkstream=True)
        while True:
            messages = await self.redis.xreadgroup(
                group, consumer, streams={stream.value: ">"}, count=100, block=5_000
            )
            for key, msgs in messages:
                for msg_id, fields in msgs:
                    yield msg_id, fields
arq workers subscribe to the Redis stream and await events. They run outside the FastAPI process:

python
Copy
Edit
# workers/enricher_default.py
@registry.register_enricher
class DefaultEnricher(RequestEnrichmentWorker):
    name = "default-enricher"

    async def enrich(self, request, user):
        locators = []  # parse request to build ResourceLocator list
        # …
        return request, locators
Worker process entry point
python
Copy
Edit
# worker_entry.py
class EnrichJob:
    async def __call__(self, ctx, raw_event: dict):
        req = HTTPRequest.from_json(raw_event["payload"])
        user = UserCtx.model_validate_json(raw_event["user"])
        enricher = registry._ENRICHERS[raw_event["enricher"]]()
        new_req, locs = await enricher.enrich(req, user)
        await ctx["queue"].publish(Stream.ENRICHED, {
            "payload": new_req.to_json(),
            "locators": json.dumps([l.__dict__ for l in locs]),
            "user": raw_event["user"],
        })

class AttackJob:
    async def __call__(self, ctx, enriched_event: dict):
        user = UserCtx.model_validate_json(enriched_event["user"])
        locators = [ResourceLocator(**d) for d in json.loads(enriched_event["locators"])]
        attacker_cls = registry._WORKERS[ctx["worker_name"]]
        attacker = attacker_cls()
        await attacker.ingest(
            user=user,
            request=HTTPRequestData(**enriched_event["payload"]),
            resource_locators=locators,
        )

settings = Settings()  # loads Redis URL

def startup(ctx):
    ctx["queue"] = Queue(aioredis.from_url(settings.redis_url))
arq’s WorkerSettings lists EnrichJob once per configured enricher and one AttackJob per AttackWorker.

5 . FastAPI layer
5.1 Application bootstrap
python
Copy
Edit
# app/main.py
app = FastAPI(title="Pentest Hub")
registry.sanity_check()                          # 🔑 mismatch guard

@app.on_event("startup")
async def _startup():
    state.redis = redis.asyncio.from_url(settings.redis_url)
    state.queue = Queue(state.redis)
    state.db = AsyncSession(engine)

@app.on_event("shutdown")
async def _shutdown():
    await state.redis.aclose()
    await engine.dispose()
5.2 Key endpoints (v1)
python
Copy
Edit
# app/api/v1.py
router = APIRouter(prefix="/v1")

class InitAppBody(BaseModel):
    name: str
    users: list[UserCtx]

@router.post("/applications", status_code=201)
async def init_application(body: InitAppBody, db=Depends(get_db)):
    app_row = Application(name=body.name)
    db.add(app_row)
    await db.flush()

    for u in body.users:
        db.add(AppUser(**u.model_dump(), application_id=app_row.id))
    await db.commit()
    return {"id": app_row.id}

class RawRequestBody(BaseModel):
    app_id: UUID
    user_id: UUID
    request: dict   # JSON serialised HTTPRequest

@router.post("/traffic")
async def ingest_traffic(body: RawRequestBody, q=Depends(get_queue)):
    await q.publish(Stream.RAW, {
        "payload": json.dumps(body.request),
        "user": json.dumps({"id": body.user_id}),
        "enricher": "default-enricher",
    })
    return {"status": "queued"}
6 . Putting the supplied AuthzTester to work
Create a thin adapter:

python
Copy
Edit
# app/workers/attack_authz.py
@registry.register_attacker
class AuthzAttackWorker(AttackWorker):
    name = "authz"
    consumes = {"default-enricher"}

    def __init__(self):
        self.tester = AuthzTester()

    async def ingest(self, *, user, request, resource_locators, session=None):
        # AuthzTester expects **sync** - wrap with anyio.to_thread if heavy
        self.tester.ingest(
            user=user.username,
            request=request,
            resource_locators=resource_locators,
            session=session,
        )
7 . Configuration & environment
python
Copy
Edit
# app/core/config.py
class Settings(BaseSettings):
    postgres_dsn: PostgresDsn
    redis_url: RedisDsn
    agent_binary: str = "/opt/agent/bin/run"

    class Config:
        env_file = ".env"
8 . Testing strategy

Layer	Tooling	Example
Pure functions (planner, template mutation)	pytest	tests/unit/test_planner.py
FastAPI routes	pytest-asyncio + httpx.AsyncClient	tests/integration/test_api.py
Worker interaction	Spin up Redis via docker-compose; feed RAW event and assert ENRICHED appears	tests/integration/test_stream.py
Mock the heavy AuthzTester network calls with respx.

9 . Operational notes & good practices
Back-pressure – Redis Streams’ maxlen≈10 000 prevents unbounded growth. Expose /healthz returning queue depths.

Idempotency – event IDs (Redis XAID) let workers retry safely (mark as processed in DB).

Observability – produce OpenTelemetry spans: ingest → enrich → attack.

Security – all agent <-> server traffic goes through HTTPS with short-lived PAT tokens per agent instance.

Scalability – workers are horizontal-scale; FastAPI stays stateless.

You now have:
A pluggable FastAPI control plane

Durable pipelines (Redis Streams → Arq)

Clear contracts (HTTPRequest, UserCtx, ResourceLocator)

Compile-time safety via Pydantic + mypy

A guard that ensures every enrichment output has at least one consumer

Use this skeleton to evolve richer workers, deeper analytics, and additional API scopes (findings export, live metrics, etc.).

ADDENUM:

Below is a rewritten implementation guide that retains everything from the previous version that is still correct while applying your three new requirements:

AttackWorker now consumes a generic AttackData object (no direct resource_locators).

The Redis Streams dependency is removed — a light-weight, thread-safe in-process queue is used instead.

Executable test-cases are defined first and each major section reminds the implementer that the code in that section must satisfy the referenced tests.

0 . Test-cases (write these first)
python
Copy
Edit
"""
tests/unit/test_pipeline.py
All new / modified features MUST satisfy these tests.
Run with:  pytest -q
"""
import asyncio, threading, time
from uuid import uuid4
from app.domain.schemas import UserCtx, AttackData
from app.services.eventbus import EventBus
from app.services.enrichment import RequestEnrichmentWorker
from app.services.attack import AttackWorker
from app.core.registry import register_enricher, register_attacker, sanity_check
from app.protocol import HTTPRequestData, ResourceLocator, RequestPart

# ---------------------------------------------------------------------------
# 1. Registry sanity check ---------------------------------------------------
def test_sanity_guard_raises_for_unconsumed_enricher(monkeypatch):
    class DummyEnricher(RequestEnrichmentWorker):
        name = "dummy-e"
        async def enrich(self, req, user): ...
    register_enricher(DummyEnricher)

    # Monkey-patch registry so there is NO attacker that consumes dummy-e
    with pytest.raises(RuntimeError):
        sanity_check()

# ---------------------------------------------------------------------------
# 2. AttackData construction -------------------------------------------------
def test_attackdata_roundtrip():
    req = HTTPRequestData(
        method="GET", url="http://t", headers={}, post_data=None,
        redirected_from_url=None, redirected_to_url=None, is_iframe=False
    )
    loc = ResourceLocator(id="X", request_part=RequestPart.URL, type_name="doc")
    data = AttackData(request=req, locators=[loc])
    assert data.locators[0].id == "X"
    assert data.request.url == "http://t"

# ---------------------------------------------------------------------------
# 3. End-to-end queue --------------------------------------------------------
async def _producer(bus, data):
    await bus.publish_raw(data)

async def _consumer(bus, results):
    async for ev in bus.consume_raw():
        results.append(ev); break

def test_inprocess_queue():
    bus = EventBus()
    data = {"msg": "hi"}
    results = []
    loop = asyncio.new_event_loop()
    t1 = threading.Thread(target=loop.run_until_complete, args=(_producer(bus, data),))
    t2 = threading.Thread(target=loop.run_until_complete, args=(_consumer(bus, results),))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results and results[0]["msg"] == "hi"
Every code fragment in later sections that touches these areas must compile and make this test-suite pass.

1 . High-level design choices (revisited)

Concern	Option Decided	Justification (unchanged text kept)
North-bound API	FastAPI (REST)	same as before
Agent control	Pull model	same
Queue / bus	In-process asyncio.Queue + thread-safe wrapper	New: avoids Redis; simple to run in CI & unit tests
Worker execution	concurrent.futures.ThreadPoolExecutor (or plain threads)	keeps GIL impact low; no external broker
Plug-in mechanism	importlib.metadata entry-points	same
State store	PostgreSQL	same
Observability	structured logging + OpenTelemetry stubs	same
2 . Directory layout (unchanged except new file paths marked ★)
arduino
Copy
Edit
pentest-hub/
├─ app/
│  ├─ main.py
│  ├─ api/
│  ├─ core/
│  ├─ domain/
│  ├─ protocol/               ★ common DTOs moved here
│  │   └─ __init__.py
│  ├─ services/
│  │   ├─ eventbus.py         ★ in-process queue abstraction
│  │   ├─ enrichment.py
│  │   └─ attack.py
│  ├─ workers/
│  └─ tests/
3 . Core protocol objects (new AttackData)
python
Copy
Edit
# app/protocol/__init__.py
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID
from .http import HTTPRequestData, ResourceLocator   # existing DTOs

@dataclass(slots=True, frozen=True)
class AttackData:
    """
    Generic payload delivered to any AttackWorker.
    Extra analysis information can be attached later without
    changing the workers’ public signature.
    """
    request: HTTPRequestData
    locators: Sequence[ResourceLocator]
    correlation_id: UUID | None = None
4 . Event bus – in-process & thread-safe (replaces Redis Streams)
python
Copy
Edit
# app/services/eventbus.py
import asyncio, threading
from collections import deque
from typing import Any

class _ThreadSafeDeque:
    """Minimal blocking queue usable from both asyncio & threads."""
    def __init__(self):                    # FIFO
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

    async def consume_raw(self):
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, self._raw.get, 1.0)
            if item is not None:
                yield item

    async def consume_enriched(self):
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, self._enriched.get, 1.0)
            if item is not None:
                yield item
You must use this EventBus in place of Redis Streams.
The queue test (#3) at the top ensures thread-safety and basic publish/consume semantics.

5 . Worker base classes (resource_locators ⇒ AttackData)
python
Copy
Edit
# app/services/enrichment.py
from app.protocol import AttackData

class RequestEnrichmentWorker(abc.ABC):
    name: str

    @abc.abstractmethod
    async def enrich(
        self, request: HTTPRequest, user: UserCtx
    ) -> AttackData:
        """
        MUST return an AttackData instance.
        Test-case: implementers must ensure locators are preserved (test #2).
        """
python
Copy
Edit
# app/services/attack.py
from app.protocol import AttackData

class AttackWorker(abc.ABC):
    name: str
    consumes: set[str]  # names of enrichment workers

    @abc.abstractmethod
    async def ingest(self, *, user: UserCtx, data: AttackData) -> None:
        ...
6 . Dynamic registration & guard (unchanged interface, new guard logic)
python
Copy
Edit
# app/core/registry.py
# … previous code …

def sanity_check():
    produced = set(_ENRICHERS)
    consumed = {e for w in _WORKERS.values() for e in w.consumes}
    missing = produced - consumed
    if missing:
        raise RuntimeError(
            "No AttackWorker consumes output of: " + ", ".join(sorted(missing))
        )
This satisfies test #1.

7 . Background loop implementation without Redis
Worker threads subscribe to the EventBus. The pattern is:

python
Copy
Edit
# worker_entry.py
import asyncio, threading, concurrent.futures
from app.services.eventbus import EventBus
from app.core import registry
from app.services import enrichment, attack

bus = EventBus()
THREADS = 4
pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)

async def _run_enrichers():
    async for ev in bus.consume_raw():
        enl_cls = registry._ENRICHERS[ev["enricher"]]
        user = UserCtx.model_validate_json(ev["user"])
        req = HTTPRequest.from_json(ev["payload"])
        data = await enl_cls().enrich(req, user)
        await bus.publish_enriched(
            {"user": ev["user"], "data": data}   # AttackData is JSON-serialisable
        )

async def _run_attackers():
    async for ev in bus.consume_enriched():
        data: AttackData = ev["data"]
        user = UserCtx.model_validate_json(ev["user"])
        for aw_cls in registry._WORKERS.values():
            if ev["producer"] in aw_cls.consumes:
                # dispatch on pool to keep separation from event loop
                asyncio.get_running_loop().run_in_executor(
                    pool, asyncio.run, aw_cls().ingest(user=user, data=data)
                )

def start_background():
    asyncio.run(asyncio.gather(_run_enrichers(), _run_attackers()))
8 . Using AuthzAttackWorker with AttackData
python
Copy
Edit
@register_attacker
class AuthzAttackWorker(AttackWorker):
    name = "authz"
    consumes = {"default-enricher"}

    def __init__(self):
        self.tester = AuthzTester()

    async def ingest(self, *, user: UserCtx, data: AttackData):
        self.tester.ingest(
            user=user.username,
            request=data.request,
            resource_locators=data.locators,
            session=user.session,
        )
9 . FastAPI layer (unchanged, except queue injection)
python
Copy
Edit
# app/api/v1.py   – excerpt
@router.post("/traffic")
async def ingest_traffic(body: RawRequestBody, bus=Depends(get_bus)):
    await bus.publish_raw({
        "payload": json.dumps(body.request),
        "user": json.dumps({"id": body.user_id}),
        "enricher": "default-enricher",
    })
    return {"status": "queued"}
Where get_bus is:

python
Copy
Edit
def get_bus():
    return app.state.bus
and initialised in app/main.py:

python
Copy
Edit
@app.on_event("startup")
async def _startup():
    app.state.bus = EventBus()
10 . Testing strategy (updated)
The three tests shown in §0 are mandatory.
Add your previous unit/integration tests; they are still valid because public contracts retained their meaning.

Use pytest-asyncio for coroutine tests.

Use pytest-xdist -n auto to reveal accidental race conditions.

✅ Summary of what changed

Area	Old	New
Data delivered to AttackWorker	(request, resource_locators)	AttackData dataclass
Queue implementation	Redis Streams	In-process thread-safe queue
Tests	none in guide	Three pytest tests at top
Registry guard	unchanged concept	guard logic + test
Authz example	accepted locators directly	converts from AttackData
Everything else (directory layout, FastAPI endpoints, plugin system, persistence, observability) remains exactly as before.

Implementers: build the features in the order of the tests above – tests first, code next – and make sure the full suite passes before moving on.

# INSTALLING PIP PACKAGES
Use `uv pip`. You are in an uv environment