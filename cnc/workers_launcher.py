import asyncio
from fastapi import FastAPI
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cnc.database.session import engine
from cnc.services.queue import BroadcastChannel
from cnc.services.enrichment import RequestEnrichmentWorker 
from cnc.workers.attackers.authnz.attacker import AuthzAttacker

from cnc.workers.agent.browser import start_single_browser

# agents
from cnc.services.agent.discovery_pool import run_asyncio_loop_with_sigint_handling as start_discovery_pool

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
        raw_channel = BroadcastChannel()
        enriched_channel = BroadcastChannel()
    
    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create the DB session
    async with async_session() as session:
        # Start workers with DI channels
        print("Starting workers with dependency injection...")
        
        # Run all workers concurrently
        await asyncio.gather(
            # start_enrichment_worker(raw_channel, enriched_channel, session),
            # start_attacker_worker(enriched_channel, session),
            start_single_browser(),
            start_discovery_pool(),
        )

if __name__ == "__main__":
    try:
        asyncio.run(start_workers())
    except KeyboardInterrupt:
        print("Worker launcher shutdown by user")
    except Exception as e:
        print(f"Worker launcher error: {e}")
        raise