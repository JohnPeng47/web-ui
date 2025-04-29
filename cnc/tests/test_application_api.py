import pytest
from httpx import AsyncClient
import uuid
from typing import Dict

pytestmark = pytest.mark.asyncio


async def test_create_application(test_client: AsyncClient, test_app_data: Dict):
    """Test creating a new application."""
    response = await test_client.post("/application/", json=test_app_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_app_data["name"]
    assert data["description"] == test_app_data["description"]
    assert "id" in data
    assert "created_at" in data


async def test_get_application(test_client: AsyncClient, test_app_data: Dict):
    """Test retrieving an application by ID."""
    # First create an application
    create_response = await test_client.post("/application/", json=test_app_data)
    assert create_response.status_code == 200
    app_id = create_response.json()["id"]
    
    # Now try to retrieve it
    get_response = await test_client.get(f"/application/{app_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == app_id
    assert data["name"] == test_app_data["name"]


async def test_get_nonexistent_application(test_client: AsyncClient):
    """Test retrieving a non-existent application."""
    random_id = str(uuid.uuid4())
    response = await test_client.get(f"/application/{random_id}")
    assert response.status_code == 404


async def test_register_agent(test_client: AsyncClient, test_app_data: Dict, test_agent_data: Dict):
    """Test registering an agent for an application."""
    # First create an application
    create_response = await test_client.post("/application/", json=test_app_data)
    assert create_response.status_code == 200
    app_id = create_response.json()["id"]
    
    # Register an agent
    register_response = await test_client.post(
        f"/application/{app_id}/agents/register", 
        json=test_agent_data
    )
    assert register_response.status_code == 200
    data = register_response.json()
    assert data["user_name"] == test_agent_data["user_name"]
    assert data["role"] == test_agent_data["role"]
    assert data["application_id"] == app_id
    assert "id" in data
    assert "created_at" in data


async def test_push_messages(
    test_client: AsyncClient, 
    test_app_data: Dict, 
    test_agent_data: Dict,
    test_http_message: Dict
):
    """Test pushing HTTP messages through an agent."""
    # Create application
    create_response = await test_client.post("/application/", json=test_app_data)
    app_id = create_response.json()["id"]
    
    # Register agent
    register_response = await test_client.post(
        f"/application/{app_id}/agents/register", 
        json=test_agent_data
    )
    agent_data = register_response.json()
    
    # Push messages
    push_response = await test_client.post(
        f"/application/{app_id}/agents/push",
        json={"messages": [test_http_message]},
        headers={
            "X-Username": test_agent_data["user_name"],
            "X-Role": test_agent_data["role"]
        }
    )
    
    assert push_response.status_code == 202
    data = push_response.json()
    assert data["accepted"] == 1


async def test_push_messages_unauthorized(
    test_client: AsyncClient, 
    test_app_data: Dict,
    test_http_message: Dict
):
    """Test pushing messages with an unregistered agent."""
    # Create application
    create_response = await test_client.post("/application/", json=test_app_data)
    app_id = create_response.json()["id"]
    
    # Push messages without registering first
    push_response = await test_client.post(
        f"/application/{app_id}/agents/push",
        json={"messages": [test_http_message]},
        headers={
            "X-Username": "unregistered_user",
            "X-Role": "unknown"
        }
    )
    
    assert push_response.status_code == 401