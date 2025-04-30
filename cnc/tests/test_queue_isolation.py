import pytest
import asyncio
from typing import List, Dict, Any
from services.queue import BroadcastChannel
from services.enrichment import RequestEnrichmentWorker
from services.attack import AuthzAttacker
from httplib import HTTPMessage, HTTPRequest, HTTPRequestData
from schemas.http import EnrichedRequest


class MockHTTPMessage(HTTPMessage):
    """Simplified HTTPMessage for testing"""
    def __init__(self, url: str, method: str):
        self.request = HTTPRequest(
            data=HTTPRequestData(
                method=method,
                url=url,
                headers={},
                post_data=None,
                is_iframe=False
            )
        )
        self.response = None


class TestChannelIsolation:
    """
    Demonstrates the isolation benefits of the BroadcastChannel refactoring.
    
    Tests that we can create multiple independent hubs with no cross-talk,
    which wasn't possible with the global queue registry.
    """
    
    @pytest.mark.asyncio
    async def test_multiple_isolated_hubs(self):
        """Test that multiple hubs can operate independently without cross-talk."""
        # Create two separate hubs, each with their own channel pairs
        hub1_raw = BroadcastChannel[HTTPMessage]()
        hub1_enriched = BroadcastChannel[EnrichedRequest]()
        
        hub2_raw = BroadcastChannel[HTTPMessage]()
        hub2_enriched = BroadcastChannel[EnrichedRequest]()
        
        # Lists to store messages processed by each hub
        hub1_messages: List[Dict[str, Any]] = []
        hub2_messages: List[Dict[str, Any]] = []
        
        # Custom AuthzAttacker that just records processed messages
        class RecordingAuthzAttacker(AuthzAttacker):
            def __init__(self, inbound, message_store):
                super().__init__(inbound=inbound, db_session=None)
                self.message_store = message_store
                self._run_count = 0
                
            async def run(self):
                # Only run for a limited count, then exit for test purposes
                while self._run_count < 10:
                    try:
                        # Try to get a message with a timeout
                        enr = await asyncio.wait_for(
                            self._sub_q.get(), 
                            timeout=0.5
                        )
                        self._run_count += 1
                        
                        # Record the message
                        self.message_store.append({
                            "url": enr.request.url,
                            "username": enr.username
                        })
                    except asyncio.TimeoutError:
                        # Exit if no more messages within timeout
                        break
        
        # Create the channel processors
        enricher1 = RequestEnrichmentWorker(
            inbound=hub1_raw,
            outbound=hub1_enriched
        )
        
        enricher2 = RequestEnrichmentWorker(
            inbound=hub2_raw,
            outbound=hub2_enriched
        )
        
        attacker1 = RecordingAuthzAttacker(
            inbound=hub1_enriched,
            message_store=hub1_messages
        )
        
        attacker2 = RecordingAuthzAttacker(
            inbound=hub2_enriched,
            message_store=hub2_messages
        )
        
        # Start all the workers as background tasks
        worker_tasks = [
            asyncio.create_task(enricher1.run()),
            asyncio.create_task(enricher2.run()),
            asyncio.create_task(attacker1.run()),
            asyncio.create_task(attacker2.run())
        ]
        
        # Wait a moment for workers to start
        await asyncio.sleep(0.1)
        
        # Test data
        hub1_urls = ["/hub1/resource1", "/hub1/resource2", "/hub1/resource3"]
        hub2_urls = ["/hub2/resource1", "/hub2/resource2", "/hub2/resource3"]
        
        # Send test messages to hub1 and hub2
        for url in hub1_urls:
            message = MockHTTPMessage(url=url, method="GET")
            await hub1_raw.publish(message)
        
        for url in hub2_urls:
            message = MockHTTPMessage(url=url, method="GET")
            await hub2_raw.publish(message)
        
        # Wait for processing to complete
        await asyncio.sleep(2)
        
        # Cancel all worker tasks
        for task in worker_tasks:
            task.cancel()
        
        # Verify messages were processed in the correct hubs
        assert len(hub1_messages) == 3, f"Expected 3 messages in hub1, got {len(hub1_messages)}"
        assert len(hub2_messages) == 3, f"Expected 3 messages in hub2, got {len(hub2_messages)}"
        
        # Verify hub1 only processed hub1 URLs
        for msg in hub1_messages:
            assert msg["url"].startswith("/hub1/"), f"Hub1 processed URL from hub2: {msg['url']}"
        
        # Verify hub2 only processed hub2 URLs
        for msg in hub2_messages:
            assert msg["url"].startswith("/hub2/"), f"Hub2 processed URL from hub1: {msg['url']}"
        
        # Verify all URLs were processed
        processed_hub1_urls = [msg["url"] for msg in hub1_messages]
        processed_hub2_urls = [msg["url"] for msg in hub2_messages]
        
        for url in hub1_urls:
            assert url in processed_hub1_urls, f"URL {url} missing from hub1 processed messages"
        
        for url in hub2_urls:
            assert url in processed_hub2_urls, f"URL {url} missing from hub2 processed messages"
        
        print("All messages were correctly isolated between hubs with no cross-talk!")


    @pytest.mark.asyncio
    async def test_worker_with_fake_channels(self):
        """Test that we can inject fake channels for testing worker code."""
        # Create a test channel
        test_channel = BroadcastChannel[EnrichedRequest]()
        
        # Lists to record processed messages
        processed_messages: List[Dict[str, Any]] = []
        
        # Custom worker for testing
        class TestableAuthzAttacker(AuthzAttacker):
            def __init__(self, inbound, message_store):
                super().__init__(inbound=inbound, db_session=None)
                self.message_store = message_store
                self._run_count = 0
                
            async def run(self):
                while self._run_count < 10:
                    try:
                        enr = await asyncio.wait_for(self._sub_q.get(), timeout=0.5)
                        self._run_count += 1
                        # Just record the URL for testing
                        self.message_store.append({
                            "url": enr.request.url,
                            "username": enr.username
                        })
                    except asyncio.TimeoutError:
                        break
        
        # Create the worker with our test channel
        worker = TestableAuthzAttacker(
            inbound=test_channel,
            message_store=processed_messages
        )
        
        # Start worker as background task
        worker_task = asyncio.create_task(worker.run())
        
        # Wait a moment for worker to start
        await asyncio.sleep(0.1)
        
        # Send test messages
        urls = ["/test/resource1", "/test/resource2", "/test/resource3"]
        for url in urls:
            # Create and publish a test message
            request = HTTPRequest(
                data=HTTPRequestData(
                    method="GET",
                    url=url,
                    headers={},
                    post_data=None,
                    is_iframe=False
                )
            )
            enriched = EnrichedRequest(
                request=request,
                username="testuser"
            )
            await test_channel.publish(enriched)
        
        # Wait for processing to complete
        await asyncio.sleep(1)
        
        # Cancel worker task
        worker_task.cancel()
        
        # Verify messages were processed
        assert len(processed_messages) == 3, f"Expected 3 messages, got {len(processed_messages)}"
        
        # Verify all URLs were processed
        processed_urls = [msg["url"] for msg in processed_messages]
        for url in urls:
            assert url in processed_urls, f"URL {url} not found in processed messages"
        
        print("Worker can be tested in isolation using fake channels!") 