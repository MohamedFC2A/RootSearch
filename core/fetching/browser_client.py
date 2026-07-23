import asyncio
from typing import Optional
import logging

logger = logging.getLogger("RootSearch.Fetching.Browser")

class HeadlessBrowserEngine:
    def __init__(self):
        self._playwright = None

    async def fetch_dynamic_html(self, url: str, timeout: int = 15000) -> Optional[str]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                # Block ads and heavy media assets for speed
                await page.route("**/*.{png,jpg,jpeg,svg,gif,css,woff,woff2}", lambda route: route.abort())
                
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                content = await page.content()
                await browser.close()
                return content
        except ImportError:
            logger.info("Playwright not installed, headless rendering skipped.")
            return None
        except Exception as e:
            logger.error(f"Playwright rendering failed for {url}: {e}")
            return None
