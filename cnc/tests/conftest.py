import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from uuid import uuid4, UUID

import httpx
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