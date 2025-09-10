import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from cnc.database.session import get_session, override_db
from cnc.database.agent.models import DiscoveryAgentModel, ExploitAgentModel

async def test_insert_discovery_agent():
    """Test inserting a DiscoveryAgent into the database."""
    async for session in get_session():
        print("giewg")
        # Create an ExploitAgent with the specified values
        agent = ExploitAgentModel(
            agent_status="active",
            max_steps=5,
            model_name="gpt-4o-mini",
            model_costs=0.01,
            log_filepath="/tmp/agent.log",
            agent_type="exploit",
            vulnerability_title="test"
        )
        
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        
if __name__ == "__main__":
    asyncio.run(test_insert_discovery_agent())