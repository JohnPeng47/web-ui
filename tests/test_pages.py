import json
import re
import asyncio

from src.agent.discovery.pages import PageObservations


def _extract_ids(observations_json):
    page_ids = []
    msg_ids_by_page = []
    for page_wrapper in observations_json:
        page_ids.append(page_wrapper["id"])
        page_payload = page_wrapper["item"]
        msg_ids = [m["id"] for m in page_payload.get("http_msgs", [])]
        msg_ids_by_page.append(msg_ids)
    return page_ids, msg_ids_by_page


def test_ids_consistent_roundtrip():
    page_contents = json.loads(open("tests/complete_page_data.json", "r").read())

    # Load from legacy JSON → assign nested ids
    obs1 = PageObservations.from_json(page_contents)

    json1 = asyncio.run(obs1.to_json())

    # Round-trip through the new wrapper format
    obs2 = PageObservations.from_json(json1)
    json2 = asyncio.run(obs2.to_json())

    # Extract ids from both serializations
    page_ids_1, msg_ids_by_page_1 = _extract_ids(json1)
    page_ids_2, msg_ids_by_page_2 = _extract_ids(json2)

    # Page ids should remain identical and stable
    assert page_ids_1 == page_ids_2
    for pid in page_ids_1:
        assert re.match(r"^\d+$", pid)

    # Message ids should remain identical and stable per page and order
    assert len(msg_ids_by_page_1) == len(msg_ids_by_page_2)
    for idx in range(len(msg_ids_by_page_1)):
        p1 = page_ids_1[idx]
        ids1 = msg_ids_by_page_1[idx]
        ids2 = msg_ids_by_page_2[idx]
        assert ids1 == ids2
        for mid in ids1:
            # Expect nested a.b.c format beginning with the page id
            assert re.match(rf"^{p1}\.\d+\.\d+$", mid)


