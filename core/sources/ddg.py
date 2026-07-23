import asyncio
from typing import List, Dict, Any
import logging

logger = logging.getLogger("RootSearch.Sources.DDG")

class DuckDuckGoClient:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def _sync_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        results = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                ddg_gen = ddgs.text(query, max_results=max_results)
                if ddg_gen:
                    for r in ddg_gen:
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "content": r.get("body", ""),
                            "engine": "duckduckgo"
                        })
        except ImportError:
            logger.warning("duckduckgo_search package not installed.")
        except Exception as e:
            logger.warning(f"DDG sync search internal error: {e}")
        return results

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        for attempt in range(1, self.max_retries + 1):
            try:
                # Offload synchronous execution to an executor thread
                res = await loop.run_in_executor(None, self._sync_search, query, max_results)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"DDG Search attempt {attempt} failed: {e}")
                await asyncio.sleep(0.5 * attempt)
        return []
