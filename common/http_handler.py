import asyncio
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
)
from urllib.parse import urlparse

from httplib import HTTPMessage, HTTPRequest, HTTPResponse
from playwright.sync_api import Request, Response

from src.utils import ContentTypeDetector
from logger import get_agent_loggers

agent_log, _ = get_agent_loggers()

BAN_LIST = [
    # 1 Google / DoubleClick
    "doubleclick.net/",
    "googleads.g.doubleclick.net/",
    "googleadservices.com/",
    "/pagead/",
    "/instream/ad_status.js",
    "/td.doubleclick.net/",
    "/collect?tid=",
    "/gtag.",
    # 2 Tag Manager / reCAPTCHA / Cast
    "googletagmanager.com/",
    "google.com/recaptcha/",
    "recaptcha/api",
    "recaptcha/api2",
    "gstatic.com/recaptcha/",
    "gstatic.com/cv/js/sender/",
    # 3 YouTube
    "youtube.com/embed/",
    "youtubei/v1/log_event",
    "youtube.com/iframe_api",
    "youtube.com/youtubei/",
    # 4 Play / WAA
    "play.google.com/log",
    "google.internal.waa.v1.Waa/GenerateIT",
    "jnn-pa.googleapis.com/$rpc",
    # 5 LinkedIn / StackAdapt / Piwik
    "px.ads.linkedin.com/",
    "linkedin.com/attribution_trigger",
    "stackadapt.com/",
    "tags.srv.stackadapt.com/",
    "ps.piwik.pro/",
    "/ppms.php",
]

def is_uninteresting(url: str) -> bool:
    """Return True if *url* contains a substring from BAN_LIST."""
    return any(token in url for token in BAN_LIST)

# --------------------------------------------------------------------------------------
# 2.  HTTP filtering config
# --------------------------------------------------------------------------------------

@dataclass
class HTTPFilterConfig:
    include_mime_types: Sequence[str] = field(default_factory=lambda: ["html", "script", "xml", "flash", "other_text"])
    include_status_codes: Sequence[str] = field(default_factory=lambda: ["2xx", "3xx", "4xx", "5xx"])
    max_payload_size: int | None = 4000


# --------------------------------------------------------------------------------------
# 3.  Main history manager
# --------------------------------------------------------------------------------------

class HTTPFilter:
    """
    Filter a list of HTTPMessage objects (request/response) according to an `HTTPFilter`.
    Only MIME-types explicitly listed in filter.include_mime_types will pass.
    """

    # Content-type predicates keyed by symbolic name
    MIME_TESTS: Dict[str, Callable[[str], bool]] = {
        "html": lambda ct: "text/html" in ct,
        "script": lambda ct: "javascript" in ct or "application/json" in ct,
        "xml": lambda ct: "xml" in ct,
        "flash": lambda ct: "application/x-shockwave-flash" in ct,
        "other_text": lambda ct: re.match(r"text/[^;/]*(;|$)", ct) is not None and "html" not in ct and "xml" not in ct,
        "css": lambda ct: "text/css" in ct,
        "images": lambda ct: "image/" in ct,
        "application/json": lambda ct: "application/json" in ct,
        "other_binary": lambda ct: not (ct.startswith("text/") or ct.startswith("image/") or "javascript" in ct),
    }

    STATUS_TESTS: Dict[str, Callable[[int], bool]] = {
        "2xx": lambda s: 200 <= s < 300,
        "3xx": lambda s: 300 <= s < 400,
        "4xx": lambda s: 400 <= s < 500,
        "5xx": lambda s: 500 <= s < 600,
    }

    # URL substrings that are always ignored (in addition to BAN_LIST)
    URL_FILTERS: Sequence[str] = ("socket.io",)

    def __init__(
        self, 
        http_filter_config: HTTPFilterConfig | None = None, 
        *, 
        logger: logging.Logger | None = None
    ) -> None:
        self.content_detector = ContentTypeDetector()
        self.cfg = http_filter_config or HTTPFilterConfig()


    # TODO: this part is completely fucked
    # ------------------------------------------------------------------ internal helpers
    async def _passes_all_filters(self, msg: "HTTPMessage") -> bool:
        """Evaluate every gate in order and short-circuit on the first failure."""
        url = msg.request.url

        if msg.response is None:
            agent_log.info("Reject %s – no response", msg.request.url)
            return False

        if is_uninteresting(url) or any(pat in url for pat in self.URL_FILTERS):
            agent_log.info("Reject %s – disallowed URL", url)
            return False

        # try:
        import puremagic
        response_body = await msg.response.get_body()
        content_type = puremagic.magic_stream(response_body)
        print("CONTENT TYPE: ", content_type)
        # except Exception:
        #     # Fallback to header-based detection
        #     content_type = msg.response.get_content_type()
        
        agent_log.info("CONTENT TYPE: %s", content_type)
        if not self._mime_allowed(content_type):
            agent_log.info("Reject %s – MIME %s", url, content_type)
            return False
        if not self._status_allowed(msg.response.status):
            agent_log.info("Reject %s – status %s not allowed", url, msg.response.status)
            return False

        if self.cfg.max_payload_size is not None and msg.response.get_response_size() > self.cfg.max_payload_size:
            agent_log.info("Reject %s – payload too large", url)
            return False

        return True

    # ---------------- predicate helpers
    def _mime_allowed(self, content_type: str) -> bool:
        for symbolic in self.cfg.include_mime_types:
            test = self.MIME_TESTS.get(symbolic)
            if test and test(content_type):
                return True
        return False

    def _status_allowed(self, status: int) -> bool:
        for symbolic in self.cfg.include_status_codes:
            test = self.STATUS_TESTS.get(symbolic)
            if test and test(status):
                return True
        return False


DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000
DEFAULT_FLUSH_TIMEOUT       = 5.0    # seconds to wait for all requests to be flushed
DEFAULT_PER_REQUEST_TIMEOUT = 2.0     # seconds to wait for *each* unmatched request
DEFAULT_SETTLE_TIMEOUT      = 1.0     # seconds of network “silence” after the *last* response
POLL_INTERVAL               = 0.5    # how often we poll internal state

# TODO: major error here in response/request matching, unable to pair res/req with absolute confidence
class HTTPHandler:
    def __init__(
        self,
        *,
        banlist: List[str] | None = None,
        scopes: List[str] | None = None,
        http_filter: HTTPFilter | None = None,
    ):
        self._messages: List[HTTPMessage] = []
        self._step_messages: List[HTTPMessage] = []
        self._request_queue: List[HTTPRequest] = []
        self._req_start: Dict[HTTPRequest, float] = {}

        self._ban_substrings: List[str] = banlist or BAN_LIST
        self._ban_list: Set[str] = set()
        self._scopes: List[str] = self._validate_scopes(scopes or [])

        self._http_filter: HTTPFilter = http_filter or HTTPFilter()

    def ingest_messages(self, messages: List[HTTPMessage]):
        self._messages.extend(messages)
        
    def _validate_scopes(self, scopes: List[str]) -> List[str]:
        """Validate that scopes are well-formed URLs. Scheme is optional."""
        validated_scopes = []
        for scope in scopes:
            # If scope doesn't have scheme, add // to make it parse correctly
            if "://" not in scope:
                test_scope = "//" + scope
            else:
                test_scope = scope
                
            parsed = urlparse(test_scope)
            
            # Check that we have at least a netloc (host)
            if not parsed.netloc:
                agent_log.warning(f"Invalid scope '{scope}' - missing host, skipping")
                continue
                
            validated_scopes.append(scope)
            
        return validated_scopes

    async def handle_request(self, http_request: HTTPRequest):
        try:
            url = http_request.url

            self._request_queue.append(http_request)
            self._req_start[http_request] = asyncio.get_running_loop().time()
        except Exception as e:
            agent_log.error("Error handling request: %s", e)

    async def handle_response(self, http_response: HTTPResponse, http_request: HTTPRequest):
        try:
            matching_request = next(
                (req for req in self._request_queue
                 if req.url == http_request.url and req.method == http_request.method),
                None
            )
            if matching_request:
                self._request_queue.remove(matching_request)
                self._req_start.pop(matching_request, None)

            self._step_messages.append(
                HTTPMessage(request=http_request, response=http_response)
            )
        except Exception as e:
            agent_log.error("Error handling response: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────────────────────────────
    def _is_banned(self, url: str) -> bool:
        """Return True if the URL matches any ban-substring or was added at runtime."""
        if url in self._ban_list:
            agent_log.info(f"MSG BANNED: {url}")
            return True
        for s in self._ban_substrings:
            if s in url:
                self._ban_list.add(url)      # cache for fast positive lookup next time
                agent_log.info(f"MSG BANNED: {url}")
                return True

        return False

    def _is_in_scope(self, url: str) -> bool:
        """Return True if scopes are empty or the URL starts with any configured scope prefix."""
        if not self._scopes:
            return True
                
        parsed_url = urlparse(url)

        for scope in self._scopes:
            # If scope doesn't have scheme, add // to make it parse correctly
            if '://' not in scope:
                scope = '//' + scope
                
            parsed_scope = urlparse(scope)
            
            # Check host match
            if parsed_url.netloc != parsed_scope.netloc:
                continue
                
            # Check path is a subpath
            if parsed_url.path.startswith(parsed_scope.path):
                return True
        
        # agent_log.info(f"MSG NOT IN SCOPE: {url}")
        return False

    async def _validate_msg(self, msg: HTTPMessage) -> bool:
        """Validate URL against scope/ban/mime/status/size."""
        if (
            self._is_in_scope(msg.request.url)
            and not self._is_banned(msg.request.url)
            # and await self._http_filter._passes_all_filters(msg)
        ):
            return True
        return False

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
        agent_log.info("Starting HTTP flush")
        loop        = asyncio.get_running_loop()
        start_time  = loop.time()

        last_seen_response_idx = len(self._step_messages)
        last_response_time     = start_time

        print("len of step messages: ", len(self._step_messages))
        print("len of request queue: ", len(self._request_queue))

        while True:
            await asyncio.sleep(POLL_INTERVAL)
            now = loop.time()

            # 0️⃣  Hard timeout check
            if now - start_time >= flush_timeout:
                agent_log.warning(
                    "Flush hit hard timeout of %.1f s; returning immediately", flush_timeout
                )
                break

            # 1️⃣  Per-request time-outs
            for req in list(self._request_queue):
                started_at = self._req_start.get(req, now)
                if now - started_at >= per_request_timeout:
                    agent_log.info("Request timed out: %s", req.url)
                    self._messages.append(HTTPMessage(request=req, response=None))
                    self._request_queue.remove(req)
                    self._req_start.pop(req, None)
                else:
                    agent_log.debug("[REQUEST STAY] %s stay: %.2f s", req.url, now - started_at)

            # 2️⃣  Quiet-period tracking
            if len(self._step_messages) != last_seen_response_idx:
                last_seen_response_idx = len(self._step_messages)
                last_response_time     = now

            # 3️⃣  Exit conditions
            queue_empty  = not self._request_queue
            quiet_enough = (now - last_response_time) >= settle_timeout
            if queue_empty and quiet_enough:
                agent_log.info("Flush complete")
                break

        # ────────────────────────────────────────────────────────────────
        # Finalise
        # ────────────────────────────────────────────────────────────────
        unmatched = [HTTPMessage(request=req, response=None) for req in self._request_queue]
        self._req_start.clear()

        session_msgs = self._step_messages
        self._request_queue = []
        self._step_messages = []

        # keep unmatched only if in scope (no response => cannot pass full filter)
        unmatched_in_scope = [m for m in unmatched if self._is_in_scope(m.request.url)]
        # keep session messages that fully pass scope + filter
        session_valid = [m for m in session_msgs if await self._validate_msg(m)]

        self._messages.extend(unmatched_in_scope)
        self._messages.extend(session_valid)

        # agent_log.info("Returning %d messages from flush (in-scope & filtered)", len(session_valid))
        return session_valid

    def get_history(self) -> List[HTTPMessage]:
        return self._messages