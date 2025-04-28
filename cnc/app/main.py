from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
import uvicorn
import os

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core import registry
from app.services.eventbus import EventBus


# Initialize logging
setup_logging()

# Create engine with SQLite settings
engine = create_async_engine(
    settings.sqlite_db_url, 
    connect_args={"check_same_thread": False} # Required for SQLite
)

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and initialize state
    async with engine.begin() as conn:
        # Create all tables - You might want to use migrations in production
        await conn.run_sync(SQLModel.metadata.create_all)

    # Set up state
    db_session = AsyncSession(engine)
    bus = EventBus()
    app.state.db = db_session
    app.state.bus = bus
    print("--- Startup complete ---") # Optional: for verification
    yield
    # Shutdown: Close DB connection and dispose engine
    print("--- Shutting down ---") # Optional: for verification
    await db_session.close()
    await engine.dispose()


# Initialize application with lifespan
app = FastAPI(title="Pentest Hub", lifespan=lifespan)

# Include routers
app.include_router(v1_router)

# Register the sanity check (registry check)
registry.sanity_check()


@app.get("/healthz")
async def healthcheck():
    return {"status": "ok"}


# Add CLI entry point
if __name__ == "__main__":
    # Load environment variables (consider using python-dotenv if needed)
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    # Use reload=True for development convenience, turn off in production
    uvicorn.run("app.main:app", host=host, port=port, reload=True)