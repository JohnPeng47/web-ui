import pytest
from typing import Dict

from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_create_and_get_engagement(test_app_client: AsyncClient):
    """Create then fetch an engagement by ID."""
    application_client = test_app_client

    create_payload = {
        "name": "Fetchable Engagement",
        "base_url": "https://example.org",
        "description": "For GET test",
        "scopes_data": ["https://example.com"]
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
    assert fetched["scopes_data"] == create_payload["scopes_data"]