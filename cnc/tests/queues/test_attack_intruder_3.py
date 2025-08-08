"""
Rewritten AuthZ tester integration tests.
These tests now use the *same* queue‑driven setup as the original
``test_authz_attacker_with_enriched_requests`` fixture – a real
``BroadcastChannel[EnrichedRequest]`` feeding an ``AuthzAttacker`` that
runs in the background.  All requests are published to the queue instead
of being passed directly to ``AuthzTester``.

⚠️  NOTE
-----
* The exact constructor signature for ``EnrichedRequest`` may differ in
your code‑base.  Replace the placeholder fields below with the real field
names if required – the important part is that the resulting object is
what your ``AuthzAttacker`` expects on its inbound channel.
* If ``AuthzTester`` exposes a dedicated ``reset()`` helper you can swap
  the direct ``findings.clear()`` calls for that.
"""

import asyncio
from uuid import UUID
from typing import List, Set, Tuple

import pytest
import pytest_asyncio

from cnc.services.queue import BroadcastChannel
from cnc.workers.attackers.authnz.attacker import AuthzAttacker
from cnc.workers.attackers.authnz.models import AuthNZAttack
from cnc.schemas.http import EnrichedRequest
from httplib import HTTPRequest, HTTPRequestData, ResourceLocator, RequestPart

# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _mk_enriched_request(
    *,
    username: str,
    method: str,
    url: str,
    cookie: str,
    resource_id: str,
    type_name: str,
    role: str,
) -> EnrichedRequest:
    """Create an ``EnrichedRequest`` instance suited for our tests."""

    # 1. Raw HTTP description
    http_data = HTTPRequestData(
        method=method,
        url=url,
        headers={"cookie": cookie},
        post_data=None,
        is_iframe=False,
        redirected_from_url=None,
        redirected_to_url=None,
    )
    http_req = HTTPRequest(data=http_data)

    # 2. Resource locator (AuthZTester needs this slice information)
    locator = ResourceLocator(
        id=resource_id,
        type_name=type_name,
        request_part=RequestPart.URL,
    )

    # 3. Compose EnrichedRequest – tweak the kwargs for your model
    return EnrichedRequest(
        username=username,
        role=role,
        request=http_req,
        resource_locators=[locator],
    )


def _findings_as_tuples(findings) -> Set[Tuple[str, str, str]]:
    """Convert finding objects to a hashable triple set for easy comparison."""
    print("FINDINGS: ", findings)
    return {
        # Each finding is expected to expose these three attrs; change if needed
        (f.user, f.resource_id, getattr(f, "action", getattr(f, "request_path", "")))
        for f in findings
    }


# ---------------------------------------------------------------------------
# Test‑wide fixture: a *single* attacker instance running for the whole module
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def attacker_env():
    """Spin up *one* ``AuthzAttacker`` fed by a queue for all tests."""

    channel: BroadcastChannel[EnrichedRequest] = BroadcastChannel()
    app_id = UUID("00000000-0000-0000-0000-000000000001")

    attacker = AuthzAttacker(inbound=channel, db_session=None, app_id=app_id)
    run_task = asyncio.create_task(attacker.run())

    try:
        yield attacker, channel
    finally:
        run_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run_task


# ---------------------------------------------------------------------------
# Test cases (rewritten to use the queue‑based plumbing)
# ---------------------------------------------------------------------------

class TestAuthzTesterViaQueue:
    """Equivalent of the old *direct‑ingest* tests, now via queue."""

    @pytest.mark.asyncio
    async def test_no_tests_after_first_request(self, attacker_env):
        attacker, channel = attacker_env

        # Reset *just* the internal findings – avoids re‑initialising Playwright
        attacker._authz_tester.findings.clear()

        # First request – UserA hits R1 (Type1)
        req1 = _mk_enriched_request(
            username="UserA",
            method="GET",
            url="/type1/resource/R1",
            cookie="a_session=1",
            resource_id="R1",
            type_name="Type1",
            role="customer"
        )

        await channel.publish(req1)
        await asyncio.sleep(0.1)  # let the attacker process

        assert (
            len(attacker._authz_tester.findings) == 0
        ), "No checks should trigger after a single request"

    @pytest.mark.asyncio
    async def test_cross_user_tests_after_second_request(self, attacker_env):
        attacker, channel = attacker_env
        attacker._authz_tester.findings.clear()

        # Request 1 – UserA -> R1 (Type1)
        req1 = _mk_enriched_request(
            username="UserA",
            method="GET",
            url="/type1/resource/R1",
            cookie="a_session=1",
            resource_id="R1",
            type_name="Type1",
            role="customer"
        )

        # Request 2 – UserB -> R2 (Type2)
        req2 = _mk_enriched_request(
            username="UserB",
            method="GET",
            url="/type2/resource/R2",
            cookie="b_session=1",
            resource_id="R2",
            type_name="Type2",
            role="customer"
        )

        # Publish in order
        await channel.publish(req1)
        await channel.publish(req2)

        # Allow background processing
        await asyncio.sleep(2.0)

        actual = _findings_as_tuples(attacker._authz_tester.findings)
        expected = {
            ("HorizontalUserAuthz", "UserA:customer", None, "GET /type2/resource/R2", None),
            ("HorizontalResourceAuthz", "UserB:customer", "R1", "GET /type1/resource/R1", "Type1"),
        }

        assert (
            actual == expected
        ), "Expected symmetric cross‑user resource‑access tests"

        # Bonus sanity‑check – at least one finding is a recognised AuthNZAttack
        assert any(
            isinstance(f, AuthNZAttack) for f in attacker._authz_tester.findings
        )
