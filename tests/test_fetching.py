import unittest
import asyncio
from core.fetching.HTTP_client import TLSImpersonateClient
from core.fetching.browser_client import HeadlessBrowserEngine
from core.fetching.parser import ContentCleaner
from core.fetching.engine import ResilientFetchEngine

class TestFetchingEngine(unittest.TestCase):
    def test_content_cleaner_trafilatura_or_bs4(self):
        sample_html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <nav>Navbar Links</nav>
                <article>
                    <h1>Main Headline Article</h1>
                    <p>This is a test paragraph containing real text content to be extracted by Trafilatura or BeautifulSoup DOM cleaner.</p>
                    <p>Second paragraph with more interesting technical information for unit testing verification.</p>
                </article>
                <footer>Footer Copyright 2026</footer>
            </body>
        </html>
        """
        cleaned = ContentCleaner.extract_clean_text(sample_html, "https://example.com/test")
        self.assertIsNotNone(cleaned)
        self.assertIn("text", cleaned)
        self.assertIn("Main Headline Article", cleaned["text"])
        self.assertNotIn("Footer Copyright", cleaned["text"])

    def test_resilient_fetch_engine(self):
        engine = ResilientFetchEngine(max_concurrency=2, timeout=3.0)
        items = [
            {"title": "Sample 1", "url": "https://example.com", "content": "Fallback 1"},
            {"title": "Sample 2", "url": "", "content": "Fallback 2"}
        ]
        async def _run():
            results = await engine.fetch_all(items)
            self.assertEqual(len(results), 2)
            self.assertIn("full_content", results[0])
            self.assertIn("full_content", results[1])
        asyncio.run(_run())

if __name__ == "__main__":
    unittest.main()
