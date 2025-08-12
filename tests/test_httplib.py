from typing import List
from httplib import parse_burp_xml, HTTPMessage
from httplib import HTTPMessage

BURP_REQUEST_FILE = "tests/integration/cross_tenant_requests"

def test_http_request_conversion():
    http_msgs = parse_burp_xml(BURP_REQUEST_FILE)
    http_json = [HTTPMessage(await http_msg.to_payload()) for http_msg in http_msgs]

