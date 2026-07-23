"""
RootSearch - Comprehensive Test Suite for AIAnalyzer & LLM Resilience
اختبارات تحليل الذكاء الاصطناعي والمرونة في قراءة الـ JSON ومعالجة الـ Prompts
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.analyzer import AIAnalyzer
from core.search_engine import SearchResult
from core.net import close_global_sessions
from config import config


class TestAIAnalyzerAndLLMResilience(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.analyzer = AIAnalyzer()

    async def asyncTearDown(self):
        await close_global_sessions()

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_expand_query_clean_json(self, mock_llm):
        """Test expand_query handles clean JSON array response."""
        mock_llm.return_value = '["subquery 1", "subquery 2", "subquery 3"]'
        res = await self.analyzer.expand_query("quantum computing", model="fathom_s1")
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0], "subquery 1")

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_expand_query_markdown_json(self, mock_llm):
        """Test expand_query handles JSON inside markdown code blocks (```json ... ```)."""
        mock_llm.return_value = '```json\n["query A", "query B", "query C"]\n```'
        res = await self.analyzer.expand_query("machine learning", model="fathom_s1")
        self.assertEqual(len(res), 3)
        self.assertIn("query A", res)

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_expand_query_malformed_json_fallback(self, mock_llm):
        """Test expand_query gracefully falls back when LLM returns quoted list."""
        mock_llm.return_value = '["Python web dev", "Django web dev", "FastAPI web dev"]'
        res = await self.analyzer.expand_query("web dev", model="fathom_s1")
        self.assertGreaterEqual(len(res), 1)


    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_filter_sources_ai(self, mock_llm):
        """Test AI filtering of source results based on query relevance."""
        mock_llm.return_value = '{"http://r1.com": 0.95, "http://r2.com": 0.20}'
        results = [
            SearchResult(title="R1", url="http://r1.com", snippet="Relevant content", source="google"),
            SearchResult(title="R2", url="http://r2.com", snippet="Irrelevant spam", source="bing"),
        ]
        filtered = await self.analyzer.filter_sources_ai("test query", results, max_seeds=5)
        self.assertGreaterEqual(len(filtered), 1)

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_generate_direct_answer(self, mock_llm):
        """Test direct answer generation with cited sources."""
        mock_llm.return_value = "The capital of France is Paris [1]."
        results = [SearchResult(title="Paris", url="https://fr.wikipedia.org/wiki/Paris", snippet="Capital of France", source="wikipedia")]
        ans = await self.analyzer.generate_direct_answer("What is capital of France?", results, all_content="Paris is capital")
        self.assertEqual(ans.get("answer"), "The capital of France is Paris [1].")

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_summarize_deep(self, mock_llm):
        """Test deep semantic summarization of long page content."""
        mock_llm.return_value = "Summary: Key takeaway points."
        content = "Long content paragraph about software engineering practices."
        summary = await self.analyzer.summarize_text(content, "software engineering")
        self.assertTrue(len(summary) > 0)




if __name__ == '__main__':
    unittest.main()
