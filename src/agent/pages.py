from typing import Optional, List, Dict, Tuple, Set
from httplib import HTTPMessage, HTTPResponse

from src.utils import get_token_count

# TODO: add plan item here that is related to the 
def concat_output(output_str: str, new_str: str) -> str:
    """Concatenate strings for output with simple base64 redaction.
    - Any base64-looking substring longer than 16 chars is replaced with "<b64>...".
    """
    if not new_str:
        return (output_str or "")
    try:
        import re
        # Base64-looking sequences (A-Z, a-z, 0-9, +, /) with optional padding =, length >= 17
        pattern = r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])"
        redacted = re.sub(pattern, "<b64>...", new_str)
    except Exception:
        redacted = new_str
    return (output_str or "") + redacted

class Page:
    PAYLOAD_RES_SIZE = 1000

    def __init__(
        self, 
        url: str, 
        http_msgs: Optional[List[HTTPMessage]] = None, 
        links: Optional[List[str]] = None,
        page_id: Optional[int] = None
    ):
        self.page_id = page_id
        self.url = url
        # Maintain the raw list for serialization and analysis
        self.http_msgs: List[HTTPMessage] = []
        self.links = links if links is not None else []

        self._groups: Dict[Tuple[str, str], List[HTTPMessage]] = {}
        self._group_order: List[Tuple[str, str]] = []

        if http_msgs:
            for msg in http_msgs:
                self.add_http_msg(msg)

    def add_http_msg(self, msg: HTTPMessage):
        self.http_msgs.append(msg)
        key = (msg.method, msg.url)
        if key not in self._groups:
            self._groups[key] = []
            self._group_order.append(key)
        self._groups[key].append(msg)

    def get_page_item(self, section_number: int):
        """Return an example HTTP request for the given section (1-based)."""
        if section_number <= 0 or section_number > len(self._group_order):
            return None
        key = self._group_order[section_number - 1]
        msgs = self._groups.get(key, [])
        if not msgs:
            return None
        # Return any associated request; choose the most recent
        return msgs[-1].request

    def add_link(self, link: str):
        if link not in self.links:
            self.links.append(link)

    def _truncate_body(self, body: str) -> str:
        if not body:
            return ""
        if len(body) > self.PAYLOAD_RES_SIZE:
            return body[:self.PAYLOAD_RES_SIZE] + "..."
        return body

    def _format_body(self, body_obj) -> str:
        """Return compact string body from dict/bytes/str/other."""
        if body_obj is None:
            return ""
        try:
            # Dict-like
            if isinstance(body_obj, dict):
                import json
                return json.dumps(body_obj, separators=(",", ":"))
            # Bytes
            if isinstance(body_obj, (bytes, bytearray)):
                try:
                    return body_obj.decode("utf-8", errors="replace")
                except Exception:
                    return str(body_obj)
            # String
            if isinstance(body_obj, str):
                return body_obj
            # Fallback
            return str(body_obj)
        except Exception:
            return str(body_obj)

    def _aggregate_headers(self, headers_list: List[Dict[str, str]]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, int]]]:
        """Aggregate headers across a list of header dicts.
        Returns a tuple of:
          - shared headers across all messages: list of (key, latest_value)
          - partial headers: list of (key, latest_value, count_present)
        """
        if not headers_list:
            return [], []

        total = len(headers_list)
        # Track last value and count of presence
        last_value: Dict[str, str] = {}
        present_count: Dict[str, int] = {}

        for hdrs in headers_list:
            if not hdrs:
                continue
            for k, v in hdrs.items():
                last_value[k] = v
                present_count[k] = present_count.get(k, 0) + 1

        shared: List[Tuple[str, str]] = []
        partial: List[Tuple[str, str, int]] = []

        for k, cnt in present_count.items():
            if cnt == total:
                shared.append((k, last_value.get(k, "")))
            else:
                partial.append((k, last_value.get(k, ""), cnt))

        # Keep output stable by sorting keys
        shared.sort(key=lambda x: x[0])
        partial.sort(key=lambda x: x[0])
        return shared, partial

    def _format_headers_section(self, title: str, headers_list: List[Dict[str, str]]) -> str:
        if not headers_list:
            return ""
        shared, partial = self._aggregate_headers(headers_list)
        out = f"{title}\n"
        for k, v in shared:
            out += f"  {k}: {v}\n"
        for k, v, c in partial:
            out += f"  {k}: {v} ({c})\n"
        return out

    def _collect_interesting_headers(self, msgs: List[HTTPMessage]) -> str:
        """Summarize interesting headers across all messages (req/res)."""
        if not msgs:
            return ""
        interesting_keys = {
            "authorization",
            "cookie",
            "set-cookie",
            "content-type",
            "location",
            "x-powered-by",
            "server",
            "cache-control",
            "pragma",
            "expires",
            "x-frame-options",
            "content-security-policy",
            "x-content-type-options",
            "strict-transport-security",
            "access-control-allow-origin",
        }

        req_last: Dict[str, str] = {}
        req_count: Dict[str, int] = {}
        res_last: Dict[str, str] = {}
        res_count: Dict[str, int] = {}

        for m in msgs:
            # Request headers
            rh = getattr(m.request, "headers", {}) or {}
            for k, v in rh.items():
                kl = k.lower()
                if kl in interesting_keys:
                    req_last[kl] = v
                    req_count[kl] = req_count.get(kl, 0) + 1
            # Response headers
            if m.response:
                rsh = getattr(m.response, "headers", {}) or {}
                for k, v in rsh.items():
                    kl = k.lower()
                    if kl in interesting_keys:
                        res_last[kl] = v
                        res_count[kl] = res_count.get(kl, 0) + 1

        if not req_last and not res_last:
            return ""

        out = "Interesting headers:\n"
        if req_last:
            out += "[Request]\n"
            for k in sorted(req_last.keys()):
                out += f"  {k}: {req_last[k]} ({req_count.get(k, 0)})\n"
        if res_last:
            out += "[Response]\n"
            for k in sorted(res_last.keys()):
                out += f"  {k}: {res_last[k]} ({res_count.get(k, 0)})\n"
        return out

    def __str__(self):
        if not self.page_id:
            raise ValueError("Page ID is not set")
        
        output = f"Page: {self.url}\n"

        if not self.http_msgs:
            return output.rstrip()

        http_msgs_out = "HTTP Messages:\n"
        for i, key in enumerate(self._group_order):
            method, url = key
            msgs = self._groups.get(key, [])
            total = len(msgs)
            # Duplicates are extra messages with the same method+url
            duplicates = max(0, total - 1)

            group_header = f"{self.page_id}.{i+1} {method} {url} (msgs:{total}, dups:{duplicates})\n"
            http_msgs_out = concat_output(http_msgs_out, group_header)

            # Aggregate headers
            req_headers_list: List[Dict[str, str]] = [getattr(m.request, "headers", {}) or {} for m in msgs]
            res_headers_list: List[Dict[str, str]] = []
            for m in msgs:
                if m.response:
                    res_headers_list.append(getattr(m.response, "headers", {}) or {})
                else:
                    res_headers_list.append({})

            req_hdrs = self._format_headers_section("[REQ HEADERS]", req_headers_list)
            res_hdrs = self._format_headers_section("[RES HEADERS]", res_headers_list)
            http_msgs_out = concat_output(http_msgs_out, req_hdrs)
            http_msgs_out = concat_output(http_msgs_out, res_hdrs)

            # Unique request bodies
            seen_req: Set[str] = set()
            req_bodies_out = ""
            for m in msgs:
                req_body_str = self._format_body(getattr(m.request, "post_data", None))
                if not req_body_str:
                    continue
                if req_body_str in seen_req:
                    continue
                seen_req.add(req_body_str)
                req_bodies_out += self._truncate_body(req_body_str) + "\n"
            if req_bodies_out:
                http_msgs_out = concat_output(http_msgs_out, "[REQUEST BODIES]\n" + req_bodies_out)

            # Unique response bodies
            seen_res: Set[str] = set()
            res_bodies_out = ""
            for m in msgs:
                if not m.response:
                    continue
                body_obj = getattr(m.response.data, "body", None)
                body_str = self._format_body(body_obj)
                if not body_str:
                    continue
                if body_str in seen_res:
                    continue
                seen_res.add(body_str)
                res_bodies_out += self._truncate_body(body_str) + "\n"
            if res_bodies_out:
                http_msgs_out = concat_output(http_msgs_out, "[RESPONSE BODIES]\n" + res_bodies_out)

        # Append sections to output
        output = concat_output(output, http_msgs_out)

        # Interesting headers section
        interesting = self._collect_interesting_headers(self.http_msgs)
        if interesting:
            output = concat_output(output, interesting)

        return output.rstrip()

    async def to_json(self):
        return {
            "url": self.url,
            "http_msgs": [await msg.to_json() for msg in self.http_msgs],
            "links": self.links
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            url=data["url"],
            http_msgs=[HTTPMessage.from_json(msg) for msg in data["http_msgs"]],
            links=data["links"]
        )

class PageObservations:
    """Important class for holding Pages containing the info observed by the agent during the Discovery phase"""
    def __init__(self, pages: List[Page] = []):
        self.pages: List[Page] = pages
        self.curr_id = 1

        for page in self.pages:
            page.page_id = self.curr_id
            self.curr_id += 1

    def add_page(self, page: Page):
        self.pages.append(page)
        page.page_id = self.curr_id

    def curr_page(self):
        return self.pages[-1]

    def get_page_item(self, compound_id: str):
        page_id = int(compound_id.split(".")[0])
        section_number = int(compound_id.split(".")[1])
        
        page = self.pages[page_id - 1]
        return page.get_page_item(section_number)

    async def to_json(self):
        return [await page.to_json() for page in self.pages]

    @classmethod
    def from_json(cls, data: dict):
        return cls(pages=[Page.from_json(page) for page in data])

    def __str__(self):
        out = ""
        for i, page in enumerate(self.pages):
            out += f"PAGE: {i+1}.\n{str(page)}\n"
        return out
        
