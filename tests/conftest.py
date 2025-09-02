from browser_use.agent.views import AgentHistoryList
from src.agent.pages import PageObservations

from typing import List
from httplib import HTTPMessage

from pathlib import Path
import json
import pytest

HISTORY_DATA_PATH = Path(__file__).parent / "data" / "history.json"
HTTP_REQUESTS_DATA_PATH = Path(__file__).parent / "data" / "http_requests.json"

@pytest.fixture
def history_data():
    """
    Fixture to load history data from a JSON file.
    """
    with open(HISTORY_DATA_PATH, "r") as f:
        data = f.read()
        
    data = json.loads(data)
    return AgentHistoryList(**data)


@pytest.fixture
def http_msgs() -> List[HTTPMessage]:
    with open(HTTP_REQUESTS_DATA_PATH, "r") as f:
        data = f.read()
        
    data = json.loads(data)
    flat_list = []
    for page in PageObservations.from_json(data).pages:
        flat_list.extend(page.http_msgs)
    return flat_list