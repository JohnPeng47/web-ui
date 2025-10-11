import json
from typing import List, Dict, Any
from httplib import (
    parse_burp_xml, 
    HTTPMessage, 
    HTTPRequest, 
    HTTPRequestData,
    post_data_to_dict,
    format_body
)

BURP_REQUEST_FILE = "tests/integration/cross_tenant_requests"


# Tests for different request payload formats

def test_http_request_json_payload():
    """Test HTTPRequest with JSON payload"""
    json_data = {"username": "test_user", "password": "secret123", "remember": True}
    json_string = json.dumps(json_data)
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/login",
        headers={
            "content-type": "application/json",
            "content-length": str(len(json_string))
        },
        post_data=json_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.url == "https://example.com/api/login"
    assert request.post_data == json_data
    assert request.get_body() == json_data


def test_http_request_urlencoded_form_data():
    """Test HTTPRequest with URL-encoded form data"""
    form_data = {"username": "test_user", "password": "secret123", "action": "login"}
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/login",
        headers={
            "content-type": "application/x-www-form-urlencoded",
        },
        post_data=form_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.post_data == form_data
    body = request.get_body()
    assert body["username"] == "test_user"
    assert body["password"] == "secret123"


def test_http_request_multipart_form_data():
    """Test HTTPRequest with multipart/form-data"""
    form_data = {
        "username": "test_user",
        "email": "test@example.com",
        "profile_pic": "[binary data]"
    }
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/upload",
        headers={
            "content-type": "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
        },
        post_data=form_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.post_data == form_data
    assert request.get_body()["username"] == "test_user"


def test_http_request_xml_payload():
    """Test HTTPRequest with XML payload"""
    xml_data = {
        "xml": "<user><name>test_user</name><email>test@example.com</email></user>"
    }
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/user",
        headers={
            "content-type": "application/xml",
        },
        post_data=xml_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.post_data == xml_data


def test_http_request_plain_text_payload():
    """Test HTTPRequest with plain text payload"""
    text_data = {"text": "This is a plain text message"}
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/message",
        headers={
            "content-type": "text/plain",
        },
        post_data=text_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.post_data == text_data


def test_http_request_html_payload():
    """Test HTTPRequest with HTML payload"""
    html_data = {
        "html": "<html><body><h1>Test Page</h1></body></html>"
    }
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/content",
        headers={
            "content-type": "text/html",
        },
        post_data=html_data
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "POST"
    assert request.post_data == html_data


def test_http_request_empty_payload():
    """Test HTTPRequest with no payload"""
    request_data = HTTPRequestData(
        method="GET",
        url="https://example.com/api/users",
        headers={
            "accept": "application/json",
        },
        post_data=None
    )
    request = HTTPRequest(data=request_data)
    
    assert request.method == "GET"
    assert request.post_data is None
    assert request.get_body() == ""


def test_http_request_nested_json_payload():
    """Test HTTPRequest with nested JSON structures"""
    nested_data = {
        "user": {
            "profile": {
                "name": "John Doe",
                "age": 30,
                "tags": ["developer", "python", "security"]
            },
            "settings": {
                "notifications": True,
                "theme": "dark"
            }
        }
    }
    
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/profile",
        headers={
            "content-type": "application/json",
        },
        post_data=nested_data
    )
    request = HTTPRequest(data=request_data)
    
    body = request.get_body()
    assert body["user"]["profile"]["name"] == "John Doe"
    assert "python" in body["user"]["profile"]["tags"]
    assert body["user"]["settings"]["theme"] == "dark"


def test_post_data_to_dict_urlencoded():
    """Test post_data_to_dict with URL-encoded data"""
    post_data = "username=test&password=secret123&remember=true"
    result = post_data_to_dict(post_data)
    
    assert result["username"] == "test"
    assert result["password"] == "secret123"
    assert result["remember"] == "true"


def test_post_data_to_dict_json_string():
    """Test post_data_to_dict with JSON string"""
    json_data = {"username": "test", "password": "secret"}
    post_data = json.dumps(json_data)
    result = post_data_to_dict(post_data)
    
    assert result["username"] == "test"
    assert result["password"] == "secret"


def test_post_data_to_dict_empty():
    """Test post_data_to_dict with empty data"""
    assert post_data_to_dict(None) == {}
    assert post_data_to_dict("") == {}


def test_post_data_to_dict_special_characters():
    """Test post_data_to_dict with special characters"""
    post_data = "email=test%40example.com&name=John+Doe&message=Hello%20World"
    result = post_data_to_dict(post_data)
    
    assert "email" in result
    assert "name" in result
    assert "message" in result


