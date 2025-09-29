import json
import asyncio
from unittest.mock import patch

import pytest

from cnc.services.detection import DetectionScheduler
from src.agent.discovery.pages import Page, PageObservations


class FakeRequest:
    def __init__(self, headers=None, body=None):
        self.headers = headers or {}
        self._body = body

    def get_body(self):
        return self._body or ""


class FakeResponse:
    def __init__(self, headers=None, body=None):
        self.headers = headers or {}
        self._body = body

    def get_body(self):
        return self._body or ""


class FakeHTTPMessage:
    def __init__(self, method: str, url: str, req_body: str = "", res_body: str = ""):
        self.method = method
        self.url = url
        self.request = FakeRequest(headers={"Content-Type": "application/json"}, body=req_body)
        self.response = FakeResponse(headers={"Content-Type": "application/json"}, body=res_body)


class FakeModel:
    def __init__(self, assert_prompt_fn, response_action_id: str):
        self.assert_prompt_fn = assert_prompt_fn
        self.response_action_id = response_action_id

    async def ainvoke(self, prompt: str):
        # Allow the test to assert on the full rendered prompt
        if self.assert_prompt_fn:
            self.assert_prompt_fn(prompt)
        payload = {
            "actions": [
                {
                    "page_item_id": self.response_action_id,
                    "vulnerability_description": "desc",
                    "vulnerability_title": "title",
                }
            ]
        }
        return type("Resp", (), {"content": json.dumps(payload)})


def _make_pages_fixture() -> PageObservations:
    # One page with two groups: (GET,/a) and (POST,/b)
    msgs = [
        FakeHTTPMessage("GET", "/a", req_body="qa", res_body="ra"),
        FakeHTTPMessage("POST", "/b", req_body="qb", res_body="rb"),
    ]
    page = Page(url="http://example.test", http_msgs=msgs)
    obs = PageObservations([page])
    return obs


def test_generate_actions_full_context_uses_all_pages():
    pages = _make_pages_fixture()

    def assert_prompt(prompt: str):
        assert "Target scope: ALL" in prompt
        # Both endpoints should appear in the prompt text
        assert "GET /a" in prompt
        assert "POST /b" in prompt

    model = FakeModel(assert_prompt_fn=assert_prompt, response_action_id="1.1")
    scheduler = DetectionScheduler()

    with patch.object(scheduler, "_build_pages_prompt") as mock_build:
        mock_build.side_effect = lambda pages, page_item_id: print(f"Building prompt for pages: {pages}, page_item_id: {page_item_id}") or scheduler._build_pages_prompt.__wrapped__(scheduler, pages, page_item_id)
        
        res = asyncio.run(
            scheduler.generate_actions_no_trigger(
                model=model,
                pages=pages,
                num_actions=1,
            )
        )

    assert len(res) == 1
    assert res[0].vulnerability_title == "title"
    assert res[0].vulnerability_description == "desc"
    # Should resolve to a real message
    assert res[0].page_item is not None
    assert getattr(res[0].page_item, "method", None) == "GET"


def test_generate_actions_subset_context_uses_selected_only():
    pages = _make_pages_fixture()

    def assert_prompt(prompt: str):
        assert "Target scope: 1.1" in prompt
        # Subset should show only the first section (GET /a) and not the other
        assert "GET /a" in prompt
        assert "POST /b" not in prompt

    model = FakeModel(assert_prompt_fn=assert_prompt, response_action_id="1.1")
    scheduler = DetectionScheduler()

    with patch.object(scheduler, "_build_pages_prompt") as mock_build:
        mock_build.side_effect = lambda pages, page_item_id: print(f"Building prompt for pages: {pages}, page_item_id: {page_item_id}") or scheduler._build_pages_prompt.__wrapped__(scheduler, pages, page_item_id)
        
        res = asyncio.run(
            scheduler.generate_actions_no_trigger_for_item(
                model=model,
                pages=pages,
                num_actions=1,
                page_item_id="1.1",
            )
        )

    assert len(res) == 1
    assert res[0].vulnerability_title == "title"
    assert res[0].vulnerability_description == "desc"
    assert res[0].page_item is not None
    assert getattr(res[0].page_item, "method", None) == "GET"


