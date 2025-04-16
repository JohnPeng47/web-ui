import base64
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class HTTPRequestData:
    """Internal representation of HTTP request data"""
    method: str
    url: str
    headers: Dict[str, str]
    post_data: Optional[str]
    redirected_from_url: Optional[str]
    redirected_to_url: Optional[str] 
    is_iframe: bool

class HTTPRequest:
    """HTTP request class with unified implementation"""
    def __init__(self, data: HTTPRequestData):
        self._data = data

    @property
    def method(self) -> str:
        return self._data.method

    @property
    def url(self) -> str:
        return self._data.url

    @property
    def headers(self) -> Dict[str, str]:
        return self._data.headers

    @property
    def post_data(self) -> Optional[str]:
        return self._data.post_data

    @property
    def redirected_from(self) -> Optional["HTTPRequest"]:
        if self._data.redirected_from_url:
            # Create minimal request object for redirect
            data = HTTPRequestData(
                method="",
                url=self._data.redirected_from_url,
                headers={},
                post_data=None,
                redirected_from_url=None,
                redirected_to_url=None,
                is_iframe=False
            )
            return HTTPRequest(data)
        return None

    @property
    def redirected_to(self) -> Optional["HTTPRequest"]:
        if self._data.redirected_to_url:
            # Create minimal request object for redirect
            data = HTTPRequestData(
                method="",
                url=self._data.redirected_to_url,
                headers={},
                post_data=None,
                redirected_from_url=None,
                redirected_to_url=None,
                is_iframe=False
            )
            return HTTPRequest(data)
        return None

    @property
    def is_iframe(self) -> bool:
        return self._data.is_iframe

@dataclass
class HTTPResponseData:
    """Internal representation of HTTP response data"""
    url: str
    status: int
    headers: Dict[str, str]
    is_iframe: bool
    body: Optional[bytes] = None
    body_error: Optional[str] = None

class HTTPResponse:
    """HTTP response class with unified implementation"""
    def __init__(self, data: HTTPResponseData):
        self._data = data

    @property
    def url(self) -> str:
        return self._data.url

    @property
    def status(self) -> int:
        return self._data.status

    @property
    def headers(self) -> Dict[str, str]:
        return self._data.headers

    @property
    def is_iframe(self) -> bool:
        return self._data.is_iframe

    async def get_body(self) -> bytes:
        if self._data.body_error:
            raise Exception(self._data.body_error)
        if self._data.body is None:
            raise Exception("Response body not available")
        return self._data.body

@dataclass
class HTTPMessage:
    """Encapsulates a request/response pair"""
    request: HTTPRequest 
    response: Optional[HTTPResponse]

    @property
    def url(self):
        return self.request.url
    
    @property
    def method(self):
        return self.request.method
    
    @property
    def body(self):
        return self.request.post_data

@dataclass
class HTTPMessageList:
    """A collection of HTTP messages with a name"""
    messages: List[HTTPMessage]

def parse_burp_headers(raw_headers: str) -> Dict[str, str]:
    """Parse HTTP headers from a raw string into a dictionary"""
    headers = {}
    lines = raw_headers.split('\n')
    
    # Skip the first line (HTTP method line) for request headers
    start_line = 1 if lines and (lines[0].startswith('GET') or lines[0].startswith('POST')) else 0
    
    for line in lines[start_line:]:
        if not line.strip():
            continue
        parts = line.split(':', 1)
        if len(parts) == 2:
            key, value = parts
            headers[key.strip().lower()] = value.strip()
    
    return headers

