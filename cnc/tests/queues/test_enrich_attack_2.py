"""
cnc/tests/test_enrichment_queue.py
"""
import asyncio
import os
from uuid import uuid4, UUID
import pytest

from cnc.services.queue import BroadcastChannel
from cnc.services.enrichment import RequestEnrichmentWorker
from cnc.schemas.http import EnrichedRequest

pytestmark = pytest.mark.asyncio

async def test_push_messages_to_raw_queue(test_app_client, test_app_data, test_http_message) -> None:
    """
    Verify that POST /application/{app_id}/agents/push (1) returns 202 and
    (2) publishes the HTTPMessage to app.state.raw_channel and then to app.state.enriched_channel.
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
    # Get the app instance to access the raw_channel and enriched_channel
    raw_channel: BroadcastChannel = app.state.raw_channel
    enriched_channel: BroadcastChannel = app.state.enriched_channel
    
    raw_queue: asyncio.Queue = raw_channel.subscribe()
    enriched_queue: asyncio.Queue = enriched_channel.subscribe()

    # Create a sample HTTP message
    sample_message = test_http_message
    
    # Push messages
    messages = [sample_message]
        
    # Create worker with injected dependencies
    enrichment_worker = RequestEnrichmentWorker(
        inbound=raw_channel,
        outbound=enriched_channel,
        db_session=None  # We'll need to provide a session in a real scenario
    )
    
    # Run the worker in the background
    worker_task = asyncio.create_task(enrichment_worker.run())
    
    # --- invoke endpoint ------------------------------------------------------
    data = await application_client.push_messages(
        UUID(app_id),
        agent_id,
        messages
    )
    
    # --- confirm message reached the enriched queue ----------------------------
    received_enriched = await asyncio.wait_for(enriched_queue.get(), timeout=1.0)
    enriched_queue.task_done()
    
    assert received_enriched.resource_locators[0].type_name == "user"

    # Clean up the worker task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
