import pytest
from uuid import UUID
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_register_discovery_agent(test_app_client: AsyncClient):
    application_client = test_app_client

    # Create an engagement to register the agent under
    engagement_payload = {
        "name": "Agent Test Engagement",
        "base_url": "https://agent.test",
        "description": "Engagement for agent registration test",
    }
    create_resp = await application_client.post("/engagement/", json=engagement_payload)
    assert create_resp.status_code == 200
    engagement = create_resp.json()
    engagement_id = engagement["id"]

    # Register a discovery agent
    agent_payload = {
        "max_steps": 5,
        "model_name": "gpt-4o-mini",
        "model_costs": 0.01,
        "log_filepath": "/tmp/agent.log",
        "agent_status": "active",
    }
    register_resp = await application_client.post(
        f"/engagement/{engagement_id}/agents/discovery/register",
        json=agent_payload,
    )
    assert register_resp.status_code == 200
    agent = register_resp.json()

    # Basic response structure checks
    assert isinstance(agent.get("id"), int)
    assert agent["agent_status"] == agent_payload["agent_status"]
    assert agent["max_steps"] == agent_payload["max_steps"]
    assert agent["model_name"] == agent_payload["model_name"]
    assert agent.get("created_at")

