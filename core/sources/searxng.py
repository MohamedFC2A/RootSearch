import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel

logger = logging.getLogger("RootSearch.Sources.SearXNG")

class SearXNGResult(BaseModel):
    title: str
    url: str
    content: str
    engine: str = "searxng"
    score: float = 1.0
    published_date: Optional[str] = None
    category: Optional[str] = None

class SearXNGClient:
    def __init__(self, instance_urls: Optional[List[str]] = None, timeout: float = 5.0):
        self.instance_urls = instance_urls or [
            "https://searx.be",
            "https://searx.space",
            "https://searx.prvcy.eu"
        ]
        self.timeout = timeout

    async def search(self, query: str, categories: Optional[List[str]] = None, max_results: int = 15) -> List[SearXNGResult]:
        if categories is None:
            categories = ["general"]

        params = {
            "q": query,
            "format": "json",
            "categories": ",".join(categories),
            "language": "en-US",
        }
        for instance in self.instance_urls:
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(f"{instance.rstrip('/')}/search", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        results = []
                        for item in data.get("results", [])[:max_results]:
                            results.append(SearXNGResult(
                                title=item.get("title", ""),
                                url=item.get("url", ""),
                                content=item.get("content", ""),
                                engine=item.get("engine", "searxng"),
                                score=item.get("score", 1.0),
                                published_date=item.get("publishedDate")
                            ))
                        if results:
                            return results
            except Exception as e:
                logger.warning(f"SearXNG instance {instance} failed: {e}. Trying next fallback instance.")
        return []
