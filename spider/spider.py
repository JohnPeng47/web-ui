import threading
import queue
import time
from typing import Callable, Iterable, List, Optional, Set, Tuple, Dict
from urllib.parse import urljoin, urlparse, urldefrag
from html.parser import HTMLParser
from dataclasses import dataclass, field

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeoutError
from spider.parsers.html import parse_links

# ──────────────────────────────────────────────────────────────────────────────
# Core HTML link parser — dependency-free, "translate" style:
# Extracts href/src/action URIs from common DOM elements.
# Interface: link_parser(response_html: str) -> List[str]
# ──────────────────────────────────────────────────────────────────────────────

class _HTMLLinkExtractor(HTMLParser):
    ATTR_KEYS = {"href", "src", "action"}

    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        for k, v in attrs:
            if v and k in self.ATTR_KEYS:
                self.links.append(v)


def html_core_link_parser(response_html: str) -> List[str]:
    parser = _HTMLLinkExtractor()
    parser.feed(response_html)
    return parser.links


# ──────────────────────────────────────────────────────────────────────────────
# Logging structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RequestLog:
    url: str
    method: str
    request_headers: Dict[str, str] = field(default_factory=dict)
    status: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    redirected_from: Optional[str] = None
    error: Optional[str] = None
    discovered_links: List[str] = field(default_factory=list)
    fetch_ms: Optional[int] = None


# ──────────────────────────────────────────────────────────────────────────────
# Spider
# ──────────────────────────────────────────────────────────────────────────────

