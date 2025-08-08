import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from uuid import uuid4, UUID

import httpx
import json
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,          # preferred helper in SQLAlchemy 2.0+
)
from sqlmodel import SQLModel
from typing import Any, Dict, List, Optional, Tuple, Union, AsyncGenerator

# ── App-side imports ──────────────────────────────────────────────────────────
from src.agent.client import AgentClient
from cnc.main import create_app
from cnc.services.queue import BroadcastChannel
from cnc.database.models import Agent as AgentModel, Application
from cnc.database.session import override_db, create_db_and_tables, engine
from cnc.schemas.http import EnrichedRequest
from httplib import ResourceLocator, RequestPart

from httplib import HTTPMessage, HTTPRequest, HTTPResponse, HTTPRequestData, HTTPResponseData


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

        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield AgentClient(client=ac), app           # hand them to the test