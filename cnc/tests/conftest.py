import pytest
import pytest_asyncio
import httpx
from httpx import AsyncClient
from contextlib import asynccontextmanager
from fastapi import FastAPI
import os
import uuid

from database.session import override_db
from main import create_app


@pytest_asyncio.fixture
async def test_client(tmp_path):
    """Create a test client with a temporary database."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    
    async with override_db(db_url):
        app = create_app()
        
        # Use the app's lifespan
        async with httpx.ASGITransport(app=app) as transport:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac  # Database will be deleted on context exit


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
    """Sample HTTP message for testing."""
    return {
        "request": {
            "method": "GET",
            "url": "https://example.com/api/v1/users/123",
            "headers": {
                "User-Agent": "Mozilla/5.0",
                "Cookie": "sessionid=abc123"
            },
            "is_iframe": False
        },
        "response": {
            "url": "https://example.com/api/v1/users/123",
            "status": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "is_iframe": False,
            "body_b64": "eyJ1c2VybmFtZSI6ICJ0ZXN0X3VzZXIiLCAicm9sZSI6ICJ1c2VyIn0="  # {"username": "test_user", "role": "user"}
        }
    }