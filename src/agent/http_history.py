from httplib import HTTPMessage
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass

import asyncio
from typing import Set, Any

from playwright.sync_api import Request, Response
from httplib import HTTPRequest, HTTPResponse

from logging import getLogger
logger = getLogger(__name__)

BAN_LIST = [
    # 1 Google / DoubleClick
    "doubleclick.net/", "googleads.g.doubleclick.net/", "googleadservices.com/",
    "/pagead/", "/instream/ad_status.js", "/td.doubleclick.net/", "/collect?tid=", "/gtag.",
    # 2 Tag Manager / reCAPTCHA / Cast
    "googletagmanager.com/", "google.com/recaptcha/", "recaptcha/api", "recaptcha/api2",
    "gstatic.com/recaptcha/", "gstatic.com/cv/js/sender/",
    # 3 YouTube
    "youtube.com/embed/", "youtubei/v1/log_event", "youtube.com/iframe_api", "youtube.com/youtubei/",
    # 4 Play / WAA
    "play.google.com/log", "google.internal.waa.v1.Waa/GenerateIT", "jnn-pa.googleapis.com/$rpc",
    # 5 LinkedIn / StackAdapt / Piwik
    "px.ads.linkedin.com/", "linkedin.com/attribution_trigger", "stackadapt.com/", "tags.srv.stackadapt.com/",
    "ps.piwik.pro/", "/ppms.php"
]

def is_uninteresting(url: str) -> bool:
    return any(part in url for part in BAN_LIST)

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

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text", "application/json", "images"]
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

    def __init__(self):
        self.http_filter = HTTPFilter(
            include_mime_types=DEFAULT_INCLUDE_MIME,
            include_status_codes=DEFAULT_INCLUDE_STATUS,
            max_payload_size=MAX_PAYLOAD_SIZE
        )

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
            
            if is_uninteresting(msg.request.url):
                logger.info(f"[FILTER] Excluding {url} - BANNNED!!")
                continue

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

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000
DEFAULT_FLUSH_TIMEOUT       = 5.0    # seconds to wait for all requests to be flushed
DEFAULT_PER_REQUEST_TIMEOUT = 2.0     # seconds to wait for *each* unmatched request
DEFAULT_SETTLE_TIMEOUT      = 1.0     # seconds of network “silence” after the *last* response
POLL_INTERVAL               = 0.5    # how often we poll internal state

class HTTPHandler:
	def __init__(
		self,
		*,
		banlist: List[str] | None = None,
	):
		self._messages: List[HTTPMessage]      = []
		self._step_messages: List[HTTPMessage] = []
		self._request_queue: List[HTTPRequest] = []
		self._req_start: Dict[HTTPRequest, float] = {}

		# URL filter  ───────────────────────────────────────────────────────
		# A simple substring-based ban list imported from a shared module.
		self._ban_substrings: List[str] = banlist or BAN_LIST
		self._ban_list: Set[str]        = set()   # concrete URLs flagged at run-time

	# ─────────────────────────────────────────────────────────────────────
	# Helper
	# ─────────────────────────────────────────────────────────────────────
	def _is_banned(self, url: str) -> bool:
		"""Return True if the URL matches any ban-substring or was added at runtime."""
		if url in self._ban_list:
			return True
		for s in self._ban_substrings:
			if s in url:
				self._ban_list.add(url)      # cache for fast positive lookup next time
				return True
		return False

	# ─────────────────────────────────────────────────────────────────────
	# Browser-callback handlers
	# ─────────────────────────────────────────────────────────────────────
	async def handle_request(self, request: Request):
		try:
			http_request = HTTPRequest.from_pw(request)
			url          = http_request.url

			if self._is_banned(url):
				logger.debug(f"Dropped banned URL: {url}")
				return

			self._request_queue.append(http_request)
			self._req_start[http_request] = asyncio.get_running_loop().time()
		except Exception as e:
			logger.exception("Error handling request: %s", e)

	async def handle_response(self, response: Response):
		try:
			if not response:
				return

			req_match      = HTTPRequest.from_pw(response.request)
			http_response  = HTTPResponse.from_pw(response)

			matching_request = next(
				(req for req in self._request_queue
				 if req.url == response.request.url and req.method == response.request.method),
				None
			)
			if matching_request:
				self._request_queue.remove(matching_request)
				self._req_start.pop(matching_request, None)

			self._step_messages.append(
				HTTPMessage(request=req_match, response=http_response)
			)
		except Exception as e:
			logger.exception("Error handling response: %s", e)

	# ─────────────────────────────────────────────────────────────────────
	# Flush logic with hard timeout
	# ─────────────────────────────────────────────────────────────────────
	async def flush(
		self,
		*,
		per_request_timeout: float = DEFAULT_PER_REQUEST_TIMEOUT,
		settle_timeout:      float = DEFAULT_SETTLE_TIMEOUT,
		flush_timeout:       float = DEFAULT_FLUSH_TIMEOUT,
	) -> List["HTTPMessage"]:
		"""
		Block until either:
		  • all outstanding requests are answered / timed out and the network
			has been quiet for `settle_timeout` seconds, **or**
		  • `flush_timeout` seconds have elapsed in total.
		"""
		logger.info("Starting HTTP flush")
		loop        = asyncio.get_running_loop()
		start_time  = loop.time()

		last_seen_response_idx = len(self._step_messages)
		last_response_time     = start_time

		while True:
			await asyncio.sleep(POLL_INTERVAL)
			now = loop.time()

			# 0️⃣  Hard timeout check
			if now - start_time >= flush_timeout:
				logger.warning(
					"Flush hit hard timeout of %.1f s; returning immediately", flush_timeout
				)
				break

			# 1️⃣  Per-request time-outs
			for req in list(self._request_queue):
				started_at = self._req_start.get(req, now)
				if now - started_at >= per_request_timeout:
					logger.info("Request timed out: %s", req.url)
					self._messages.append(HTTPMessage(request=req, response=None))
					self._request_queue.remove(req)
					self._req_start.pop(req, None)
				else:
					logger.debug("[REQUEST STAY] %s stay: %.2f s", req.url, now - started_at)

			# 2️⃣  Quiet-period tracking
			if len(self._step_messages) != last_seen_response_idx:
				last_seen_response_idx = len(self._step_messages)
				last_response_time     = now

			# 3️⃣  Exit conditions
			queue_empty  = not self._request_queue
			quiet_enough = (now - last_response_time) >= settle_timeout
			if queue_empty and quiet_enough:
				logger.info("Flush complete")
				break

		# ────────────────────────────────────────────────────────────────
		# Finalise
		# ────────────────────────────────────────────────────────────────
		unmatched = [
			HTTPMessage(request=req, response=None) for req in self._request_queue
		]
		self._req_start.clear()

		session_msgs        = self._step_messages
		self._request_queue = []
		self._step_messages = []
		self._messages.extend(unmatched)
		self._messages.extend(session_msgs)

		logger.info("Returning %d messages from flush", len(session_msgs))
		return session_msgs

