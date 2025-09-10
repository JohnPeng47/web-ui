import asyncio
import uuid
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,          # preferred helper in SQLAlchemy 2.0+
)
from typing import AsyncGenerator

# ── App-side imports ──────────────────────────────────────────────────────────
from cnc.main import create_app
from cnc.database.session import override_db, create_db_and_tables, engine
from cnc.schemas.http import EnrichedRequest
from cnc.main import start_all

from cnc.pools.discovery_agent_pool import start_discovery_agent as start_discovery_pool
from src.agent.discovery.min_agent_single_page import MinimalAgentSinglePage

from httplib import (
    ResourceLocator, 
    RequestPart,
    HTTPMessage, 
    HTTPRequest, 
    HTTPResponse, 
    HTTPRequestData, 
    HTTPResponseData
)


@pytest.fixture
def test_app_data():
    """Test application data for creating a new app."""
    return {
        "name": f"Test App {uuid.uuid4()}",
        "description": "Test application for integration tests"
    }


@pytest.fixture
def test_agent_data():
    """Test agent data for registering a new agent."""
    return {
        "user_name": f"test_user_{uuid.uuid4()}",
        "role": "tester"
    }


@pytest.fixture
def test_http_message():    
    request_data = HTTPRequestData(
        method="GET",
        url="https://example.com/api/v1/users/123",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cookie": "sessionid=abc123"
        },
        is_iframe=False
    )
    
    response_data = HTTPResponseData(
        url="https://example.com/api/v1/users/123",
        status=200,
        headers={
            "Content-Type": "application/json"
        },
        is_iframe=False,
    )
    
    return HTTPMessage(
        request=HTTPRequest(data=request_data),
        response=HTTPResponse(data=response_data)
    ).model_dump(mode="json")

@pytest.fixture
def test_enriched_requests():    
    request_data1 = HTTPRequestData(
        method="GET",
        url="https://example.com/api/v1/users/123",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cookie": "sessionid=abc123"
        },
        is_iframe=False
    )
    http_request1 = HTTPRequest(data=request_data1)
    
    request_data2 = HTTPRequestData(
        method="POST",
        url="https://example.com/api/v1/products",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Authorization": "Bearer token123"
        },
        post_data=json.loads('{"product_id": "123", "price": 10.99}'),
        is_iframe=False
    )
    http_request2 = HTTPRequest(data=request_data2)
    
    enriched_request1 = EnrichedRequest(
        request=http_request1,
        username="user1",
        role="admin",
        resource_locators=[
            ResourceLocator(id="123", request_part=RequestPart.URL, type_name="user")
        ]
    )
    enriched_request2 = EnrichedRequest(
        request=http_request2,
        username="user2",
        role="customer",
        resource_locators=[
            ResourceLocator(id="123", request_part=RequestPart.BODY, type_name="product")
        ]
    )
    
    return [enriched_request1, enriched_request2]


TEST_DB_URL = (
    "sqlite+aiosqlite:///./cnc/test_db.sqlite"  # file-based keeps the schema
)

# ── Helper: one shared *async* session maker bound to the overridden engine ───
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

# ── FIXTURE: FastAPI app + HTTPX AsyncClient on an isolated DB ────────────────
@pytest_asyncio.fixture(scope="function")
async def test_app_client() -> AsyncGenerator:
    async with override_db(TEST_DB_URL):
        await create_db_and_tables()           # schema lives on disk
        app = create_app()                     # routes import the models

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac         # hand them to the test


# ── FIXTURE: App client with background workers (auto-teardown) ───────────────
@pytest_asyncio.fixture(scope="function")
async def test_app_client_with_workers() -> AsyncGenerator[AsyncClient, None]:
    """
    Starts the browser worker and discovery agent pool tied to the same FastAPI
    app instance used by the HTTP client. All background tasks are cancelled and
    cleaned up when the fixture scope ends.
    """
    # Deferred imports to avoid test collection side-effects
    from cnc.workers.agent.browser import start_single_browser, get_browser_session

    async with override_db(TEST_DB_URL):
        await create_db_and_tables()
        app = create_app()

        # Background workers
        browser_task = asyncio.create_task(start_single_browser())
        stop_event: asyncio.Event = asyncio.Event()
        discovery_task = asyncio.create_task(
            start_discovery_pool(
                app.state.discovery_agent_queue,
                agent_cls=MinimalAgentSinglePage
            )
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            try:
                yield ac
            finally:
                # Teardown workers
                stop_event.set()
                for t in (discovery_task, browser_task):
                    if not t.done():
                        t.cancel()
                # Await cancellations without raising
                for t in (discovery_task, browser_task):
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass

# @pytest_asyncio.fixture(scope="function")
# async def test_ () -> AsyncGenerator:
#     async with override_db(TEST_DB_URL):
#         await create_db_and_tables()           # schema lives on disk
#         app = create_app()                     # routes import the models

#         transport = ASGITransport(app=app)
#         async with AsyncClient(transport=transport, base_url="http://test") as ac:
#             yield ac         # hand them to the test


