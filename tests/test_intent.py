"""
Unit tests for the Query Intent Classifier (core/intent.py)
"""

import sys
import os
import unittest

# Add parent path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.intent import classify_query, ACADEMIC_ENGINES


class TestQueryIntent(unittest.TestCase):
    def test_general_query_excludes_academic_engines(self):
        intent = classify_query("من هو رونالدو")
        self.assertEqual(intent.category, "general")
        # المحركات الأكاديمية يجب ألا تظهر لاستعلام عام
        for eng in ("arxiv", "pubmed", "openalex", "crossref"):
            self.assertNotIn(eng, intent.suggested_engines)

    def test_academic_query_includes_academic_engines(self):
        intent = classify_query("quantum entanglement paper")
        self.assertEqual(intent.category, "academic")
        self.assertIn("arxiv", intent.suggested_engines)
        self.assertIn("pubmed", intent.suggested_engines)

    def test_always_on_engines_present(self):
        for q in ("من هو رونالدو", "quantum entanglement paper", "python async bug"):
            intent = classify_query(q)
            for eng in ("duckduckgo", "startpage", "wikipedia"):
                self.assertIn(eng, intent.suggested_engines)

    def test_temporal_detection_and_years(self):
        intent = classify_query("أحدث أخبار الذكاء الاصطناعي 2024")
        self.assertTrue(intent.is_temporal)
        self.assertIn(2024, intent.query_years)

    def test_code_query_category(self):
        intent = classify_query("python regex function error")
        self.assertEqual(intent.category, "code")
        self.assertIn("stackexchange", intent.suggested_engines)


if __name__ == '__main__':
    unittest.main()
