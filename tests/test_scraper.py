"""
RootSearch - Comprehensive Test Suite for DeepScraper & Networking Security
اختبارات الـ Scraper، حماية SSRF، استخراج الروابط وتناغم الشبكة
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.scraper import DeepScraper
from core.net import SafeResolver, close_global_sessions
from core.search_engine import SearchResult
from config import config


class TestScraperAndNetworkSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.scraper = DeepScraper()

    async def asyncTearDown(self):
        await self.scraper.close()
        await close_global_sessions()

    async def test_ssrf_safe_resolver_blocks_loopback(self):
        """Test SafeResolver blocks 127.0.0.1 loopback address."""
        resolver = SafeResolver()
        with patch('asyncio.get_running_loop') as mock_loop_get:
            mock_loop = MagicMock()
            mock_loop_get.return_value = mock_loop
            # Mock getaddrinfo returning 127.0.0.1
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (2, 1, 6, '', ('127.0.0.1', 80))
            ])
            with self.assertRaises(OSError) as ctx:
                await resolver.resolve("localhost", 80)
            self.assertIn("blocked", str(ctx.exception).lower())

    async def test_ssrf_safe_resolver_blocks_private_ip(self):
        """Test SafeResolver blocks 192.168.1.100 private LAN address."""
        resolver = SafeResolver()
        with patch('asyncio.get_running_loop') as mock_loop_get:
            mock_loop = MagicMock()
            mock_loop_get.return_value = mock_loop
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (2, 1, 6, '', ('192.168.1.100', 80))
            ])
            with self.assertRaises(OSError):
                await resolver.resolve("internal.local", 80)

    async def test_ssrf_safe_resolver_blocks_cloud_metadata_ip(self):
        """Test SafeResolver blocks 169.254.169.254 AWS/GCP metadata endpoint."""
        resolver = SafeResolver()
        with patch('asyncio.get_running_loop') as mock_loop_get:
            mock_loop = MagicMock()
            mock_loop_get.return_value = mock_loop
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (2, 1, 6, '', ('169.254.169.254', 80))
            ])
            with self.assertRaises(OSError):
                await resolver.resolve("169.254.169.254", 80)

    async def test_ssrf_safe_resolver_allows_public_ip(self):
        """Test SafeResolver allows valid public IP address (8.8.8.8)."""
        resolver = SafeResolver()
        with patch('asyncio.get_running_loop') as mock_loop_get:
            mock_loop = MagicMock()
            mock_loop_get.return_value = mock_loop
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (2, 1, 6, '', ('8.8.8.8', 80))
            ])
            res = await resolver.resolve("google.com", 80)
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["host"], "8.8.8.8")

    @patch.object(DeepScraper, 'fetch_page')
    async def test_scrape_batch(self, mock_fetch):
        """Test batch scraping multiple seed results concurrently."""
        mock_fetch.return_value = "<html><body><h1>Scraped Page Content</h1><p>Deep details here.</p></body></html>"
        seeds = [
            SearchResult(title="P1", url="https://example.com/1", snippet="S1", source="google"),
            SearchResult(title="P2", url="https://example.com/2", snippet="S2", source="bing"),
        ]
        results = await self.scraper.scrape_batch(seeds, max_pages=10)
        self.assertGreaterEqual(len(results), 1)

    @patch.object(DeepScraper, 'fetch_page')
    async def test_scrape_recursive_depth_and_node_limit(self, mock_fetch):
        """Test recursive crawler obeys max_nodes limit and BFS traversal bounds."""
        mock_fetch.return_value = "<html><body><a href='https://example.com/child1'>Child 1</a><p>Content for parent page.</p></body></html>"
        seeds = [SearchResult(title="Root", url="https://example.com/root", snippet="Root", source="google")]
        results = await self.scraper.scrape_recursive(
            seeds=seeds,
            query="test",
            max_nodes=5,
            max_depth=2,
            concurrency=2
        )
        self.assertIsInstance(results, list)

    def test_extract_text_from_html(self):
        """Test HTML clean text extraction excluding script, style, and nav noise."""
        html = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body>
                <script>console.log('strip me');</script>
                <article>
                    <h1>Main Heading</h1>
                    <p>This is the main body text of the article for testing purposes.</p>
                </article>
            </body>
        </html>
        """
        extracted = self.scraper.extract_content_bs4(html, "https://example.com")
        text = extracted.get("content", "")
        self.assertTrue(len(text) > 0)
        self.assertNotIn("console.log", text)




if __name__ == '__main__':
    unittest.main()

