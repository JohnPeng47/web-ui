import pytest
from uuid import UUID
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_agent_lifecycle(test_app_client: AsyncClient):
    """Test complete agent lifecycle: register, get, upload page data, get page data."""
    application_client = test_app_client

    # Create an engagement to register the agent under
    engagement_payload = {
        "name": "Agent Test Engagement",
        "base_url": "https://agent.test",
        "description": "Engagement for agent registration test",
        "scopes_data": ["https://agent.test"]
    }
    create_resp = await application_client.post("/engagement/", json=engagement_payload)
    assert create_resp.status_code == 200
    engagement = create_resp.json()
    engagement_id = engagement["id"]

    # 1. Register a discovery agent
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

    # Basic response structure checks - AgentOut only has id field
    assert isinstance(agent.get("id"), int)
    
    agent_id = agent["id"]

    # 2. Get the agent (implicitly tested in other endpoints, but we can verify the agent exists)
    # Note: There's no explicit GET endpoint for individual agents in the router,
    # but we can verify the agent exists through the page data endpoints

    # 3. Upload page data
    page_data_payload = {
        "agent_id": agent_id,
        "page_data": [
            {
                "url": "https://agent.test/page1",
                "title": "Test Page 1",
                "content": "This is test content",
                "status_code": 200
            },
            {
                "url": "https://agent.test/page2", 
                "title": "Test Page 2",
                "content": "More test content",
                "status_code": 200
            }
        ]
    }
    upload_resp = await application_client.post(
        f"/agents/{agent_id}/page-data",
        json=page_data_payload,
    )
    assert upload_resp.status_code == 200
    updated_agent = upload_resp.json()
    assert updated_agent["id"] == agent_id

    # 4. Get the page data
    get_page_data_resp = await application_client.get(f"/agents/{agent_id}/page-data")
    assert get_page_data_resp.status_code == 200
    page_data_result = get_page_data_resp.json()
    
    assert "page_data" in page_data_result
    assert len(page_data_result["page_data"]) == 2
    assert page_data_result["page_data"][0]["url"] == "https://agent.test/page1"
    assert page_data_result["page_data"][0]["title"] == "Test Page 1"
    assert page_data_result["page_data"][1]["url"] == "https://agent.test/page2"
    assert page_data_result["page_data"][1]["title"] == "Test Page 2"