def test_format_body_json_dict():
    """Test format_body with JSON dict"""
    body = {"key": "value", "number": 42}
    headers = {"content-type": "application/json"}
    result = format_body(body, headers)
    
    assert isinstance(result, dict)
    assert result["key"] == "value"
    assert result["number"] == 42


def test_format_body_json_bytes():
    """Test format_body with JSON as bytes"""
    json_data = {"test": "data", "count": 100}
    body = json.dumps(json_data).encode("utf-8")
    headers = {"content-type": "application/json"}
    result = format_body(body, headers)
    
    assert isinstance(result, dict)
    assert result["test"] == "data"
    assert result["count"] == 100


def test_format_body_html_bytes():
    """Test format_body with HTML as bytes"""
    html = "<html><body>Test</body></html>"
    body = html.encode("utf-8")
    headers = {"content-type": "text/html"}
    result = format_body(body, headers)
    
    assert isinstance(result, str)
    assert "<html>" in result
    assert "Test" in result


def test_format_body_plain_text():
    """Test format_body with plain text"""
    body = "This is plain text content"
    headers = {"content-type": "text/plain"}
    result = format_body(body, headers)
    
    assert isinstance(result, str)
    assert result == body


def test_format_body_xml_string():
    """Test format_body with XML string"""
    xml = "<root><item>value</item></root>"
    headers = {"content-type": "application/xml"}
    result = format_body(xml, headers)
    
    assert isinstance(result, str)
    assert "<root>" in result


def test_format_body_binary_data():
    """Test format_body with binary data"""
    body = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    headers = {"content-type": "image/png"}
    result = format_body(body, headers)
    
    assert isinstance(result, bytes)


def test_format_body_form_urlencoded():
    """Test format_body with URL-encoded form"""
    body = "key1=value1&key2=value2"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    result = format_body(body, headers)
    
    assert isinstance(result, str)
    assert "key1=value1" in result


def test_http_request_to_json_and_back():
    """Test serializing and deserializing HTTPRequest"""
    original_data = {
        "method": "POST",
        "url": "https://example.com/api",
        "headers": {"content-type": "application/json"},
        "post_data": {"key": "value"}
    }
    
    request_data = HTTPRequestData(**original_data)
    request = HTTPRequest(data=request_data)
    
    # Convert to JSON
    json_data = request.to_json()
    
    # Convert back
    restored_request = HTTPRequest.from_json(json_data)
    
    assert restored_request.method == original_data["method"]
    assert restored_request.url == original_data["url"]
    assert restored_request.post_data == original_data["post_data"]


def test_http_request_with_auth_session():
    """Test HTTPRequest with authentication session"""
    request_data = HTTPRequestData(
        method="POST",
        url="https://example.com/api/secure",
        headers={
            "authorization": "Bearer token123",
            "content-type": "application/json"
        },
        post_data={"action": "get_data"}
    )
    request = HTTPRequest(data=request_data)
    
    assert request.auth_session is not None
    assert request.auth_session.headers["authorization"] == "Bearer token123"


def test_http_request_hash():
    """Test HTTPRequest hashing for deduplication"""
    request_data1 = HTTPRequestData(
        method="POST",
        url="https://example.com/api",
        headers={"content-type": "application/json"},
        post_data={"key": "value"}
    )
    request1 = HTTPRequest(data=request_data1)
    
    request_data2 = HTTPRequestData(
        method="POST",
        url="https://example.com/api",
        headers={"content-type": "application/json"},
        post_data={"key": "value"}
    )
    request2 = HTTPRequest(data=request_data2)
    
    # Same requests should have same hash
    assert hash(request1) == hash(request2)
    
    # Different requests should (likely) have different hash
    request_data3 = HTTPRequestData(
        method="GET",
        url="https://example.com/api",
        headers={"content-type": "application/json"},
        post_data=None
    )
    request3 = HTTPRequest(data=request_data3)
    assert hash(request1) != hash(request3)


def test_post_data_to_dict_malformed_data_logs_warning(caplog):
    """Test post_data_to_dict logs warning for malformed data that cannot be parsed"""
    import logging
    
    # Malformed data that doesn't match any parsing pattern
    # (not URL-encoded, not valid JSON)
    malformed_data = "this is malformed data without proper format"
    
    # Clear any existing logs
    caplog.clear()
    
    # Set log level to capture warnings
    with caplog.at_level(logging.WARNING):
        result = post_data_to_dict(malformed_data)
    
    # Verify the result contains error message
    assert result == {"error": "Failed to parse post data"}
    
    # Verify the warning was logged
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert "Failed to parse post data" in caplog.records[0].message
    assert malformed_data in caplog.records[0].message