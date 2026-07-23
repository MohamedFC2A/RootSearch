import unittest
import asyncio
from core.aggregator import SourceTrustEvaluator
from core.sources.searxng import SearXNGClient
from core.sources.ddg import DuckDuckGoClient
from core.sources.academic import HeterogeneousDataExtractor

class TestAggregatorAndSources(unittest.TestCase):
    def setUp(self):
        self.evaluator = SourceTrustEvaluator()

    def test_domain_trust_scoring(self):
        edu_score = self.evaluator.calculate_authority_score("https://mit.edu/research")
        gov_score = self.evaluator.calculate_authority_score("https://nasa.gov/news")
        trusted_score = self.evaluator.calculate_authority_score("https://arxiv.org/abs/2101.00001")
        blacklisted_score = self.evaluator.calculate_authority_score("https://content-farm.xyz/spam")

        self.assertGreaterEqual(edu_score, 0.8)
        self.assertGreaterEqual(gov_score, 0.8)
        self.assertGreaterEqual(trusted_score, 0.8)
        self.assertEqual(blacklisted_score, 0.0)

    def test_filter_and_rank(self):
        raw_results = [
            {"title": "Spam Site", "url": "https://content-farm.xyz/page"},
            {"title": "MIT Paper", "url": "https://mit.edu/paper"},
            {"title": "Wiki Page", "url": "https://wikipedia.org/wiki/AI"}
        ]
        ranked = self.evaluator.filter_and_rank(raw_results, threshold=0.3)
        urls = [r["url"] for r in ranked]

        self.assertNotIn("https://content-farm.xyz/page", urls)
        self.assertIn("https://mit.edu/paper", urls)
        self.assertIn("https://wikipedia.org/wiki/AI", urls)

    def test_searxng_client_instantiation(self):
        client = SearXNGClient(instance_urls=["https://invalid-instance.local"])
        async def _run():
            res = await client.search("python")
            self.assertIsInstance(res, list)
        asyncio.run(_run())

    def test_ddg_client_search(self):
        client = DuckDuckGoClient()
        async def _run():
            res = await client.search("test", max_results=2)
            self.assertIsInstance(res, list)
        asyncio.run(_run())

    def test_arxiv_extractor(self):
        async def _run():
            res = await HeterogeneousDataExtractor.fetch_arxiv_papers("quantum computing", max_results=2)
            self.assertIsInstance(res, list)
            if res:
                self.assertIn("url", res[0])
                self.assertIn("title", res[0])
        asyncio.run(_run())

if __name__ == "__main__":
    unittest.main()
