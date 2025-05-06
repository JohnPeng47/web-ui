"""
cnc/tests/queues/test_attack_intruder_3.py
"""
import asyncio
import json
import pytest
from uuid import UUID

from cnc.services.queue import BroadcastChannel
from cnc.workers.attackers.authnz.attacker import AuthzAttacker
from cnc.workers.attackers.authnz.models import HorizontalResourceAuthz, VerticalResourceAuthz, AuthNZAttack
from schemas.http import EnrichedRequest
from httplib import HTTPRequest, HTTPRequestData, ResourceLocator, RequestPart

pytestmark = pytest.mark.asyncio

async def test_authz_attacker_with_enriched_requests(test_enriched_requests) -> None:
    """
    Test that the AuthzAttacker correctly processes enriched requests and generates findings.
    """
    # Create a broadcast channel for enriched requests
    enriched_channel = BroadcastChannel[EnrichedRequest]()
    
    # Create the AuthzAttacker with the enriched channel
    app_id = UUID("00000000-0000-0000-0000-000000000001")  # Mock app ID
    authz_attacker = AuthzAttacker(
        inbound=enriched_channel,
        db_session=None,
        app_id=app_id
    )
    
    # Run the attacker in the background
    attacker_task = asyncio.create_task(authz_attacker.run())
    
    # Send the enriched requests to the channel
    for enriched_request in test_enriched_requests:
        await enriched_channel.publish(enriched_request)
    
    # Give the attacker some time to process the requests
    await asyncio.sleep(0.5)
    
    # Check that the attacker has processed the requests and generated findings
    assert len(authz_attacker._authz_tester.findings) > 0
    
    # Verify that the findings include the expected attack types
    attack_types = [finding.sub_type for finding in authz_attacker._authz_tester.findings 
                   if isinstance(finding, AuthNZAttack)]
    
    print("ATTACKS: ")
    for attack in attack_types:
        print(attack)

    # We expect to see horizontal and/or vertical resource attacks
    assert any(attack_type in attack_types for attack_type in 
              ["Vertical User Action"])
    
    # Clean up the attacker task
    attacker_task.cancel()
    try:
        await attacker_task
    except asyncio.CancelledError:
        pass