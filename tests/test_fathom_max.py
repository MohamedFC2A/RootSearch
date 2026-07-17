"""
Unit tests for Fathom S1 & Fathom Max upgrades
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

# Add parent path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import config
from core.analyzer import AIAnalyzer
from core.search_engine import SearchResult
from core.aggregator import ResultAggregator


class TestFathomUpgrades(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.analyzer = AIAnalyzer()

    def test_config_values(self):
        """Verify the Fathom S1/Max limits are correctly added to config."""
        self.assertEqual(config.fathom_s1_max_sources, 35)
        self.assertEqual(config.fathom_max_nodes, 150)
        self.assertEqual(config.fathom_max_depth, 4)
        self.assertEqual(config.fathom_max_concurrency, 12)
        self.assertEqual(config.results_per_engine, 40)

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_expand_query_fathom_max(self, mock_call_llm):
        """Verify expand_query returns 5 subqueries for Fathom Max and 3 for S1."""
        # 1. Test Fathom Max subquery count
        mock_call_llm.return_value = '["q1", "q2", "q3", "q4", "q5"]'
        subqueries_max = await self.analyzer.expand_query("test", model="fathom_max")
        self.assertEqual(len(subqueries_max), 5)
        self.assertEqual(subqueries_max, ["q1", "q2", "q3", "q4", "q5"])

        # 2. Test Fathom S1 subquery count
        mock_call_llm.return_value = '["q1", "q2", "q3"]'
        subqueries_s1 = await self.analyzer.expand_query("test", model="fathom_s1")
        self.assertEqual(len(subqueries_s1), 3)
        self.assertEqual(subqueries_s1, ["q1", "q2", "q3"])

    @patch('core.analyzer.AIAnalyzer._call_llm')
    async def test_generate_aggregated_report_fathom_max_prompt(self, mock_call_llm):
        """Verify Fathom Max uses the enhanced Super-Reasoning prompt with validation matrix."""
        mock_call_llm.return_value = "Verified Deep Report with ASCII Table"
        
        results = [
            SearchResult(title="R1", url="http://r1.com", snippet="S1", source="google", relevance_score=0.9),
            SearchResult(title="R2", url="http://r2.com", snippet="S2", source="bing", relevance_score=0.8)
        ]
        analyses = [{"url": "http://r1.com", "keywords": ["k1"]}, {"url": "http://r2.com", "keywords": ["k2"]}]

        report = await self.analyzer.generate_aggregated_report(
            results, analyses, "test query", model="fathom_max"
        )
        
        # Verify call_llm was made
        self.assertTrue(mock_call_llm.called)
        # Check across all calls — generate_direct_answer and deep_analysis both call _call_llm
        all_prompts = [call[0][0] for call in mock_call_llm.call_args_list if call[0]]
        fathom_max_prompt = next((p for p in all_prompts if "Fathom Max Ultimate Intelligence Engine" in p), None)
        self.assertIsNotNone(fathom_max_prompt, "Fathom Max prompt not found in any _call_llm call")
        # Check if the prompt contains fathom_max elements
        self.assertIn("Fathom Max Ultimate Intelligence Engine", fathom_max_prompt)
        self.assertIn("Fact-Checking & Contradiction Resolution Matrix", fathom_max_prompt)
        self.assertIn("جدول التحقق من صحة البيانات ومصفوفة المصداقية", fathom_max_prompt)
        
        self.assertEqual(report['deep_analysis'], "Verified Deep Report with ASCII Table")



if __name__ == '__main__':
    unittest.main()
