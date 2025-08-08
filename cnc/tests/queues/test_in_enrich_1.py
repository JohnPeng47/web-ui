"""
cnc/tests/test_enrichment_queue.py
"""
import asyncio
import os
from uuid import uuid4, UUID

import pytest
from cnc.services.queue import BroadcastChannel
from cnc.schemas.http import EnrichAuthNZMessage

pytestmark = pytest.mark.asyncio

async def test_push_messages_to_raw_queue(test_app_client, test_app_data, test_http_message) -> None:
    """
    Verify that POST /application/{app_id}/agents/push (1) returns 202 and
    (2) publishes the HTTPMessage to app.state.raw_channel.
    """
    application_client, app = test_app_client

    # Create an application
    app_id = await application_client.create_application(
        test_app_data["name"],
        test_app_data.get("description")
    )

    # Register an agent
    agent_data = await application_client.register_agent(UUID(app_id))
    agent_id = UUID(agent_data["id"])

    # --- subscribe BEFORE making the request ---------------------------------
    # Get the app instance to access the raw_channel
    raw_channel: BroadcastChannel = app.state.raw_channel
    queue: asyncio.Queue = raw_channel.subscribe()

    # Create a sample HTTP message
    sample_message = test_http_message
    
    # Push messages
    messages = [sample_message]
    
    # --- invoke endpoint ------------------------------------------------------
    data = await application_client.push_messages(
        UUID(app_id),
        agent_id,
        messages
    )

    assert "accepted" in data
    assert data["accepted"] == 1

    # --- confirm message reached the queue -----------------------------------
    received: EnrichAuthNZMessage = await asyncio.wait_for(queue.get(), timeout=1.0)
    queue.task_done()

    assert received.http_msg.request.url == "https://example.com/api/v1/users/123"
    # assert queue.empty()
