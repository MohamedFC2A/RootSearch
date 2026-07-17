"""
Unit tests for the Fathom S1 Cognitive Reasoning Layer
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

# Add current path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.cognitive import (
    DomainCredibilityScorer,
    PhysicalSanityGate,
    DualHeadSemanticGuard,
    AsynchronousMicroJudge,
    CognitiveReasoningPipeline
)


class TestDomainCredibilityScorer(unittest.TestCase):
    def setUp(self):
        self.dcs = DomainCredibilityScorer()

    def test_domain_weight(self):
        # Tier 1
        self.assertEqual(self.dcs.get_domain_weight("https://www.fifa.com/news"), 1.0)
        self.assertEqual(self.dcs.get_domain_weight("https://nasa.gov/about"), 1.0)
        self.assertEqual(self.dcs.get_domain_weight("https://mit.edu"), 1.0)

        # Tier 2
        self.assertEqual(self.dcs.get_domain_weight("https://en.wikipedia.org/wiki/Cristiano_Ronaldo"), 0.7)
        self.assertEqual(self.dcs.get_domain_weight("https://reuters.com"), 0.7)

        # Tier 3
        self.assertEqual(self.dcs.get_domain_weight("https://myblog.wordpress.com"), 0.3)
        self.assertEqual(self.dcs.get_domain_weight(""), 0.3)

    def test_conflict_resolution(self):
        claims = [
            {"value": 187, "unit": "cm", "url": "https://fifa.com", "recurrence": 1},      # Tier 1, wt 1.0, score 1.0
            {"value": 1.87, "unit": "meters", "url": "https://wikipedia.org", "recurrence": 1}, # Tier 2, wt 0.7, score 0.7
            {"value": 1.85, "unit": "meters", "url": "https://blog.com", "recurrence": 1}       # Tier 3, wt 0.3, score 0.3
        ]
        
        resolved = self.dcs.resolve_conflicts("human_height", claims)
        
        # Max score is 1.0. 35% threshold is 0.35.
        # 1.85 meters has score 0.3, which is < 0.35 and should be discarded.
        # 187 cm (1.0) and 1.87 meters (0.7) should be kept.
        values = [r["value"] for r in resolved]
        self.assertIn(187, values)
        self.assertIn(1.87, values)
        self.assertNotIn(1.85, values)


class TestPhysicalSanityGate(unittest.TestCase):
    def setUp(self):
        self.psg = PhysicalSanityGate()

    def test_height_validation(self):
        # Valid height in meters
        valid, val, unit = self.psg.validate_and_calibrate("human_height", 1.87, "meters")
        self.assertTrue(valid)
        self.assertEqual(val, 1.87)
        self.assertEqual(unit, "meters")

        # Invalid height: 187 meters (too tall)
        # Should auto-calibrate: divide by 100 because 187 fits cm -> 1.87 meters
        valid, val, unit = self.psg.validate_and_calibrate("human_height", 187, "meters")
        self.assertTrue(valid)
        self.assertEqual(val, 1.87)
        self.assertEqual(unit, "meters")

        # Invalid height: 1000 meters (cannot calibrate)
        valid, val, unit = self.psg.validate_and_calibrate("human_height", 1000, "meters")
        self.assertFalse(valid)

    def test_weight_validation(self):
        # Valid weight
        valid, val, unit = self.psg.validate_and_calibrate("human_weight", 80, "kg")
        self.assertTrue(valid)
        self.assertEqual(val, 80)


class TestDualHeadSemanticGuard(unittest.TestCase):
    def setUp(self):
        self.dhsg = DualHeadSemanticGuard()

    def test_context_detection(self):
        text = "The height of the player is quite tall, weight is 80kg."
        contexts = self.dhsg.detect_context(text)
        self.assertIn("Physical Dimension", contexts)
        self.assertIn("Measurement", contexts)

    def test_sanitize_text(self):
        # Homograph correction: stock exchange -> inch under Physical Dimension context
        text = "Cristiano Ronaldo height is 187 meters and 1 stock exchange."
        sanitized = self.dhsg.sanitize_text(text)
        self.assertIn("inch", sanitized)
        self.assertNotIn("stock exchange", sanitized)

    def test_sanitize_preserves_legitimate_finance(self):
        # Regression: finance/measurement text must NOT be corrupted just because it
        # mentions size/shares/stock exchange without an adjacent numeric height.
        text = "The New York Stock Exchange size grew as shares rose sharply."
        sanitized = self.dhsg.sanitize_text(text)
        self.assertEqual(sanitized, text)
        self.assertNotIn("inch", sanitized)


class TestAsynchronousMicroJudge(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.amj = AsynchronousMicroJudge()

    async def test_rule_based_fallback(self):
        data = {"text": "Cristiano Ronaldo height is 187 meters and 1 stock exchange."}
        corrected = self.amj.rule_based_fallback(data)
        self.assertEqual(corrected["text"], "Cristiano Ronaldo height is 1.87 meters (6 feet 2 inches).")

    async def test_rule_based_fallback_preserves_finance_and_landmarks(self):
        # Regression: no human-height context => never rewrite "stock exchange",
        # "shares", or a large "N meters" value (e.g. a tower height).
        fin = {"text": "The New York Stock Exchange listed new shares today."}
        self.assertEqual(self.amj.rule_based_fallback(fin)["text"], fin["text"])

        tower = {"text": "The tower is 187 meters tall and iconic."}
        self.assertEqual(self.amj.rule_based_fallback(tower)["text"], tower["text"])


class TestCognitiveReasoningPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pipeline = CognitiveReasoningPipeline()

    async def test_verify_text_full_flow(self):
        input_text = "Cristiano Ronaldo height is 187 meters and 1 stock exchange."
        # Run verification. Should return: "Cristiano Ronaldo height is 1.87 meters (6 feet 2 inches)."
        output_text = await self.pipeline.verify_text(input_text)
        self.assertEqual(output_text, "Cristiano Ronaldo height is 1.87 meters (6 feet 2 inches).")


if __name__ == '__main__':
    unittest.main()
