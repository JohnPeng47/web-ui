import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.session import create_db_and_tables, engine
from services.queue import queues
from workers.request_enrichment import start_enrichment_worker
from workers.authz_attacker import start_authz_attacker


async def start_workers():
    """Launch all worker processes."""
    print("Starting worker launcher...")
    
    # Initialize database
    await create_db_and_tables()
    
    # Initialize queues
    queues.get("raw_http_msgs")
    queues.get("enriched_requests_authz")
    
    # Start workers
    print("Starting workers...")
    enrichment_task = asyncio.create_task(
        start_enrichment_worker(
            sub_queue_id="raw_http_msgs",
            pub_queue_id="enriched_requests_authz"
        )
    )
    
    authz_task = asyncio.create_task(
        start_authz_attacker(
            queue_id="enriched_requests_authz"
        )
    )
    
    # Wait for both workers to complete (they run indefinitely)
    await asyncio.gather(enrichment_task, authz_task)


if __name__ == "__main__":
    try:
        asyncio.run(start_workers())
    except KeyboardInterrupt:
        print("Worker launcher shutdown by user")
    except Exception as e:
        print(f"Worker launcher error: {e}")
        raise