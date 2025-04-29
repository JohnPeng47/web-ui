from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

from routers.application import router as application_router
from routers.agent import router as agent_router
from database.session import create_db_and_tables
from services.queue import queues
import asyncio
from workers_launcher import start_workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Initialize queues
    queues.get("raw_http_msgs")
    queues.get("enriched_requests_authz")
    
    # Initialize database
    await create_db_and_tables()
    
    # App is now ready
    yield
    
    # Cleanup code would go here (if needed)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pentest Hub",
        description="A hub-and-spoke service for pentest traffic collection and analysis",
        version="0.1.0",
        lifespan=lifespan
    )
    
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
        start_workers(),
        start_api_server()
    )


if __name__ == "__main__":
    asyncio.run(main())