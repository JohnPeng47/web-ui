"""
cnc/tests/test_enrichment_queue.py
"""
import asyncio
import os
from uuid import uuid4, UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,          # preferred helper in SQLAlchemy 2.0+
)
from sqlmodel import SQLModel

from cnc.main import create_app
from cnc.services.queue import BroadcastChannel
from cnc.database.models import Agent as AgentModel, Application
from cnc.database.session import override_db, create_db_and_tables, engine

from httplib import HTTPMessage, HTTPRequest, HTTPResponse, HTTPRequestData, HTTPResponseData

pytestmark = pytest.mark.asyncio

async def test_push_messages_to_raw_queue(test_app_client, test_app_data, test_http_message) -> None:
    """
    Verify that POST /application/{app_id}/agents/push (1) returns 202 and
    (2) publishes the HTTPMessage to app.state.raw_channel.
    """
    application_client, app = test_app_client

    # Create an application
    app_data = await application_client.create_application(
        test_app_data["name"],
        test_app_data.get("description")
    )
    app_id = app_data["id"]

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
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    queue.task_done()

    assert received.model_dump() == sample_message
    assert queue.empty()
