from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from typing import Dict, Any
from httplib import HTTPMessage
from schemas.http import EnrichedRequest

from routers.application import make_application_router
from routers.agent import make_agent_router
from database.session import create_db_and_tables
from services.queue import BroadcastChannel
import asyncio
from workers_launcher import start_workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Initialize database
    await create_db_and_tables()
    
    # App is now ready
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Create the FastAPI app without routers initially
    app = FastAPI(
        title="Pentest Hub",
        description="A hub-and-spoke service for pentest traffic collection and analysis",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Create broadcast channels
    raw_channel = BroadcastChannel[HTTPMessage]()
    enriched_channel = BroadcastChannel[EnrichedRequest]()
    
    # Store channels in app state for access by workers and dependencies
    app.state.raw_channel = raw_channel
    app.state.enriched_channel = enriched_channel
    
    # Create routers with injected dependencies
    application_router = make_application_router(raw_channel)
    agent_router = make_agent_router(raw_channel)
    
    # Include routers
    app.include_router(application_router)
    app.include_router(agent_router)
    
    return app

app = create_app()

async def start_api_server():
    """Start the FastAPI server using uvicorn."""
    config = uvicorn.Config("main:app", host="0.0.0.0", port=8000, reload=True)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """Start both workers and API server concurrently."""
    await asyncio.gather(
        start_workers(app),
        start_api_server()
    )

if __name__ == "__main__":
    asyncio.run(main())