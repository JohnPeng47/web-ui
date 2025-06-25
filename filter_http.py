from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from httplib import HTTPMessage

from pentest_bot.logger import get_agent_loggers

_, full_log = get_agent_loggers()

# --------------------------------------------------------------------------------------
# 1.  Global ban-list helpers
# --------------------------------------------------------------------------------------

BAN_LIST: Sequence[str] = (
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
)

def is_uninteresting(url: str) -> bool:
    """Return True if *url* contains a substring from BAN_LIST."""
    return any(token in url for token in BAN_LIST)

# --------------------------------------------------------------------------------------
# 2.  HTTP filtering config
# --------------------------------------------------------------------------------------

@dataclass
class HTTPFilter:
    include_mime_types: Sequence[str] = field(default_factory=lambda: ["html", "script", "xml", "flash", "other_text"])
    include_status_codes: Sequence[str] = field(default_factory=lambda: ["2xx", "3xx", "4xx", "5xx"])
    max_payload_size: int | None = 4000


# --------------------------------------------------------------------------------------
# 3.  Main history manager
# --------------------------------------------------------------------------------------

class HTTPHistory:
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

    def __init__(self, http_filter: HTTPFilter | None = None, *, logger: logging.Logger | None = None) -> None:
        self.cfg = http_filter or HTTPFilter()

    # ------------------------------------------------------------------ public API

    def filter_http_messages(self, messages: List["HTTPMessage"]) -> List["HTTPMessage"]:
        """Return the subset of *messages* that pass every configured gate."""
        allowed: List["HTTPMessage"] = []
        for msg in messages:
            if not self._passes_all_filters(msg):
                continue
            allowed.append(msg)
        return allowed

    # ------------------------------------------------------------------ internal helpers

    def _passes_all_filters(self, msg: "HTTPMessage") -> bool:
        """Evaluate every gate in order and short-circuit on the first failure."""
        if msg.response is None:
            full_log.info("Reject %s – no response", msg.request.url)
            return False

        url = msg.request.url
        if is_uninteresting(url) or any(pat in url for pat in self.URL_FILTERS):
            full_log.info("Reject %s – disallowed URL", url)
            return False

        ct = msg.response.get_content_type()
        if not self._mime_allowed(ct):
            full_log.info("Reject %s – MIME %s not allowed", url, ct)
            return False

        if not self._status_allowed(msg.response.status):
            full_log.info("Reject %s – status %s not allowed", url, msg.response.status)
            return False

        if self.cfg.max_payload_size is not None and msg.response.get_response_size() > self.cfg.max_payload_size:
            full_log.info("Reject %s – payload too large", url)
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