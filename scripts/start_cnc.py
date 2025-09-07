import asyncio
import sys
sys.path.append("cnc")

from cnc.main import start_all 
from cnc.pools.discovery_agent_pool import start_discovery_agent as start_discovery_pool

if __name__ == "__main__":
    asyncio.run(start_all(start_discovery_pool))