def parse_burp_request(request_text: str, is_base64: bool, url: str, method: str) -> HTTPRequest:
    """Parse raw HTTP request data into a HTTPRequest object"""
    if is_base64:
        try:
            request_text = base64.b64decode(request_text).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Error decoding base64 request: {e}")
            request_text = ""
    
    # Split headers and body
    parts = request_text.split('\n\n', 1)
    headers_text = parts[0]
    post_data = parts[1] if len(parts) > 1 else None
    
    headers = parse_burp_headers(headers_text)
    
    # Create request data
    request_data = HTTPRequestData(
        method=method,
        url=url,
        headers=headers,
        post_data=post_data,
        redirected_from_url=None,  # No redirect info in Burp export
        redirected_to_url=None,    # No redirect info in Burp export
        is_iframe=False            # No iframe info in Burp export
    )
    
    return HTTPRequest(request_data)

def parse_burp_response(response_text: str, is_base64: bool, url: str, status: int) -> HTTPResponse:
    """Parse raw HTTP response data into a HTTPResponse object"""
    body = None
    body_error = None
    
    try:
        if is_base64:
            decoded_text = base64.b64decode(response_text)
            # Find the empty line that separates headers from body
            headers_end = decoded_text.find(b'\r\n\r\n')
            if headers_end != -1:
                headers_text = decoded_text[:headers_end].decode('utf-8', errors='replace')
                body = decoded_text[headers_end + 4:]  # Skip \r\n\r\n
            else:
                headers_text = decoded_text.decode('utf-8', errors='replace')
        else:
            parts = response_text.split('\n\n', 1)
            headers_text = parts[0]
            body = parts[1].encode('utf-8') if len(parts) > 1 else None
    except Exception as e:
        headers_text = ""
        body_error = f"Error processing response: {str(e)}"
    
    headers = parse_burp_headers(headers_text)
    
    # Create response data
    response_data = HTTPResponseData(
        url=url,
        status=status,
        headers=headers,
        is_iframe=False,  # No iframe info in Burp export
        body=body,
        body_error=body_error
    )
    
    return HTTPResponse(response_data)

def parse_burp_xml(xml_content: str) -> List[HTTPMessage]:
    """Parse a Burp Suite XML export file into an HTTPMessageList"""
    root = ET.fromstring(xml_content)
    messages = []
    
    for item in root.findall('.//item'):
        try:
            # Extract basic information
            url = item.find('url').text
            method = item.find('method').text
            status_elem = item.find('status')
            status = int(status_elem.text) if status_elem is not None else 0
            
            # Parse request
            request_elem = item.find('request')
            is_request_base64 = request_elem.get('base64') == 'true'
            request = parse_burp_request(request_elem.text, is_request_base64, url, method)
            
            # Parse response
            response = None
            response_elem = item.find('response')
            if response_elem is not None and response_elem.text:
                is_response_base64 = response_elem.get('base64') == 'true'
                response = parse_burp_response(response_elem.text, is_response_base64, url, status)
            
            # Create HTTP message
            message = HTTPMessage(request=request, response=response)
            messages.append(message)
        
        except Exception as e:
            print(f"Error parsing item: {e}")
            continue
    
    return messages

def main():
    # Path to the Burp XML file
    burp_file_path = 'histories/burp_requests/test_vulnweb'
    
    # Read the XML content
    with open(burp_file_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    # Extract actual XML content if it's wrapped in document tags
    if '<document_content>' in xml_content:
        start = xml_content.find('<document_content>') + len('<document_content>')
        end = xml_content.find('</document_content>')
        xml_content = xml_content[start:end]
    
    # Parse the XML into HTTPMessageList
    message_list = parse_burp_xml(xml_content)
    
    # Print summary of the parsed data
    print(f"Parsed {len(message_list.messages)} HTTP messages")
    
    # Example: Print details of the first message
    if message_list.messages:
        msg = message_list.messages[0]
        print(f"\nFirst message details:")
        print(f"URL: {msg.url}")
        print(f"Method: {msg.method}")
        print(f"Request headers: {list(msg.request.headers.keys())}")
        if msg.response:
            print(f"Response status: {msg.response.status}")
            print(f"Response headers: {list(msg.response.headers.keys())}")

if __name__ == "__main__":
    main()