class PlaywrightSpider:
    def __init__(
        self,
        base_url: str,
        seeds: Iterable[str],
        parsers: Optional[List[Callable[[str], List[str]]]] = None,
        chrome_exe_path: Optional[str] = None,
        max_workers: int = 2,
        max_visits: int = 200,
        same_origin_only: bool = True,
        request_timeout_ms: int = 20000,
        headless: bool = True,
        wait_until: str = "domcontentloaded",
    ) -> None:
        """
        base_url: Root URL used for resolution and (optionally) same-origin gating.
        seeds: Initial URLs (can be relative; they will be resolved).
        parsers: List of callables(response_html) -> List[str] that return URIs.
        chrome_exe_path: Path to Chromium/Chrome executable.
        max_workers: Number of parallel browser contexts.
        max_visits: Crawl budget (pages).
        same_origin_only: Restrict to base_url's origin.
        request_timeout_ms: Page.goto timeout per request.
        headless: Launch browser headless.
        wait_until: Playwright wait state ("domcontentloaded", "load", "networkidle").
        """
        self.base_url = base_url.rstrip("/")
        self.base_origin = f"{urlparse(self.base_url).scheme}://{urlparse(self.base_url).netloc}"
        self.same_origin_only = same_origin_only

        self.chrome_exe_path = chrome_exe_path
        self.max_workers = max_workers
        self.max_visits = max_visits
        self.request_timeout_ms = request_timeout_ms
        self.headless = headless
        self.wait_until = wait_until

        self.parsers = parsers or [parse_links]

        # Crawl state
        self._url_queue: "queue.Queue[str]" = queue.Queue()
        self._visited: Set[str] = set()
        if not seeds:
            seeds = [self.base_url]
        for s in seeds:
            print(f"Adding seed: {self._resolve(self.base_url, s)}")
            self._url_queue.put(self._resolve(self.base_url, s))

        # Browser state
        self._p = None
        self._browser: Optional[Browser] = None
        self._contexts: List[BrowserContext] = []

        # Logs
        self.logs: List[RequestLog] = []

        # Coordination
        self._lock = threading.Lock()
        self._stop = False

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def prepare_run(self) -> None:
        """
        Initialize Playwright and a pool of browser contexts.
        Equivalent to the 'with sync_playwright() as p:' pattern, but kept alive.
        """
        self._p = sync_playwright().start()
        launch_kwargs = {
            "headless": self.headless,
        }
        if self.chrome_exe_path:
            launch_kwargs["executable_path"] = self.chrome_exe_path

        # One browser, multiple contexts (lighter than multiple browsers)
        self._browser = self._p.chromium.launch(**launch_kwargs)

        # Pre-create contexts for workers
        for _ in range(self.max_workers):
            ctx = self._browser.new_context()
            self._contexts.append(ctx)

    def run(self) -> None:
        """
        Execute the crawl until queue is empty, stop flag, or budget exhausted.
        """
        if not self._browser or not self._contexts:
            raise RuntimeError("Call prepare_run() before run().")

        workers = []
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker, args=(self._contexts[i],), daemon=True)
            t.start()
            workers.append(t)

        # Wait for queue to drain or budget hit
        try:
            while any(t.is_alive() for t in workers):
                with self._lock:
                    if len(self._visited) >= self.max_visits:
                        self._stop = True
                if self._stop:
                    break
                time.sleep(0.05)
        finally:
            # Cleanup
            for ctx in self._contexts:
                try:
                    ctx.close()
                except Exception:
                    pass
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
            if self._p:
                try:
                    self._p.stop()
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────────────────────
    # Worker / fetch / parse
    # ──────────────────────────────────────────────────────────────────────

    def _worker(self, ctx: BrowserContext) -> None:
        page = ctx.new_page()
        while not self._stop:
            try:
                url = self._url_queue.get(timeout=0.1)
            except queue.Empty:
                # If queue is empty and others may still push, keep spinning
                if self._url_queue.unfinished_tasks == 0:
                    break
                else:
                    continue

            # Dedup and budget
            with self._lock:
                if url in self._visited:
                    self._url_queue.task_done()
                    continue
                if len(self._visited) >= self.max_visits:
                    self._stop = True
                    self._url_queue.task_done()
                    break
                self._visited.add(url)

            log = self._fetch_and_parse(page, url)
            self.logs.append(log)
            self._url_queue.task_done()

        try:
            page.close()
        except Exception:
            pass

    def _fetch_and_parse(self, page: Page, url: str) -> RequestLog:
        start = time.time()
        log = RequestLog(url=url, method="GET")

        try:
            response = page.goto(
                url,
                timeout=self.request_timeout_ms,
                wait_until=self.wait_until,
            )

            # Request info
            if response is not None:
                req = response.request
                log.method = req.method
                try:
                    log.request_headers = dict(req.headers)
                except Exception:
                    pass

                # Response info
                log.status = response.status
                try:
                    log.response_headers = dict(response.headers())
                except Exception:
                    pass

                try:
                    redirected = response.request.redirected_from
                    if redirected:
                        log.redirected_from = redirected.url
                except Exception:
                    pass
            else:
                # Some navigations can return None if it commits cross-process before hook
                pass

            # Content & parse
            html = page.content()
            discovered = self._run_parsers(html)
            resolved = self._resolve_links_bulk(current_url=page.url or url, links=discovered)
            # Enqueue
            self._enqueue_many(resolved)
            log.discovered_links = resolved

        except PWTimeoutError as e:
            log.error = f"timeout: {str(e)}"
        except Exception as e:
            log.error = str(e)
        finally:
            log.fetch_ms = int((time.time() - start) * 1000)

        # Basic console logging (you can replace with your logger)
        self._print_log(log)
        return log

    # ──────────────────────────────────────────────────────────────────────
    # Parsing and URL normalization
    # ──────────────────────────────────────────────────────────────────────

    def _run_parsers(self, html: str) -> List[str]:
        out: List[str] = []
        for parser in self.parsers:
            try:
                out.extend(parser(html) or [])
            except Exception:
                # Parser errors shouldn't kill the crawl
                continue
        # Dedup while preserving order
        seen: Set[str] = set()
        uniq = []
        for u in out:
            if u not in seen:
                uniq.append(u)
                seen.add(u)
        return uniq

    def _resolve_links_bulk(self, current_url: str, links: Iterable[str]) -> List[str]:
        resolved: List[str] = []
        for link in links:
            # Drop fragments and whitespace
            link = (link or "").strip()
            if not link:
                continue
            link, _ = urldefrag(link)

            # Resolve relative to current_url; fallback to base_url if needed
            absolute = self._resolve(current_url, link)
            if not absolute:
                absolute = self._resolve(self.base_url, link)
            if not absolute:
                continue

            if self.same_origin_only:
                if urlparse(absolute).netloc != urlparse(self.base_origin).netloc:
                    continue

            resolved.append(absolute)
        # Dedup preserve order
        seen: Set[str] = set()
        uniq = []
        for u in resolved:
            if u not in seen:
                uniq.append(u)
                seen.add(u)
        return uniq

    @staticmethod
    def _resolve(base: str, maybe_relative: str) -> Optional[str]:
        try:
            if not maybe_relative:
                return None
            if maybe_relative.startswith("javascript:") or maybe_relative.startswith("data:"):
                return None
            # Allow protocol-relative URLs
            if maybe_relative.startswith("//"):
                parsed = urlparse(base)
                return f"{parsed.scheme}:{maybe_relative}"
            return urljoin(base, maybe_relative)
        except Exception:
            return None

    def _enqueue_many(self, urls: Iterable[str]) -> None:
        for u in urls:
            with self._lock:
                if u in self._visited:
                    continue
            self._url_queue.put(u)

    # ──────────────────────────────────────────────────────────────────────
    # Logging
    # ──────────────────────────────────────────────────────────────────────

    def _print_log(self, log: RequestLog) -> None:
        status = log.status if log.status is not None else "-"
        err = f" error={log.error}" if log.error else ""
        print(
            f"[{status}] {log.method} {log.url} ({log.fetch_ms} ms){err} | links={len(log.discovered_links)}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Example usage
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Replace with your Chrome/Chromium path if needed
    CHROME_EXE_PATH = None  # e.g., r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    base = "http://147.79.78.153:8080/"
    seeds = []

    # You can add more parsers; must match signature link_parser(html: str) -> List[str]
    parsers = [parse_links]

    spider = PlaywrightSpider(
        base_url=base,
        seeds=seeds,
        parsers=parsers,
        chrome_exe_path=CHROME_EXE_PATH,
        max_workers=2,
        max_visits=50,
        same_origin_only=True,
        request_timeout_ms=20000,
        headless=True,
        wait_until="domcontentloaded",
    )

    spider.prepare_run()
    spider.run()

    # Access structured logs programmatically
    # for entry in spider.logs:
    #     print(entry)
