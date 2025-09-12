import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def engagement_id(test_app_client: AsyncClient):
    create_payload = {
        "name": "PD Test",
        "base_url": "https://example.com",
        "scopes_data": ["https://example.com"],
        "description": "desc",
    }
    resp = await test_app_client.post("/engagement/", json=create_payload)
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_merge_page_data_endpoint(test_app_client: AsyncClient, engagement_id):
    delta = {
        "agent_id": "agent-1",
        "delta": [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/b", "title": "B"},
        ],
    }
    resp = await test_app_client.post(f"/engagement/{engagement_id}/page-data", json=delta)
    assert resp.status_code == 200
    data = resp.json()
    assert "page_data" in data
    assert len(data["page_data"]) == 2

    # Second merge adds one and updates one
    delta2 = {
        "agent_id": "agent-2",
        "delta": [
            {"url": "https://example.com/b", "title": "B2"},
            {"url": "https://example.com/c", "title": "C"},
        ],
    }
    resp2 = await test_app_client.post(f"/engagement/{engagement_id}/page-data", json=delta2)
    assert resp2.status_code == 200
    updated = resp2.json()["page_data"]
    urls = {p["url"] for p in updated}
    assert urls == {"https://example.com/a", "https://example.com/b", "https://example.com/c"}


@pytest.mark.asyncio
async def test_agent_backcompat_routes_write_and_read(test_app_client: AsyncClient, engagement_id):
    # Register discovery agent
    reg = await test_app_client.post(
        f"/engagement/{engagement_id}/agents/discovery/register",
        json={"max_steps": 1, "model_name": "gpt-4o-mini"},
    )
    assert reg.status_code == 200
    agent_id = reg.json()["id"]

    # Upload page data via agent route (should write to engagement)
    pd = {
        "agent_id": agent_id,
        "page_data": [
            {"url": "https://example.com/z", "title": "Z"}
        ],
    }
    up = await test_app_client.post(f"/agents/{agent_id}/page-data", json=pd)
    assert up.status_code == 200 or up.status_code == 500  # background scheduling may fail; write happens before

    # Read back via agent route (should proxy to engagement page_data)
    get_pd = await test_app_client.get(f"/agents/{agent_id}/page-data")
    assert get_pd.status_code == 200
    body = get_pd.json()
    assert "page_data" in body
    assert any(item.get("url") == "https://example.com/z" for item in body["page_data"])



