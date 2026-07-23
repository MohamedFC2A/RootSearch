"""
RootSearch - Comprehensive Test Suite for Search Engine Providers (22+ Engines)
اختبارات دقيقة ومكثفة لجميع محركات البحث ومرونة الاستجابات
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.search_engine import SearchEngine, SearchResult, engine_display_name
from core.net import close_global_sessions
from config import config


class TestSearchEngineProviders(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = SearchEngine()

    async def asyncTearDown(self):
        await self.engine.close()
        await close_global_sessions()

    def test_engine_display_names(self):
        """Verify display name resolution for all engine keys."""
        self.assertEqual(engine_display_name("duckduckgo"), "DuckDuckGo")
        self.assertEqual(engine_display_name("bing"), "DuckDuckGo Lite")
        self.assertEqual(engine_display_name("brave"), "GitHub")
        self.assertEqual(engine_display_name("arxiv"), "arXiv")
        self.assertEqual(engine_display_name("custom_unknown"), "Custom Unknown")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_duckduckgo_parsing(self, mock_fetch):
        """Test DuckDuckGo HTML parsing with valid HTML input."""
        mock_html = """
        <html>
            <div class="result">
                <a class="result__a" href="https://example.com/test">Test Title</a>
                <a class="result__snippet">This is a test snippet for DuckDuckGo.</a>
            </div>
        </html>
        """
        mock_fetch.return_value = mock_html
        results = await self.engine.search_duckduckgo("python", num_results=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].title, "Test Title")
        self.assertEqual(results[0].url, "https://example.com/test")
        self.assertEqual(results[0].source, "duckduckgo")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_duckduckgo_empty(self, mock_fetch):
        """Test DuckDuckGo returning empty or malformed HTML."""
        mock_fetch.return_value = "<html><body>No results</body></html>"
        results = await self.engine.search_duckduckgo("python")
        self.assertEqual(len(results), 0)

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_startpage_fallback(self, mock_fetch):
        """Test Startpage scraper fallback."""
        mock_fetch.return_value = None  # Simulates blocked/rate-limited
        with patch.object(self.engine, 'search_bing', new_callable=AsyncMock) as mock_bing:
            mock_bing.return_value = [
                SearchResult(title="Bing Title", url="https://example.com", snippet="Snippet", source="bing")
            ]
            results = await self.engine.search_startpage("test query")
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].source, "startpage")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_wikipedia(self, mock_fetch):
        """Test Wikipedia API parsing."""
        mock_json = {
            "query": {
                "search": [
                    {
                        "title": "Python (programming language)",
                        "snippet": "Python is a high-level programming language.",
                        "pageid": 23862
                    }
                ]
            }
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_wikipedia("Python")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("wikipedia.org", results[0].url)
        self.assertTrue(results[0].source.startswith("wikipedia"))

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_arxiv(self, mock_fetch):
        """Test arXiv API parsing."""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Attention Is All You Need</title>
            <id>http://arxiv.org/abs/1706.03762v7</id>
            <link href="http://arxiv.org/abs/1706.03762v7" type="text/html"/>
            <summary>The dominant sequence transduction models are based on complex recurrent neural networks.</summary>
          </entry>
        </feed>
        """
        mock_fetch.return_value = mock_xml
        results = await self.engine.search_arxiv("transformer")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "arxiv")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_openalex(self, mock_fetch):
        """Test OpenAlex API response parsing."""
        mock_json = {
            "results": [
                {
                    "display_name": "Deep Learning Paper",
                    "doi": "https://doi.org/10.1038/nature14539",
                    "abstract_inverted_index": {"Deep": [0], "learning": [1]}
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_openalex("deep learning")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "openalex")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_semantic_scholar(self, mock_fetch):
        """Test Semantic Scholar API response parsing."""
        mock_json = {
            "data": [
                {
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "url": "https://www.semanticscholar.org/paper/BERT",
                    "abstract": "We introduce a new language representation model called BERT."
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_semantic_scholar("BERT")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "semantic_scholar")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_pubmed(self, mock_fetch):
        """Test PubMed API response parsing."""
        esearch_json = {"esearchresult": {"idlist": ["30000000"]}}
        esummary_json = {
            "result": {
                "30000000": {
                    "title": "CRISPR Therapeutics in Medicine",
                    "source": "Nature Medicine",
                    "pubdate": "2024"
                }
            }
        }
        mock_fetch.side_effect = [esearch_json, esummary_json]
        results = await self.engine.search_pubmed("CRISPR")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].title, "CRISPR Therapeutics in Medicine")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_wikidata(self, mock_fetch):
        """Test Wikidata API parsing."""
        mock_json = {
            "search": [
                {
                    "id": "Q937",
                    "label": "Albert Einstein",
                    "description": "Theoretical physicist",
                    "concepturi": "http://www.wikidata.org/entity/Q937"
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_wikidata("Einstein")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "wikidata")


    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_crossref(self, mock_fetch):
        """Test CrossRef API parsing."""
        mock_json = {
            "message": {
                "items": [
                    {
                        "title": ["Quantum Computing Basics"],
                        "URL": "https://doi.org/10.1000/182",
                        "abstract": "An overview of quantum computing."
                    }
                ]
            }
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_crossref("quantum")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "crossref")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_core_with_plos_fallback(self, mock_fetch):
        """Test CORE API fallback to PLOS Open Access."""
        mock_fetch.side_effect = [
            None,  # CORE API fails
            {
                "response": {
                    "docs": [
                        {
                            "id": "10.1371/journal.pone.0000000",
                            "title_display": "PLOS Open Access Paper",
                            "abstract": ["Abstract snippet text"]
                        }
                    ]
                }
            }  # PLOS API succeeds
        ]
        results = await self.engine.search_core("genomics")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "core")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_stackexchange(self, mock_fetch):
        """Test StackExchange API parsing."""
        mock_json = {
            "items": [
                {
                    "title": "How to handle asyncio event loops?",
                    "link": "https://stackoverflow.com/questions/12345",
                    "excerpt": "When dealing with asyncio loops..."
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_stackexchange("asyncio")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "stackexchange")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_hackernews(self, mock_fetch):
        """Test HackerNews Algolia API parsing."""
        mock_json = {
            "hits": [
                {
                    "title": "Show HN: RootSearch Deep Search Engine",
                    "url": "https://github.com/example/rootsearch",
                    "story_text": "We built a multi-engine deep search system."
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_hackernews("rootsearch")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "hackernews")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_openlibrary(self, mock_fetch):
        """Test OpenLibrary API parsing."""
        mock_json = {
            "docs": [
                {
                    "title": "Structure and Interpretation of Computer Programs",
                    "key": "/books/OL1234M",
                    "first_sentence": "Computer science is not a science..."
                }
            ]
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_openlibrary("SICP")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "openlibrary")

    @patch('core.search_engine.SearchEngine._fetch')
    async def test_search_internet_archive(self, mock_fetch):
        """Test Internet Archive API parsing."""
        mock_json = {
            "response": {
                "docs": [
                    {
                        "identifier": "archive_test_item",
                        "title": "Archived Historic Web Document",
                        "description": "Historical capture from 2000."
                    }
                ]
            }
        }
        mock_fetch.return_value = mock_json
        results = await self.engine.search_internet_archive("historic doc")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "internet_archive")

    async def test_search_all_resilience(self):
        """Test search_all parallel execution resiliency when some engines throw exceptions."""
        with patch.object(self.engine, 'search_duckduckgo', side_effect=Exception("Network Error")), \
             patch.object(self.engine, 'search_wikipedia', new_callable=AsyncMock) as mock_wiki:
            mock_wiki.return_value = [
                SearchResult(title="Wiki Result", url="https://en.wikipedia.org/wiki/Test", snippet="Snip", source="wikipedia")
            ]
            results = await self.engine.search_all("test query", model="fathom_s1")
            self.assertGreaterEqual(len(results), 1)
            sources = [r.source for r in results]
            self.assertIn("wikipedia", sources)


if __name__ == '__main__':
    unittest.main()
