from browser_use.agent.views import AgentHistoryList

from pathlib import Path
import json
import pytest

HISTORY_DATA_PATH = Path(__file__).parent / "data" / "history.json"

@pytest.fixture
def history_data():
    """
    Fixture to load history data from a JSON file.
    """
    with open(HISTORY_DATA_PATH, "r") as f:
        data = f.read()
        
    data = json.loads(data)
    return AgentHistoryList(**data)
