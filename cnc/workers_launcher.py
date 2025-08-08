import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from fastapi import FastAPI
from typing import Optional

from database.session import create_db_and_tables, engine
from services.queue import BroadcastChannel
from services.enrichment import RequestEnrichmentWorker 
from workers.attackers.authnz.attacker import AuthzAttacker
from httplib import HTTPMessage
from cnc.schemas.http import EnrichedRequest

async def start_enrichment_worker(raw_channel: BroadcastChannel, enriched_channel: BroadcastChannel, session: AsyncSession):
    """
    Start the enrichment worker.
    
    Args:
        raw_channel: Channel for raw HTTP messages
        enriched_channel: Channel for enriched requests
        session: Database session
    """
    print("Starting enrichment worker...")
    
    # Create worker with injected dependencies
    enrichment_worker = RequestEnrichmentWorker(
        inbound=raw_channel,
        outbound=enriched_channel,
        db_session=session
    )
    
    # Run the worker
    await enrichment_worker.run()

async def start_attacker_worker(enriched_channel: BroadcastChannel, session: AsyncSession):
    """
    Start the authorization attacker worker.
    
    Args:
        enriched_channel: Channel for enriched requests
        session: Database session
    """
    print("Starting authorization attacker worker...")
    
    # Create worker with injected dependencies
    authz_worker = AuthzAttacker(
        inbound=enriched_channel,
        db_session=session
    )
    
    # Run the worker
    await authz_worker.run()

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
        
        # Run all workers concurrently
        await asyncio.gather(
            start_enrichment_worker(raw_channel, enriched_channel, session),
            start_attacker_worker(enriched_channel, session)
        )

if __name__ == "__main__":
    try:
        asyncio.run(start_workers())
    except KeyboardInterrupt:
        print("Worker launcher shutdown by user")
    except Exception as e:
        print(f"Worker launcher error: {e}")
        raise