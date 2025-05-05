from typing import List
import sys
import asyncio
import traceback
from datetime import datetime
import httpx
from src.agent.client import AgentClient
from httplib import parse_burp_xml


BURP_REQUEST_FILE = "tests/integration/cross_tenant_idor"
http_msgs = parse_burp_xml(BURP_REQUEST_FILE)


async def main():
    try:
        # Create the client - replace with actual server URL in production
        client = AgentClient(
            username="intruder_agent",
            role="scanner",
            client=httpx.AsyncClient(base_url="http://localhost:8000"),
        )
        
        # Create a new application
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_name = f"IntruderTest_{timestamp}"
        app_description = f"Automated test application created at {timestamp}"
        
        print(f"Creating application: {app_name}")
        app_id = await client.create_application(app_name, app_description)
        print(f"  ID: {app_id}")

        # Register the agent with the newly created application
        print(f"\nRegistering agent for application ID: {app_id}")
        agent_info = await client.register_agent(app_id)
        print(f"Agent registered successfully:")
        print(f"  ID: {agent_info['id']}")
        print(f"  Username: {agent_info['user_name']}")
        print(f"  Role: {agent_info['role']}")
        print(f"  Application ID: {agent_info['application_id']}")

        # Push the HTTP messages to the server
        print(f"\nPushing HTTP messages to application ID: {app_id}")
        result = await client.push_messages(app_id, agent_info["id"], [await msg.to_payload() for msg in http_msgs])
        print(f"Successfully pushed {result['accepted']} HTTP messages")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nTraceback (most recent call last):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


