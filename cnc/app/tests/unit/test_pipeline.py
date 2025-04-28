"""
tests/unit/test_pipeline.py
All new / modified features MUST satisfy these tests.
Run with:  pytest -q
"""
import asyncio
import threading
import time
import pytest
from uuid import uuid4

from app.domain.schemas import UserCtx
from app.services.eventbus import EventBus
from app.services.enrichment import RequestEnrichmentWorker
from app.services.attack import AttackWorker
from app.core.registry import register_enricher, register_attacker, sanity_check
from app.protocol import AttackData, HTTPRequestData, ResourceLocator, RequestPart


# ---------------------------------------------------------------------------
# 1. Registry sanity check ---------------------------------------------------
def test_sanity_guard_raises_for_unconsumed_enricher(monkeypatch):
    class DummyEnricher(RequestEnrichmentWorker):
        name = "dummy-e"
        async def enrich(self, req, user): 
            pass
    register_enricher(DummyEnricher)

    # Monkey-patch registry so there is NO attacker that consumes dummy-e
    with pytest.raises(RuntimeError):
        sanity_check()


# ---------------------------------------------------------------------------
# 2. AttackData construction -------------------------------------------------
def test_attackdata_roundtrip():
    req = HTTPRequestData(
        method="GET", url="http://t", headers={}, post_data=None,
        redirected_from_url=None, redirected_to_url=None, is_iframe=False
    )
    loc = ResourceLocator(id="X", request_part=RequestPart.URL, type_name="doc")
    data = AttackData(request=req, locators=[loc])
    assert data.locators[0].id == "X"
    assert data.request.url == "http://t"


# ---------------------------------------------------------------------------
# 3. End-to-end queue --------------------------------------------------------
async def _producer_consumer_test():
    bus = EventBus()
    data = {"msg": "hi"}
    results = []
    
    # Put data in the queue
    await bus.publish_raw(data)
    
    # Get data from the queue
    async for ev in bus.consume_raw():
        results.append(ev)
        break
    
    assert results and results[0]["msg"] == "hi"
    return results[0]["msg"] == "hi"


def test_inprocess_queue():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_producer_consumer_test())
        assert result is True
    finally:
        loop.close()