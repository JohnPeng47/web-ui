import pytest
from typing import Dict

from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_create_engagement(test_app_client: AsyncClient):
    """Create a new engagement via /engagement/."""
    application_client = test_app_client

    payload = {
        "name": "Test Engagement",
        "base_url": "https://example.com",
        "description": "Integration test engagement"
    }

    response = await application_client.post("/engagement/", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["name"] == payload["name"]
    assert data["base_url"] == payload["base_url"]
    assert data["description"] == payload["description"]
    assert "id" in data
    assert "created_at" in data


async def test_get_engagement(test_app_client: AsyncClient):
    """Create then fetch an engagement by ID."""
    application_client = test_app_client

    create_payload = {
        "name": "Fetchable Engagement",
        "base_url": "https://example.org",
        "description": "For GET test"
    }
    create_resp = await application_client.post("/engagement/", json=create_payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    engagement_id = created["id"]

    get_resp = await application_client.get(f"/engagement/{engagement_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()

    assert fetched["id"] == engagement_id
    assert fetched["name"] == create_payload["name"]
    assert fetched["base_url"] == create_payload["base_url"]