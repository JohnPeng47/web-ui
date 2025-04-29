from services.enrichment import SimpleEnrichmentWorker
from services.queue import queues
from database.session import get_session
import asyncio
from typing import Optional


async def start_enrichment_worker(
    sub_queue_id: str = "raw_http_msgs",
    pub_queue_id: str = "enriched_requests_authz"
):
    """Start the request enrichment worker."""
    # Get a database session from the pool
    db_session = None
    async for session in get_session():
        db_session = session
        break  # Just get one session
    
    if not db_session:
        raise RuntimeError("Failed to acquire database session")
    
    worker = SimpleEnrichmentWorker(
        sub_queue_id=sub_queue_id,
        pub_queue_id=pub_queue_id,
        db_session=db_session
    )
    
    print(f"Starting enrichment worker listening on {sub_queue_id} and publishing to {pub_queue_id}")
    await worker.run()