import pytest
import uuid
from typing import Dict
from uuid import UUID

import httpx
from src.agent.client import AgentClient 

pytestmark = pytest.mark.asyncio

async def test_create_application(test_app_client, test_app_data: Dict):
    """Test creating a new application."""
    application_client, _ = test_app_client
    
    data = await application_client.create_application(test_app_data["name"], test_app_data["description"])
    
    assert data["name"] == test_app_data["name"]
    assert data["description"] == test_app_data["description"]
    assert "id" in data
    assert "created_at" in data


# async def test_get_application(test_app_client, test_app_data: Dict):
#     """Test retrieving an application by ID."""
#     application_client, _ = test_app_client
    
#     # First create an application
#     create_data = await application_client.create_application(
#         test_app_data["name"],
#         test_app_data.get("description")
#     )
#     app_id = create_data["id"]
    
#     # Now try to retrieve it
#     data = await application_client.get_application(UUID(app_id))
#     assert data["id"] == app_id
#     assert data["name"] == test_app_data["name"]


# async def test_get_nonexistent_application(test_app_client):
#     """Test retrieving a non-existent application."""
#     application_client, _ = test_app_client
    
#     random_id = str(uuid.uuid4())
#     response = await application_client.client.get(f"/application/{random_id}")
#     assert response.status_code == 404


async def test_register_agent(test_app_client, test_app_data: Dict):
    """Test registering an agent for an application."""
    application_client, _ = test_app_client
    
    # First create an application
    create_data = await application_client.create_application(
        test_app_data["name"],
        test_app_data.get("description")
    )
    app_id = create_data["id"]
    
    # Register an agent
    data = await application_client.register_agent(UUID(app_id))
    
    assert data["user_name"] == application_client.username
    assert data["role"] == application_client.role
    assert data["application_id"] == app_id
    assert "id" in data
    assert "created_at" in data


async def test_push_messages(
    test_app_client, 
    test_app_data: Dict, 
    test_http_message: Dict
):
    """Test pushing HTTP messages through an agent."""
    application_client, _ = test_app_client
    
    # Create application
    create_data = await application_client.create_application(
        test_app_data["name"],
        test_app_data.get("description")
    )
    app_id = create_data["id"]
    
    # Register agent
    agent_data = await application_client.register_agent(UUID(app_id))
    agent_id = UUID(agent_data["id"])
    
    # Create a sample HTTP message
    sample_message = test_http_message
    
    # Push messages
    messages = [sample_message]
    
    data = await application_client.push_messages(
        UUID(app_id),
        agent_id,
        messages
    )
    
    assert data["accepted"] == 1


async def test_push_messages_unauthorized(
    test_app_client, 
    test_app_data: Dict,
    test_http_message: Dict
):
    """Test pushing messages with an unregistered agent."""
    application_client, _ = test_app_client
    
    # Create application
    create_data = await application_client.create_application(
        test_app_data["name"],
        test_app_data.get("description")
    )
    app_id = create_data["id"]
    
    # Create a random agent ID that hasn't been registered
    random_agent_id = uuid.uuid4()
    
    # Push messages without registering first
    try:
        await application_client.push_messages(
            UUID(app_id),
            random_agent_id,
            [test_http_message]
        )
        pytest.fail("Expected HTTPStatusError for unauthorized agent")
    except httpx.HTTPStatusError as e:
        assert e.response.status_code == 401