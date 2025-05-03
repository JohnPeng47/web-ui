import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import FastAPI
from typing import Optional

from database.session import create_db_and_tables, engine
from services.queue import BroadcastChannel
from services.enrichment import RequestEnrichmentWorker 
from workers.attackers.authnz.attacker import AuthzAttacker
from httplib import HTTPMessage
from schemas.http import EnrichedRequest

async def start_workers(app: Optional[FastAPI] = None):
    """
    Launch all worker processes.
    
    Args:
        app: FastAPI application instance with channels in app.state.
             If provided, workers will use these channels.
             If None, new channels will be created.
    """
    print("Starting worker launcher...")
    
    # Initialize database
    # await create_db_and_tables()
    
    # Get or create channels
    if app and hasattr(app.state, "raw_channel") and hasattr(app.state, "enriched_channel"):
        # Use channels from app.state
        raw_channel = app.state.raw_channel
        enriched_channel = app.state.enriched_channel
        print("Using channels from FastAPI app.state")
    else:
        raise Exception("No channels found in FastAPI app.state. Please provide an app instance.")
    
    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create the DB session
    async with async_session() as session:
        # Start workers with DI channels
        print("Starting workers with dependency injection...")
        
        # Create workers with injected dependencies
        enrichment_worker = RequestEnrichmentWorker(
            inbound=raw_channel,
            outbound=enriched_channel,
            db_session=session
        )
        
        authz_worker = AuthzAttacker(
            inbound=enriched_channel,
            db_session=session
        )
        
        # Run all workers concurrently
        await asyncio.gather(
            enrichment_worker.run(),
            authz_worker.run()
        )

        # await asyncio.gather(
        #     enrichment_worker.run(),
        # )

if __name__ == "__main__":
    try:
        asyncio.run(start_workers())
    except KeyboardInterrupt:
        print("Worker launcher shutdown by user")
    except Exception as e:
        print(f"Worker launcher error: {e}")
        raise