import unittest
import sys
import os

# Add parent path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.k_trusted import is_domain_authorized, lock_translations, calibrate_physical_values
from core.search_engine import SearchResult

class TestKTrustedPipeline(unittest.TestCase):
    def test_domain_authorization_base(self):
        # Trusted domains
        self.assertTrue(is_domain_authorized("https://nasa.gov/about"))
        self.assertTrue(is_domain_authorized("https://mit.edu/research"))
        self.assertTrue(is_domain_authorized("https://wikipedia.org/wiki/Science"))
        self.assertTrue(is_domain_authorized("https://reuters.com/world"))
        
        # Untrusted/Tier 3 domains
        self.assertFalse(is_domain_authorized("https://reddit.com/r/science"))
        self.assertFalse(is_domain_authorized("https://quora.com/What-is-physics"))
        self.assertFalse(is_domain_authorized("https://myblog.blogspot.com/post-1"))
        self.assertFalse(is_domain_authorized("https://techblog.wordpress.com/about"))

    def test_domain_authorization_dynamic_sports(self):
        # Sports query should allow sports domains
        self.assertTrue(is_domain_authorized("https://kooora.com", query="رياضة كرة القدم"))
        self.assertTrue(is_domain_authorized("https://fifa.com/news", query="football sports"))
        
        # Non-sports query should not allow kooora.com or fifa.com
        self.assertFalse(is_domain_authorized("https://kooora.com", query="quantum physics"))
        self.assertFalse(is_domain_authorized("https://fifa.com/news", query="chemistry formula"))

    def test_translation_lock(self):
        # "Inch/Inches" mistranslated to "بورصة"
        text_with_bug = "شاشة بقياس 55 بورصة مسطحة"
        text_fixed = lock_translations(text_with_bug)
        self.assertEqual(text_fixed, "شاشة بقياس 55 بوصة مسطحة")
        
        text_with_bug2 = "هاتف قياس 6.1 بورصة"
        text_fixed2 = lock_translations(text_with_bug2)
        self.assertEqual(text_fixed2, "هاتف قياس 6.1 بوصة")

    def test_physical_calibration(self):
        # Athlete height listed as 187 meters
        text_with_anomaly = "Cristiano Ronaldo height is 187 meters and 1 inch."
        text_calibrated = calibrate_physical_values(text_with_anomaly)
        self.assertIn("1.87 meters", text_calibrated)
        self.assertNotIn("187 meters", text_calibrated)
        
        # English taller player with height in context
        text_with_anomaly2 = "Ronaldo is a football player, born in Portugal. He is 187 m tall."
        text_calibrated2 = calibrate_physical_values(text_with_anomaly2)
        self.assertIn("1.87 meters", text_calibrated2)
        
        # Arabic athlete height listed as 187 متر
        ar_anomaly = "طوله 187 متر وهو مهاجم بارز"
        ar_calibrated = calibrate_physical_values(ar_anomaly)
        self.assertIn("طوله 1.87 متر", ar_calibrated)
        self.assertNotIn("طوله 187 متر", ar_calibrated)

        # Arabic variant: متراً
        ar_anomaly2 = "يبلغ طول كريستيانو رونالدو 187 متراً"
        ar_calibrated2 = calibrate_physical_values(ar_anomaly2)
        self.assertIn("1.87 متر", ar_calibrated2)

        # Arabic variant: مترًا
        ar_anomaly3 = "اللاعب رونالدو طوله يبلغ 187 مترًا"
        ar_calibrated3 = calibrate_physical_values(ar_anomaly3)
        self.assertIn("1.87 متر", ar_calibrated3)

    def test_k_trust_algorithmic_engine_integration(self):
        # We need an async test wrapper since verify is async
        import asyncio
        from core.k_trusted import KTrustVerificationEngine
        
        engine = KTrustVerificationEngine()
        
        # Test case 1: SCL & DEABS / URE combined
        text_in = "The server is 195 meters tall and uses 5 stock exchanges of memory."
        text_out = asyncio.run(engine.verify(text_in))
        self.assertEqual(text_out, "The server is 1.95 meters tall and uses 5 inches of memory.")
        
        # Test case 2: NLI Contradiction resolution
        query = "Ronaldo height"
        sources = [
            {"url": "https://sports.gov/stats", "content": "Cristiano Ronaldo height is 1.87 meters.", "assertion": "Cristiano Ronaldo is 1.87 meters tall"},
            {"url": "https://untrusted-blog.com", "content": "Ronaldo height is 1.95 meters.", "assertion": "Ronaldo height is 1.95 meters"}
        ]
        text_contradict = "Cristiano Ronaldo is 1.87 meters tall. Ronaldo is 1.95 meters tall."
        resolved = asyncio.run(engine.verify(text_contradict, query=query, sources=sources))
        self.assertIn("1.87 meters", resolved)
        self.assertNotIn("1.95 meters", resolved)
        
        # Test case 3: Deterministic fallback
        sources_empty = []
        fallback_res = asyncio.run(engine.verify("This is an unverified claim.", query=query, sources=sources_empty))
        self.assertEqual(fallback_res, "Data unverified by K-Trust algorithms due to conflicting or unreliable sources.")
        
        # Test case 4: Contested claims matrix rendering
        sources_contested = [
            {"url": "https://sports.gov/stats", "content": "Ronaldo plays football.", "assertion": "Ronaldo plays football"},
            {"url": "https://wikipedia.org", "content": "Ronaldo is 1.87 meters tall best worst obviously opinion.", "assertion": "Ronaldo is 1.87 meters"}
        ]
        text_contested = "Ronaldo plays football. Ronaldo is 1.87 meters tall."
        res_contested = asyncio.run(engine.verify(text_contested, query="Ronaldo", sources=sources_contested))
        self.assertIn("🛡️ K-Trust Consensus Matrix (Contested Claims)", res_contested)
        self.assertIn("wikipedia.org", res_contested)

    def test_lowered_thresholds_accept_paraphrase(self):
        # العتبات المخفّضة (0.10/0.35) تقبل مصدراً متعلقاً بإعادة صياغة
        from core.k_trusted import MathematicalConsensusSolver
        solver = MathematicalConsensusSolver()
        sources = [{
            "url": "https://reuters.com",
            "content": "Cristiano Ronaldo height official profile shows tall stature",
            "assertion": "Ronaldo height is 1.87 m tall officially",
        }]
        fvs, status, details = solver.solve("Ronaldo is 1.87 meters", "Ronaldo height", sources)
        # تشابه الادعاء/التأكيد بين 0.35 و 0.5 — كان سيُرفض سابقاً، ويُقبل الآن
        self.assertNotEqual(status, "Discard")
        self.assertEqual(len(details), 1)

    def test_contested_only_not_false_unverified(self):
        # وجود جمل Contested (دون إجماع Fact) يجب ألا يُرجع "Data unverified"
        import asyncio
        from unittest.mock import patch
        from core.k_trusted import KTrustVerificationEngine
        engine = KTrustVerificationEngine()
        text = "Ronaldo height is around 1.87 meters."
        sources = [{
            "url": "https://reuters.com",
            "content": "Ronaldo height profile stature",
            "assertion": "Ronaldo height around 1.87 meters",
        }]
        # نجبر حالة Contested لضمان ثبات الاختبار بصرف النظر عن ضبط الدرجة
        with patch.object(engine.mcs, "solve", return_value=(0.5, "Contested",
                          [{"url": "https://reuters.com", "r_score": 0.5, "sim_score": 0.5, "bias": 0.0}])):
            out = asyncio.run(engine.verify(text, query="Ronaldo height", sources=sources))
        self.assertNotIn("Data unverified", out)
        self.assertIn("K-Trust Consensus Matrix", out)

if __name__ == '__main__':
    unittest.main()
