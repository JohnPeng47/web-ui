from typing import Optional, List, Dict, Tuple, Set, Union, Any
from httplib import HTTPMessage
import inspect

# TODO: this should be moved into HTTPMessage so we can use later down the line
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

class PageItem:
    """Generic wrapper that carries a stable string id and a payload item.

    Used to guarantee ordering and id assignment for both pages and http messages.
    """

    def __init__(self, item_id: str, payload: Any):
        self.id: str = item_id
        self.payload: Any = payload

    async def to_json(self):
        item = self.payload
        if hasattr(item, "to_json"):
            result = item.to_json()
            if inspect.iscoroutine(result):
                result = await result
            return {"id": self.id, "item": result}
        return {"id": self.id, "item": item}


class Page:
    PAYLOAD_RES_SIZE = 1000

    def __init__(
        self, 
        url: str, 
        http_msgs: Optional[List[Union[HTTPMessage, PageItem]]] = None, 
        item_id: Optional[str] = None
    ):
        # Single ID system using PageItem-style ids (e.g., "1", "1.2", "1.2.3")
        self.id: str = item_id or ""
        self.url = url
        # Maintain the raw list for serialization and analysis
        self.http_msgs: List[HTTPMessage] = []
        # Parallel list of wrapped items that include stable ids
        self.http_msg_items: List[PageItem] = []

        self._groups: Dict[Tuple[str, str], List[HTTPMessage]] = {}
        self._group_order: List[Tuple[str, str]] = []

        if http_msgs:
            for msg in http_msgs:
                self.add_http_msg(msg)

    def add_http_msg(self, msg: Union[HTTPMessage, PageItem]):
        # Normalize to HTTPMessage and PageItem wrapper
        if isinstance(msg, PageItem):
            raw_msg = msg.payload
            if not isinstance(raw_msg, HTTPMessage):
                # If payload came from JSON, reconstruct HTTPMessage
                try:
                    raw_msg = HTTPMessage.from_json(raw_msg)
                except Exception:
                    raw_msg = raw_msg
            wrapper_id = msg.id or ""
            wrapper = PageItem(wrapper_id, raw_msg)
        else:
            raw_msg = msg
            # Assign nested id if page id known; otherwise temporary empty id to be recalculated later
            wrapper = PageItem("", raw_msg)

        self.http_msg_items.append(wrapper)
        self.http_msgs.append(raw_msg)
        key = (raw_msg.method, raw_msg.url)
        if key not in self._groups:
            self._groups[key] = []
            self._group_order.append(key)
        self._groups[key].append(raw_msg)
        # Recalculate ids if we have a page id
        if self.id:
            self._recalculate_http_msg_ids()

    def _recalculate_http_msg_ids(self):
        if not self.id:
            return
        # Map group key to 1-based group index
        group_index_map: Dict[Tuple[str, str], int] = {
            key: idx + 1 for idx, key in enumerate(self._group_order)
        }
        # Count occurrences within each group to assign the third component
        group_counts: Dict[Tuple[str, str], int] = {}
        for item in self.http_msg_items:
            msg = item.payload
            key = (msg.method, msg.url)
            group_counts[key] = group_counts.get(key, 0) + 1
            section = group_index_map[key]
            item.id = f"{self.id}.{section}.{group_counts[key]}"

    def get_page_item(self, section_number: int) -> Optional[HTTPMessage]:
        """Return an example HTTP request for the given section (1-based)."""
        if section_number <= 0 or section_number > len(self._group_order):
            return None
        key = self._group_order[section_number - 1]
        msgs = self._groups.get(key, [])
        if not msgs:
            return None
        # Return any associated request; choose the most recent
        return msgs[-1]

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
        if not self.id:
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

            group_header = f"{self.id}.{i+1} {method} {url} (msgs:{total}, dups:{duplicates})\n"
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
                try:
                    req_body_obj = m.request.get_body()
                except Exception:
                    req_body_obj = None
                req_body_str = self._format_body(req_body_obj)
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
                try:
                    body_obj = m.response.get_body()
                except Exception:
                    body_obj = None
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
        # Emit only PageItem for http messages; page id is carried by the wrapper at higher level
        return {
            "url": self.url,
            "http_msgs": [await item.to_json() for item in self.http_msg_items],
        }

    @classmethod
    def from_json(cls, data: dict):
        url = data["url"]
        raw_msgs = data.get("http_msgs", [])

        # Determine if entries are wrapped PageItem or raw HTTPMessage json
        normalized: List[Union[HTTPMessage, PageItem]] = []
        for entry in raw_msgs:
            if isinstance(entry, dict) and "id" in entry and "item" in entry:
                # Wrapped item; reconstruct HTTPMessage payload
                payload = entry.get("item")
                if isinstance(payload, dict):
                    http_msg = HTTPMessage.from_json(payload)
                else:
                    http_msg = payload
                normalized.append(PageItem(entry["id"], http_msg))
            else:
                # Legacy raw HTTPMessage json
                if isinstance(entry, dict):
                    normalized.append(HTTPMessage.from_json(entry))
                else:
                    normalized.append(entry)

        return cls(url=url, http_msgs=normalized)

class PageObservations:
    """Important class for holding Pages containing the info observed by the agent during the Discovery phase"""
    def __init__(self, pages: List[Page] = []):
        self.pages: List[Page] = []
        self.pages_items: List[PageItem] = []
        self.curr_id = 1

        for page in pages:
            self.add_page(page)

    def add_page(self, page: Page):
        if not getattr(page, "id", ""):
            page.id = str(self.curr_id)
        self.pages.append(page)
        self.pages_items.append(PageItem(page.id, page))
        self.curr_id += 1
        page._recalculate_http_msg_ids()

    def curr_page(self):
        return self.pages[-1]

    def get_page_item(self, compound_id: str):
        page_id_str = compound_id.split(".")[0]
        section_number = int(compound_id.split(".")[1])
        page = next((p for p in self.pages if p.id == page_id_str), None)
        if not page:
            raise ValueError(f"Page with id {page_id_str} not found")
        return page.get_page_item(section_number)

    def http_msgs(self) -> List[Tuple[str, str]]:
        """Return a list of (method, url) tuples for each http_msg in all pages."""
        result = []
        for page in self.pages:
            for msg in page.http_msgs:
                result.append(msg)
        return result

    async def to_json(self):
        # Emit only PageItem wrappers for pages
        return [await item.to_json() for item in self.pages_items]

    @classmethod
    def from_json(cls, data: dict):
        pages: List[Page] = []
        for entry in data:
            if isinstance(entry, dict) and "id" in entry and "item" in entry:
                # Wrapped PageItem
                page_obj = Page.from_json(entry["item"])
                page_obj.id = entry["id"]
                pages.append(page_obj)
            else:
                # Legacy Page payload
                pages.append(Page.from_json(entry))
        return cls(pages=pages)

    def __str__(self):
        out = ""
        for _, page in enumerate(self.pages):
            out += f"PAGE: {page.id}.\n{str(page)}\n"
        return out
