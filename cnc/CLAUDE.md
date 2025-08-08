0 . Executive Overview
You’ll be building a hub-and-spoke FastAPI service that (a) receives traffic crawled by many independent “browser agents”, (b) stores it, (c) fan-outs that traffic to enrichment workers, and (d) fan-ins the enriched stream to one-or-more attack workers (starting with AuthzAttacker). Everything is 100 % async, entirely in-memory for queues, and SQLite for persistence (easily swappable behind a repo-pattern façade).

1 . High-level Component Map

Layer	Main Pieces	Key Responsibilities
API / HTTP	routers/application.py, routers/agent.py	REST endpoints, request validation (Pydantic), dependency injection (DI) for DB & queues
Service	services/application.py, services/agent.py, services/queue.py, services/enrichment.py, services/attack.py	Pure business logic; orchestrates DB + helpers; no FastAPI imports
DB	database/models.py, database/crud.py, database/session.py	SQLModel / SQLAlchemy models & CRUD
Helpers	helpers/uuid.py, helpers/queue.py	Small, stateless utilities; e.g., in-memory pub/sub queue
Workers (async tasks)	workers/request_enrichment.py, workers/authz_attacker.py	Subscribe to queues, perform CPU / I/O work, re-publish
Tests	tests/	Harness w/ temp-file SQLite + lifespan ctx-mgr; Pytest-asyncio
Entry Points	main.py, workers_launcher.py	Initialise queues, DB, FastAPI, run workers
2 . Data Shapes (Pydantic)
python
Copy
Edit
# schemas/http.py
class HTTPRequestData(BaseModel):
    method: str
    url: HttpUrl
    headers: Dict[str, str]
    post_data: Optional[Dict[str, Any]] = None
    redirected_from_url: Optional[HttpUrl] = None
    redirected_to_url: Optional[HttpUrl] = None
    is_iframe: bool = False

class HTTPResponseData(BaseModel):
    url: HttpUrl
    status: PositiveInt
    headers: Dict[str, str]
    is_iframe: bool
    body_b64: Optional[str] = None          # keep binary safe
    body_error: Optional[str] = None

class HTTPMessage(BaseModel):
    request: HTTPRequestData
    response: Optional[HTTPResponseData] = None
Additional schemas: ApplicationCreate, AgentRegister, PushMessages, etc.

3 . Queues – Minimal In-Memory Pub/Sub
python
Copy
Edit
# helpers/queue.py
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
Queue registry (singleton DI):

python
Copy
Edit
# services/queue.py
class QueueRegistry:
    def __init__(self):
        self.channels: Dict[str, Channel[Any]] = defaultdict(Channel)

    def get(self, name: str) -> Channel[Any]:
        return self.channels[name]

queues = QueueRegistry()      # import-able singleton
Standard channels


Name	Payload	Producer	Consumer
raw_http_msgs	HTTPMessage	/agents/push route	RequestEnrichmentWorker
enriched_requests_authz	EnrichedRequest	enrichment worker	AuthzAttackerWorker
Workers accept pub_queue_id & sub_queue_id at init so they can be wired from workers_launcher.py.

4 . Service Contracts
python
Copy
Edit
# services/enrichment.py
class BaseRequestEnrichmentWorker(ABC):
    def __init__(self, *, sub_queue_id: str, pub_queue_id: str): ...
    @abstractmethod
    async def run(self): ...

# concrete
class SimpleEnrichmentWorker(BaseRequestEnrichmentWorker):
    async def run(self):
        sub_q = queues.get(self.sub_id).subscribe()
        pub_ch = queues.get(self.pub_id)
        while True:
            msg: HTTPMessage = await sub_q.get()
            enr = await self._enrich(msg)          # auth/session detection, etc.
            await pub_ch.publish(enr)
python
Copy
Edit
# services/attack.py
class BaseAttackWorker(ABC):
    queue_id: str = ...
    @abstractmethod
    async def ingest(
        self,
        request: HTTPRequestData,
        username: str,
        role: str,
        session: Optional["AuthSession"] = None,
    ): ...

class AuthzAttacker(BaseAttackWorker):
    queue_id = "enriched_requests_authz"
    async def run(self):
        sub_q = queues.get(self.queue_id).subscribe()
        while True:
            enr = await sub_q.get()
            await self.ingest(**self._explode(enr))
5 . FastAPI Routers (excerpt)
python
Copy
Edit
router = APIRouter(prefix="/application")

@router.post("/", response_model=ApplicationOut)
async def create_app(payload: ApplicationCreate, db: Session = Depends(get_db)):
    app = services.application.create_app(db, payload)
    return app

@router.post("/{app_id}/agents/register", response_model=AgentOut)
async def register_agent(app_id: UUID, payload: AgentRegister, db=Depends(get_db)):
    agent = services.agent.register(db, app_id, payload)
    return agent

@router.post("/{app_id}/agents/push", status_code=202)
async def push_messages(
    app_id: UUID,
    payload: PushMessages,
    agent=Depends(require_registered_agent),
    db=Depends(get_db),
):
    # store in DB
    services.agent.store_messages(db, agent.id, payload.messages)
    # fan-out
    for m in payload.messages:
        await queues.get("raw_http_msgs").publish(m)
    return {"accepted": len(payload.messages)}
require_registered_agent depends on DB to check (user_name, role) exists for app_id.

6 . Lifespan & Queue Wiring
python
Copy
Edit
def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(application_router)
    ...
    return app

@asynccontextmanager
async def lifespan(app: FastAPI):
    # init db
    yield
    # graceful shutdown
workers_launcher.py

python
Copy
Edit
async def main():
    queues.get("raw_http_msgs")      # touch to create channel
    queues.get("enriched_requests_authz")

    enrich = SimpleEnrichmentWorker(
        sub_queue_id="raw_http_msgs",
        pub_queue_id="enriched_requests_authz",
    )
    authz = AuthzAttacker()

    await asyncio.gather(enrich.run(), authz.run())
7 . Testing Strategy
Test harness wraps create_app() in a pytest fixture:

python
Copy
Edit
@pytest_asyncio.fixture
async def test_client(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    async with override_db(db_url):
        async with LifespanManager(create_app()) as app:
            async with AsyncClient(app=app, base_url="http://test") as ac:
                yield ac      # db file deleted on ctx exit
Use separate memory queues or QueueRegistry(reset=True) in setup_function.

Unit-test each route; integration test pushes that a) hit DB, b) publish to queue, c) worker consumes.

8 . Suggested Directory Layout
pgsql
Copy
Edit
pentest_hub/
├── helpers/
│   ├── queue.py
│   └── uuid.py
├── database/
│   ├── models.py
│   ├── crud.py
│   └── session.py
├── schemas/
│   ├── http.py
│   └── application.py
├── services/
│   ├── queue.py
│   ├── application.py
│   ├── agent.py
│   ├── enrichment.py
│   └── attack.py
├── workers/
│   ├── request_enrichment.py
│   └── authz_attacker.py
├── routers/
│   ├── application.py
│   └── agent.py
├── tests/
│   ├── conftest.py
│   └── test_application_api.py
├── main.py
└── workers_launcher.py

You can install packages using "uv pip"