from typing import List
from httplib import parse_burp_xml, HTTPMessage
from httplib import HTTPMessage

import asyncio

BURP_REQUEST_FILE = "tests/integration/cross_tenant_requests"

async def test_http_request_conversion():
    http_msgs = parse_burp_xml(BURP_REQUEST_FILE)
    print(f"Parsed {len(http_msgs)} HTTP messages from {BURP_REQUEST_FILE}")
    
    http_json = []
    for http_msg in http_msgs:
        payload = await http_msg.to_payload()
        HTTPMessage(**payload)
    
    print(f"Successfully converted {len(http_json)} HTTP messages")

if __name__ == "__main__":
    asyncio.run(test_http_request_conversion())