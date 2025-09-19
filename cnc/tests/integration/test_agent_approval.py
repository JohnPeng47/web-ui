import asyncio
import os
import importlib

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def _set_manual_flag(value: bool):
    # Reload constants module to apply flag change for test
    import common.constants as constants
    constants.MANUAL_APPROVAL_EXPLOIT_AGENT = value
    importlib.reload(constants)


async def _create_engagement(client: AsyncClient) -> str:
    resp = await client.post(
        "/engagement/",
        json={
            "name": "Approval Flow Test",
            "base_url": "http://example.test/",
            "description": "",
            "scopes_data": ["http://example.test/api"],
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


async def _register_discovery_agent(client: AsyncClient, engagement_id: str) -> str:
    resp = await client.post(
        f"/engagement/{engagement_id}/agents/discovery/register",
        json={
            "max_steps": 1,
            "model_name": "gpt-4o-mini",
            "model_costs": 0.0,
            "log_filepath": "",
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _fake_page_observations_payload():
    # Minimal synthetic page data that triggers detection after one page step
    page = {
        "url": "http://example.test/",
        "http_msgs": [
            {
                "request": {
                    "data": {
                        "method": "GET",
                        "url": "http://example.test/",
                        "headers": {},
                        "post_data": None,
                        "redirected_from_url": None,
                        "redirected_to_url": None,
                        "is_iframe": False,
                    }
                },
                "response": {
                    "data": {
                        "url": "http://example.test/",
                        "status": 200,
                        "headers": {"content-type": "text/html"},
                        "is_iframe": False,
                        "body": None,
                        "body_error": None,
                    }
                },
            }
        ],
    }
    return [page]


async def _post_page_data_and_trigger(client: AsyncClient, agent_id: str):
    payload = {
        "agent_id": agent_id,
        "steps": 1,
        "max_steps": 1,
        "page_steps": 2,
        "max_page_steps": 2,
        "page_data": _fake_page_observations_payload(),
    }
    resp = await client.post(f"/agents/{agent_id}/page-data", json=payload)
    assert resp.status_code == 200
    return resp.json()


async def _list_agents(client: AsyncClient, engagement_id: str):
    resp = await client.get(f"/engagement/{engagement_id}/agents")
    assert resp.status_code == 200
    return resp.json()


async def _find_latest_exploit(agents):
    for a in agents:
        if a["agent_type"] == "exploit":
            return a
    return None


async def test_manual_approval_flow(test_app_client: AsyncClient):
    await _set_manual_flag(True)

    client = test_app_client
    engagement_id = await _create_engagement(client)
    disc_agent_id = await _register_discovery_agent(client, engagement_id)

    # Trigger detection which registers an exploit agent but does not start it
    await _post_page_data_and_trigger(client, disc_agent_id)

    # List agents and find the exploit agent
    agents = await _list_agents(client, engagement_id)
    agent = await _find_latest_exploit(agents)
    assert agent is not None
    assert agent["agent_status"] == "pending_approval"

    agent_id = agent["id"]

    # Approve the exploit agent
    approve_resp = await client.post(
        f"/agents/{agent_id}/approval", 
        json={"agent_id": agent_id, "approve_data": True}
    )
    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["status"] in ("running",)

# TODO: need to introduce setting MANUAL_TESTING_FLAG
# async def test_auto_mode_flow(test_app_client: AsyncClient):
#     await _set_manual_flag(False)

#     client = test_app_client
#     engagement_id = await _create_engagement(client)
#     disc_agent_id = await _register_discovery_agent(client, engagement_id)

#     # Trigger detection which should auto-start exploit agent
#     await _post_page_data_and_trigger(client, disc_agent_id)
#     agents = await _list_agents(client, engagement_id)
#     exploit = await _find_latest_exploit(agents)
#     assert exploit is not None

#     # In auto mode, exploit agent should not be pending approval
#     assert exploit["agent_status"] in ("pending_auto", "running", "completed")


