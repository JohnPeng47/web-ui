from typing import List, Dict, Any, Optional, Sequence, Union
import sys
import asyncio
import traceback
from datetime import datetime

from src.agent.client import AgentClient
from src.llm import RequestPart
from httplib import parse_burp_xml
from intruder import (
    AuthzTester,
    HTTPClient,
    HTTPRequestData,
    AuthSession,
    ResourceLocator,
    RequestPart,
    TestResult
)

import pytest
from unittest.mock import Mock
from intruder import (
    AuthzTester,
    HTTPClient,
    HTTPRequestData,
    AuthSession,
    Resource,
    ResourceType,
    ResourceLocator,
    RequestPart,
)

class TestAuthzTester:
    @pytest.fixture
    def mock_setup(self):
        """Setup Mock HTTPClient, AuthzTester, sessions and resource types"""
        # Setup Mock HTTPClient and AuthzTester
        mock_client = Mock(spec=HTTPClient)
        mock_client.send.return_value = None  # Don't actually send requests
        tester = AuthzTester(http_client=mock_client)
        
        # Setup mock sessions and resource types
        user_a_session = Mock(spec=AuthSession)
        user_b_session = Mock(spec=AuthSession)
        type1 = ResourceType(name="product", description="Product resource")
        
        return {
            "tester": tester,
            "mock_client": mock_client,
            "user_a_session": user_a_session,
            "user_b_session": user_b_session,
            "type1": type1
        }
    
    def create_product_edit_request(self, setup):
        """Create a product edit request for testing."""
        request_data = HTTPRequestData(
            method="POST",
            url="http://localhost:8000/products/21/edit-basic/",
            headers={
                "host": "localhost:8000",
                "content-length": "128",
                "cache-control": "max-age=0",
                "sec-ch-ua": "\"Chromium\";v=\"135\", \"Not-A.Brand\";v=\"8\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "accept-language": "en-US,en;q=0.9",
                "origin": "http://localhost:8000",
                "content-type": "application/x-www-form-urlencoded",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": "http://localhost:8000/products/21/edit-basic/",
                "accept-encoding": "gzip, deflate, br",
                "cookie": "csrftoken=XzDD7mdqORrBK5hvTTNK3rt228vsBZry; sessionid=et0u6y8f4wkxboq3jz0n1a9xpybmoa3c",
                "connection": "keep-alive"
            },
            post_data={
                "csrfmiddlewaretoken": "KycpX0FM1Ms0n3QFGBZ80Bye6wtEN7hAvplIh9JsSCRrsbGHv6whVrlK8ZkgEyuh",
                "description": "Good+item",
                "specifications": "%7B%7D"
            },
            is_iframe=False,
            redirected_from_url=None,
            redirected_to_url=None
        )
        
        resource_locator = ResourceLocator(
            id="21",
            request_part=RequestPart.URL,
            type_name="product"
        )
        
        return {
            "user": "good_corp-store_admin",
            "request_data": request_data,
            "resource_locators": [resource_locator],
        }
    
    def create_home_page_request(self, setup):
        """Create a home page request for testing."""
        request_data = HTTPRequestData(
            method="POST",
            url="http://localhost:8000/products/5/edit-basic/",
            headers={
                "host": "localhost:8000",
                "content-length": "124",
                "cache-control": "max-age=0",
                "sec-ch-ua": "\"Chromium\";v=\"135\", \"Not-A.Brand\";v=\"8\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "accept-language": "en-US,en;q=0.9",
                "origin": "http://localhost:8000",
                "content-type": "application/x-www-form-urlencoded",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document",
                "referer": "http://localhost:8000/products/5/edit-basic/",
                "accept-encoding": "gzip, deflate, br",
                "cookie": "csrftoken=WYXG8e7852QNJT51Xto7ekgZXDvKs4MR; sessionid=332a5vq2xm599pl2oicts9wm302ev9de",
                "connection": "keep-alive"
            },
            post_data={
                "csrfmiddlewaretoken": "izPxIHS3uPUfNOBsUwmqPWootgqlws2qTYxhm6d7rBS4sLFKfqpQpMpn20RNfubS",
                "description": "wwegg",
                "specifications": "%7B%7D"
            },
            is_iframe=False,
            redirected_from_url=None,
            redirected_to_url=None
        )
        
        resource_locator = ResourceLocator(
            id="5",
            request_part=RequestPart.URL,
            type_name="product"
        )
        
        return {
            "user": "evil_corp-store_admin",
            "request_data": request_data,
            "resource_locators": [resource_locator],
        }
    

    def test_stuff():
        tester = mock_setup["tester"]
        
        # Ingest the first request (product edit)
        req1 = self.create_product_edit_request(mock_setup)
        tester.ingest(
            user=req1["user"],
            request=req1["request_data"],
            resource_locators=req1["resource_locators"],
            session=req1["session"]
        )
        
        # No tests should be triggered after the first request
        assert len(tester.findings) == 0, "No tests should be triggered after first request"
        
        # Ingest the second request (home page)
        req2 = self.create_home_page_request(mock_setup)
        tester.ingest(
            user=req2["user"],
            request=req2["request_data"],
            resource_locators=req2["resource_locators"],
            session=req2["session"]
        )
        
        # Verify that the correct tests were triggered
        expected_tuples = {
            ("testuser2", "2", "http://localhost:8000/products/2/edit-basic/")
        }
        
        assert self.findings_to_tuples(tester.findings) == expected_tuples, "Expected cross-user test after second request"