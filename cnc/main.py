import asyncio
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from logger import setup_server_logger
from cnc.workers_launcher import start_workers

from cnc.schemas.http import EnrichedRequest, EnrichAuthNZMessage
from cnc.services.queue import BroadcastChannel

from cnc.database.session import create_db_and_tables
from cnc.routers.engagement import make_engagement_router
from cnc.routers.agent import make_agent_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Initialize database
    await create_db_and_tables()
    
    # App is now ready
    yield

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # configure_relationships() # Ensure it's called if not called at module level

    print("Creating FastAPI app...")
    
    # Create the FastAPI app without routers initially
    app = FastAPI(
        title="Pentest Hub",
        description="A hub-and-spoke service for pentest traffic collection and analysis",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Create broadcast channels
    raw_channel = BroadcastChannel[EnrichAuthNZMessage]()
    enriched_channel = BroadcastChannel[EnrichedRequest]()
    
    # Store channels in app state for access by workers and dependencies
    app.state.raw_channel = raw_channel
    app.state.enriched_channel = enriched_channel
    
    # Add exception handler for validation errors (422)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print(f"Validation error: {exc.errors()}")

    
    # Create routers with injected dependencies
    engagement_router = make_engagement_router()
    agent_router = make_agent_router()
    
    # Include routers
    app.include_router(engagement_router)
    app.include_router(agent_router)
    
    return app

async def start_api_server(app_instance: FastAPI):
    """Start the FastAPI server using uvicorn."""
    config = uvicorn.Config(app=app_instance, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    setup_server_logger(".server_logs")
    
    """Start both workers and API server concurrently."""
    # Create the app instance inside main
    app_instance = create_app()
    
    await asyncio.gather(
        start_workers(app_instance),
        start_api_server(app_instance)
    )

if __name__ == "__main__":
    asyncio.run(main())