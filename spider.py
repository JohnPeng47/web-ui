from typing import List
import httpx
from playwright.async_api import async_playwright

class Spider:
    def __init__(self, start_urls: List[str]):
        self._http_client = httpx.AsyncClient()
        self._browser_client = async_playwright()
