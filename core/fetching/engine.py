import asyncio
from typing import List, Dict, Any
from core.fetching.HTTP_client import TLSImpersonateClient
from core.fetching.browser_client import HeadlessBrowserEngine
from core.fetching.parser import ContentCleaner

class ResilientFetchEngine:
    def __init__(self, max_concurrency: int = 8, timeout: float = 8.0):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.tls_client = TLSImpersonateClient(timeout=int(timeout))
        self.browser_client = HeadlessBrowserEngine()
        self.timeout = timeout

    async def fetch_single(self, item: Dict[str, Any]) -> Dict[str, Any]:
        url = item.get("url", "")
        if not url:
            item["full_content"] = item.get("content", "")
            item["fetch_successful"] = False
            return item

        async with self.semaphore:
            html = None
            try:
                # Step 1: Fast TLS Impersonated HTTP Request
                html = await asyncio.wait_for(self.tls_client.fetch_html(url), timeout=self.timeout)
            except (asyncio.TimeoutError, Exception):
                html = None

            # Step 2: Fallback to Headless JS Rendering if HTML is missing or empty
            if not html or len(html.strip()) < 500:
                try:
                    html = await asyncio.wait_for(self.browser_client.fetch_dynamic_html(url), timeout=12.0)
                except (asyncio.TimeoutError, Exception):
                    html = None

            # Step 3: Clean content
            cleaned = ContentCleaner.extract_clean_text(html, url) if html else None
            
            item["full_content"] = cleaned["text"] if cleaned else item.get("content", "")
            item["fetch_successful"] = True if cleaned else False
            return item

    async def fetch_all(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self.fetch_single(item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=False)
