import asyncio
from typing import Optional
import logging

logger = logging.getLogger("RootSearch.Fetching.HTTP")

class TLSImpersonateClient:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    async def fetch_html(self, url: str, proxy: Optional[str] = None) -> Optional[str]:
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome120") as s:
                response = await s.get(
                    url,
                    timeout=self.timeout,
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                    }
                )
                if response.status_code == 200:
                    return response.text
                return None
        except ImportError:
            # Fallback to httpx if curl_cffi is not installed
            try:
                import httpx
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers=headers)
                    if response.status_code == 200:
                        return response.text
            except Exception as e:
                logger.warning(f"httpx fallback fetch failed for {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"TLS impersonate fetch failed for {url}: {e}")
            return None
