import httpx
from datetime import datetime
import asyncio
from pathlib import Path

from src.agent.client import AgentClient

VULN_APP_URL = "http://localhost:3000"
CNC_URL = "http://localhost:8000"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

async def create_app():
    # Create the client
    main_client = AgentClient(
        client=httpx.AsyncClient(base_url=CNC_URL), 
    )

    # Create a new application
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    app_name = f"AgentIntruderTest_{timestamp}"
    app_description = f"Automated test application created at {timestamp}"

    print(f"Creating application: {app_name}")
    app_id = await main_client.create_application(app_name, app_description)
    print(f"Application created successfully:")
    print(f"  ID: {app_id}")
    return app_id

if __name__ == "__main__":
    app_id = asyncio.run(create_app())
