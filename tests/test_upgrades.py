import unittest
import sys
import os
import asyncio

# Add parent path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.aggregator import ResultAggregator
from core.search_engine import SearchResult, GraphCrawler, SearchEngine
from core.k_trusted import is_domain_authorized, MathematicalConsensusSolver, KTrustVerificationEngine

class TestUpgrades(unittest.TestCase):
    def setUp(self):
        self.aggregator = ResultAggregator()

    def test_arabic_normalization_and_punctuation_stripping(self):
        # 1. Test Arabic normalization & punctuation stripping inside tokenize_and_normalize helper
        text = "رونالدو، أهدافه رائعة! هل هو الأفضل؟"
        tokens = self.aggregator._tokenize_and_normalize(text)
        expected = ["رونالدو", "اهدافه", "رائعه", "هل", "هو", "الافضل"]
        self.assertEqual(tokens, expected)

        # 2. Test punctuation-stripped BM25 matching
        # Query: "ronaldo"
        # Texts: ["Ronaldo.", "Other text"]
        scores = self.aggregator.calculate_bm25_scores(["Ronaldo.", "Other text"], "ronaldo")
        # Ronaldo. should match ronaldo and have a higher score than "Other text"
        self.assertGreater(scores[0], scores[1])
        
        # Test Arabic query matching
        scores_ar = self.aggregator.calculate_bm25_scores(["الرئيس أوباما", "الرئيس اوباما"], "أوباما")
        # both should match due to [أإآ] -> ا normalization
        self.assertGreater(scores_ar[0], 0.0)
        self.assertGreater(scores_ar[1], 0.0)

    def test_semantic_relevance_sorting_priority(self):
        # Test that GraphCrawler.prioritise sets relevance_score directly to score
        crawler = GraphCrawler(query="quantum computer")
        # Create a candidate with high initial score, but very low semantic score
        r1 = SearchResult(title="Irrelevant Wikipedia article", url="https://wikipedia.org/wiki/xyz", snippet="banana apple orange", source="wikipedia_en", relevance_score=0.97)
        r2 = SearchResult(title="Quantum computing intro", url="https://nature.com/articles/123", snippet="A deep dive into quantum computing and quantum physics", source="nature", relevance_score=0.5)

        prioritized = crawler.prioritise([r1, r2])
        # After prioritise, r1 should have low relevance score because "banana apple orange" has no query terms
        self.assertLess(r1.relevance_score, 0.1)
        self.assertGreater(r2.relevance_score, 0.2)

        # In deduplicate_and_sort, the final score should multiply relevance_score * base, preventing overriding
        engine = SearchEngine()
        # Even if r1 had high engine priority (wikipedia is 1.00), its final score will be low (r1.relevance_score * base = 0.02 * 1.0 = 0.02)
        # r2 final score will be higher (r2.relevance_score * base = 0.5 * 0.9 = 0.45)
        # Verify deduplicate_and_sort keeps r2 above r1
        sorted_results = engine.deduplicate_and_sort([r1, r2])
        self.assertEqual(sorted_results[0], r2)

    def test_temporal_intent_detection_and_filtering(self):
        # 1. Test extraction of pub year from metadata
        r_meta = SearchResult(title="Title", url="https://example.com", snippet="Snippet", source="src")
        r_meta.metadata = {"pub_year": "2025"}
        year = self.aggregator._extract_pub_year(r_meta)
        self.assertEqual(year, 2025)

        # 2. Test extraction of pub year from url path
        r_url = SearchResult(title="Title", url="https://example.com/2024/05/12/news", snippet="Snippet", source="src")
        year = self.aggregator._extract_pub_year(r_url)
        self.assertEqual(year, 2024)

        # 3. Test extraction of pub year from snippet
        r_snip = SearchResult(title="Title", url="https://example.com", snippet="Published in 2023.", source="src")
        year = self.aggregator._extract_pub_year(r_snip)
        self.assertEqual(year, 2023)

        # 4. Test rank_results with temporal intent
        # Query with temporal intent word "latest"
        query = "latest AI news"
        # Results: one recent (2025), one old (2018)
        recent_res = SearchResult(title="AI progress 2025", url="https://example.com/2025/02/10", snippet="Recent developments in 2025", source="src", relevance_score=0.5)
        old_res = SearchResult(title="AI history", url="https://example.com/2018/02/10", snippet="Past events in 2018", source="src", relevance_score=0.5)

        # Run rank_results
        ranked = asyncio.run(self.aggregator.rank_results([old_res, recent_res], query))
        # recent_res should be ranked first due to 1.2x boost (age=1 <= 2), while old_res decays
        self.assertEqual(ranked[0], recent_res)

        # Test specific year query boost
        query_2024 = "AI developments in 2024"
        res_2024 = SearchResult(title="AI news", url="https://example.com/2024", snippet="Published in 2024", source="src", relevance_score=0.5)
        res_2025 = SearchResult(title="AI news", url="https://example.com/2025", snippet="Published in 2025", source="src", relevance_score=0.5)
        
        ranked_year = asyncio.run(self.aggregator.rank_results([res_2025, res_2024], query_2024))
        # res_2024 matches the year in query and gets 1.3x boost, which ranks it higher than res_2025 (1.2x boost)
        self.assertEqual(ranked_year[0], res_2024)

    def test_k_trust_domain_auth_and_semantic_relevance(self):
        # 1. Check that new Tier 2 domains are authorized
        self.assertTrue(is_domain_authorized("https://bbc.com/news/123"))
        self.assertTrue(is_domain_authorized("https://nytimes.com/article"))
        self.assertTrue(is_domain_authorized("https://theguardian.com/uk"))

        # 2. Check get_tier_weight for Tier 2 domains returns 0.7
        solver = MathematicalConsensusSolver()
        self.assertEqual(solver.get_tier_weight("https://bbc.com"), 0.7)
        self.assertEqual(solver.get_tier_weight("https://nytimes.com"), 0.7)

        # 3. Check semantic similarity pre-check in solve
        # Query: "Ronaldo height"
        # Claim: "Ronaldo is 1.87m tall"
        # Irrelevant source: bbc.com, content is about BBC stock prices or unrelated news
        irrelevant_sources = [
            {
                "url": "https://bbc.com",
                "content": "BBC stock exchange prices and financial results of the year.",
                "assertion": "Ronaldo is 1.87m tall"
            }
        ]
        fvs, status, details = solver.solve("Ronaldo is 1.87m tall", "Ronaldo height", irrelevant_sources)
        # Should be discarded because query "Ronaldo height" and source content are semantically dissimilar (sim < 0.15)
        self.assertEqual(status, "Discard")
        self.assertEqual(len(details), 0)

        # Relevant source: bbc.com, content is about Ronaldo's height
        relevant_sources = [
            {
                "url": "https://bbc.com",
                "content": "Cristiano Ronaldo height is reported as 1.87m tall in his official profile.",
                "assertion": "Ronaldo is 1.87m tall"
            }
        ]
        fvs2, status2, details2 = solver.solve("Ronaldo is 1.87m tall", "Ronaldo height", relevant_sources)
        self.assertNotEqual(status2, "Discard")
        self.assertEqual(len(details2), 1)

    def test_short_query_zero_match_exclusion(self):
        # استعلام من كلمة واحدة: النتيجة التي لا تطابق الاستعلام تُستبعد
        query = "ronaldo"
        relevant = SearchResult(title="Cristiano Ronaldo", url="https://wikipedia.org/ronaldo",
                                snippet="Cristiano Ronaldo profile and stats", source="wikipedia_en")
        noise = SearchResult(title="Fruit salad", url="https://example.xyz",
                             snippet="banana apple orange", source="searx")
        ranked = asyncio.run(self.aggregator.rank_results([relevant, noise], query))
        urls = [r.url for r in ranked]
        self.assertIn("https://wikipedia.org/ronaldo", urls)
        self.assertNotIn("https://example.xyz", urls)

    def test_irrelevant_batch_filtered_keeps_relevant(self):
        # دفعة كبيرة من الضوضاء لا تطابق الاستعلام تُزال، والنتيجة المتعلقة تبقى
        query = "ronaldo"
        results = [
            SearchResult(title=f"Noise {i}", url=f"https://noise{i}.xyz",
                         snippet="lorem ipsum dolor sit amet", source="searx")
            for i in range(9)
        ]
        results.append(SearchResult(title="Ronaldo", url="https://wikipedia.org/r",
                                    snippet="Cristiano Ronaldo the footballer", source="wikipedia_en"))
        ranked = asyncio.run(self.aggregator.rank_results(results, query))
        urls = [r.url for r in ranked]
        self.assertIn("https://wikipedia.org/r", urls)
        self.assertTrue(all("noise" not in u for u in urls))

    def test_domain_auth_alignment_with_credibility_scorer(self):
        # مواءمة is_domain_authorized مع DomainCredibilityScorer:
        # كل نطاقات الفئة 2 (موسوعية/إعلام موثوق) يجب أن تُصرّح
        from core.cognitive import DomainCredibilityScorer
        dcs = DomainCredibilityScorer()
        for d in dcs.tier2_domains:
            self.assertTrue(is_domain_authorized(f"https://{d}/x"),
                            f"{d} should be authorized via tier2 alignment")
        # نطاقات الفئة 1 المتخصصة تبقى مشروطة بالنية (غير موثوقة دون استعلام رياضي)
        self.assertFalse(is_domain_authorized("https://fifa.com/news", query="chemistry formula"))

if __name__ == '__main__':
    unittest.main()
