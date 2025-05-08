from httplib import HTTPMessage
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass

from logging import getLogger
logger = getLogger(__name__)

@dataclass
class HTTPFilter:
    """Configuration class for HTTP message filtering"""
    
    # Default configurations
    DEFAULT_MIME_TYPES = ["html", "script", "xml", "flash", "other_text"]
    DEFAULT_STATUS_CODES = ["2xx", "3xx", "4xx", "5xx"]
    DEFAULT_MAX_PAYLOAD = 4000

    def __init__(
        self,
        include_mime_types: Optional[List[str]] = None,
        include_status_codes: Optional[List[str]] = None,
        max_payload_size: Optional[int] = DEFAULT_MAX_PAYLOAD
    ):
        self.include_mime_types = include_mime_types or self.DEFAULT_MIME_TYPES
        self.include_status_codes = include_status_codes or self.DEFAULT_STATUS_CODES
        self.max_payload_size = max_payload_size

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text", "application/json"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000

DEFAULT_HTTP_FILTER = HTTPFilter(
    include_mime_types=DEFAULT_INCLUDE_MIME,
    include_status_codes=DEFAULT_INCLUDE_STATUS,
    max_payload_size=MAX_PAYLOAD_SIZE
)

class HTTPHistory:
    """Manages the HTTP history and filters out requests"""
    
    # MIME type filters
    MIME_FILTERS: Dict[str, Callable[[str], bool]] = {
        "html": lambda ct: "text/html" in ct,
        # "script": lambda ct: "javascript" in ct or "application/json" in ct,
        "xml": lambda ct: "xml" in ct,
        "flash": lambda ct: "application/x-shockwave-flash" in ct,
        "other_text": lambda ct: "text/" in ct and not any(x in ct for x in ["html", "xml", "css"]),
        "css": lambda ct: "text/css" in ct,
        "images": lambda ct: "image/" in ct,
        "other_binary": lambda ct: not any(x in ct for x in ["text/", "image/", "application/javascript"]),
        "application/json": lambda ct: "application/json" in ct
    }

    # Status code filters
    STATUS_FILTERS: Dict[str, Callable[[int], bool]] = {
        "2xx": lambda code: 200 <= code < 300,
        "3xx": lambda code: 300 <= code < 400,
        "4xx": lambda code: 400 <= code < 500,
        "5xx": lambda code: 500 <= code < 600
    }

    # URL filters - empty list for patterns to exclude
    URL_FILTERS: List[str] = [
        "socket.io"
    ]

    def __init__(
        self, 
        http_filter: Optional[HTTPFilter] = None
    ):
        self.http_filter = http_filter or HTTPFilter()

    def filter_http_messages(self, messages: List[HTTPMessage]) -> List[HTTPMessage]:
        """
        Filter HTTP messages based on the configured HTTPFilter
        
        Args:
            messages: List of HTTPMessage objects to filter
            
        Returns:
            Filtered list of HTTPMessage objects
        """
        filtered_messages: List[HTTPMessage] = []
        
        for msg in messages:
            if not msg.response:
                logger.info(f"[FILTER] Excluding {msg.request.url} - No response")
                continue
                
            content_type = msg.response.get_content_type()
            payload_size = msg.response.get_response_size()
            status_code = msg.response.status
            url = msg.request.url
            
            # Check URL filters if any exist
            if self.URL_FILTERS and any(pattern in url for pattern in self.URL_FILTERS):
                logger.info(f"[FILTER] Excluding {url} - URL matched URL_FILTERS pattern")
                continue
            
            # Check MIME type filter
            mime_match = False
            for mime_type in self.http_filter.include_mime_types:
                if mime_type in self.MIME_FILTERS and self.MIME_FILTERS[mime_type](content_type):
                    mime_match = True
                    break
            
            if not mime_match:
                logger.info(f"[FILTER] Excluding {msg.request.url} - MIME type {content_type} not in allowed types")
                continue
                
            # Check status code filter
            status_match = False
            for status_range in self.http_filter.include_status_codes:
                if status_range in self.STATUS_FILTERS and self.STATUS_FILTERS[status_range](status_code):
                    status_match = True
                    break
            
            if not status_match:
                logger.info(f"[FILTER] Excluding {msg.request.url} - Status code {status_code} not in allowed ranges")
                continue
                
            # Check payload size filter
            if self.http_filter.max_payload_size is not None and payload_size > self.http_filter.max_payload_size:
                logger.info(f"[FILTER] Excluding {msg.request.url} - Payload size {payload_size} exceeds max {self.http_filter.max_payload_size}")
                continue
                
            filtered_messages.append(msg)

        return filtered_messages