import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from fastapi import status
from asgi_lifespan import LifespanManager

from app.main import app

@pytest.mark.asyncio
async def test_create_application():
    """Test creating a new application with users."""
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            response = await ac.post(
                "/v1/applications",
                json={
                    "name": "Test Application",
                    "users": [
                        {
                            "id": str(uuid.uuid4()),
                            "username": "testuser",
                            "role": "regular"
                        }
                    ]
                }
            )
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "id" in data

@pytest.mark.asyncio
async def test_ingest_traffic():
    """Test ingesting traffic into the system."""
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            # First, create an application with a user
            app_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            app_response = await ac.post(
                "/v1/applications",
                json={
                    "name": "Test Traffic App",
                    "users": [
                        {
                            "id": user_id,
                            "username": "trafficuser",
                            "role": "regular"
                        }
                    ]
                }
            )
            assert app_response.status_code == status.HTTP_201_CREATED

            # Now, ingest traffic
            response = await ac.post(
                "/v1/traffic",
                json={
                    "app_id": app_id,
                    "user_id": user_id,
                    "request": {
                        "method": "GET",
                        "url": "http://example.com",
                        "headers": {"User-Agent": "Test Browser"}
                    }
                }
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "queued"