from services.attack import AuthzAttacker
from services.queue import queues
from database.session import get_session
import asyncio


async def start_authz_attacker(queue_id: str = "enriched_requests_authz"):
    """Start the authorization attack worker."""
    # Get a database session from the pool
    db_session = None
    async for session in get_session():
        db_session = session
        break  # Just get one session
    
    if not db_session:
        raise RuntimeError("Failed to acquire database session")
    
    worker = AuthzAttacker(queue_id=queue_id, db_session=db_session)
    
    print(f"Starting authorization attack worker listening on {queue_id}")
    await worker.run()