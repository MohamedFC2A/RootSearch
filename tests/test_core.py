"""
Fucken Search - Unit Tests Suite
حزمة الاختبارات الآلية للتحقق من كفاءة عمل المشروع
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# إضافة المسار الحالي
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.search_engine import SearchEngine, SearchResult
from core.scraper import DeepScraper
from core.analyzer import AIAnalyzer
from core.aggregator import ResultAggregator
from web.app import app
from fastapi.testclient import TestClient


class TestResultAggregator(unittest.TestCase):
    """اختبارات مجمع النتائج وترتيبها وتطبيع الروابط"""

    def setUp(self):
        self.aggregator = ResultAggregator()

    def test_normalize_url(self):
        """التحقق من تطبيع الروابط وإزالة التكرارات الناتجة عن تتبع الروابط"""
        url1 = "https://www.example.com/path/to/page/"
        url2 = "http://example.com/path/to/page?utm_source=feed&fbclid=123"
        url3 = "https://example.com/path/to/page"
        
        norm1 = self.aggregator.normalize_url(url1)
        norm2 = self.aggregator.normalize_url(url2)
        norm3 = self.aggregator.normalize_url(url3)
        
        self.assertEqual(norm1, "https://example.com/path/to/page")
        self.assertEqual(norm2, "http://example.com/path/to/page")
        self.assertEqual(norm3, "https://example.com/path/to/page")

    def test_merge_duplicates(self):
        """التحقق من دمج النتائج المكررة (نفس الرابط) ورفع نتيجة الأهمية"""
        res1 = SearchResult(
            title="Short Title",
            url="https://example.com/page",
            snippet="Short snippet description.",
            source="google",
            relevance_score=0.8
        )
        res2 = SearchResult(
            title="Much Longer Title That is Better",
            url="https://example.com/page",
            snippet="Much longer snippet description that is far better and detailed.",
            source="bing",
            relevance_score=0.9
        )
        
        merged = self.aggregator.merge_duplicates([res1, res2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].title, "Much Longer Title That is Better")
        self.assertEqual(merged[0].snippet, "Much longer snippet description that is far better and detailed.")
        self.assertEqual(merged[0].relevance_score, 0.9)
        self.assertIn("google", merged[0].source)
        self.assertIn("bing", merged[0].source)

    def test_score_by_domain_authority(self):
        """التحقق من صحة تقييم سلطة المجال وعناوين المواقع الموثوقة"""
        wiki_score = self.aggregator.score_by_domain_authority("https://en.wikipedia.org/wiki/AI")
        gov_score = self.aggregator.score_by_domain_authority("https://nasa.gov/news")
        unknown_score = self.aggregator.score_by_domain_authority("https://randomblog12345.xyz/post")
        
        self.assertEqual(wiki_score, 1.0)
        self.assertEqual(gov_score, 1.0)
        self.assertLess(unknown_score, 0.5)

    def test_score_content_quality(self):
        """التحقق من تقييم جودة المحتوى بناء على الطول والأرقام والتنوع"""
        poor_text = "This is a very short text."
        rich_text = "Artificial Intelligence (AI) has progressed significantly in 2026. " * 30 + " It mentions 100 parameters, 50 algorithms and 10 frameworks."
        
        poor_score = self.aggregator.score_content_quality("", poor_text)
        rich_score = self.aggregator.score_content_quality(rich_text, "")
        
        self.assertGreater(rich_score, poor_score)


class TestAIAnalyzer(unittest.TestCase):
    """اختبارات محلل الذكاء الاصطناعي والمشاعر وتلخيص النصوص"""

    def setUp(self):
        self.analyzer = AIAnalyzer()

    def test_sentiment_analysis(self):
        """التحقق من دقة تحليل المشاعر إيجابي/سلبي/محايد"""
        pos_text = "This search engine is wonderful, excellent and achieves brilliant results!"
        neg_text = "This is terrible, bad, awful and resulted in a complete failure."
        
        pos_sent = self.analyzer.analyze_sentiment(pos_text)
        neg_sent = self.analyzer.analyze_sentiment(neg_text)
        
        self.assertEqual(pos_sent['sentiment'], 'positive')
        self.assertEqual(neg_sent['sentiment'], 'negative')
        self.assertGreater(pos_sent['score'], 0)
        self.assertLess(neg_sent['score'], 0)

    def test_keyword_extraction(self):
        """التحقق من استخلاص الكلمات المفتاحية واستبعاد كلمات التوقف"""
        text = "Apple apple banana fruit fruit fruit and the of in on at apple"
        kws = self.analyzer.extract_keywords_tfidf(text, top_n=3)
        
        self.assertIn("fruit", kws)
        self.assertIn("apple", kws)
        self.assertNotIn("and", kws)

    def test_arabic_sentence_splitting(self):
        """التحقق من التقسيم الصحيح للجمل العربية باستخدام علامة الاستفهام العربية (؟) والسطور الجديدة"""
        text = "ما هو الذكاء الاصطناعي؟ هو فرع من علوم الحاسوب. هل يمكنه التفكير؟ لا، بل يحاكي البشر\nالسطر الجديد هنا."
        summary = self.analyzer._extractive_summary(text, max_length=150)
        
        # التأكد من عدم حدوث استثناء برمي وتحليل الجملة بنجاح
        self.assertTrue(len(summary) > 0)


class TestDeepScraper(unittest.TestCase):
    """اختبارات متسلق المواقع وسحب المحتوى"""

    def setUp(self):
        self.scraper = DeepScraper()

    def test_extract_content_bs4(self):
        """التحقق من سحب النصوص النظيفة باستخدام BeautifulSoup واستبعاد السكربتات"""
        html = """
        <html>
            <head><title>Test Title</title></head>
            <body>
                <header>Navigation bar</header>
                <main>
                    <article>
                        <h1>Main Headline</h1>
                        <p>This is the actual page content that should be extracted from the article.</p>
                        <p>Another paragraphs to ensure length is adequate.</p>
                    </article>
                </main>
                <script>console.log("ignore me");</script>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        extracted = self.scraper.extract_content_bs4(html, "https://example.com")
        
        self.assertEqual(extracted['title'], "Test Title")
        self.assertIn("extracted from the article", extracted['content'])
        self.assertNotIn("Navigation bar", extracted['content'])
        self.assertNotIn("ignore me", extracted['content'])


class TestFastAPIApp(unittest.TestCase):
    """اختبارات خادم FastAPI ونقاط النهاية (API)"""

    def setUp(self):
        self.client = TestClient(app)

    def test_home_endpoint(self):
        """التحقق من أن الصفحة الرئيسية تعمل بشكل طبيعي وتستجيب بـ HTML"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])

    def test_status_endpoint(self):
        """التحقق من استجابة صفحة حالة النظام ببيانات JSON صحيحة"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["name"], "Fucken Search")


class TestSafeResolver(unittest.IsolatedAsyncioTestCase):
    """اختبارات محلل أسماء نطاقات آمن لمنع SSRF"""

    async def test_safe_resolution(self):
        from core.search_engine import SafeResolver
        resolver = SafeResolver()
        
        # المواقع الموثوقة يجب أن تنجح
        try:
            resolved = await resolver.resolve("wikipedia.org")
            self.assertTrue(len(resolved) > 0)
        except Exception as e:
            self.fail(f"Failed to resolve wikipedia.org: {e}")
            
        # العناوين المحلية والخاصة يجب أن تفشل
        with self.assertRaises(OSError):
            await resolver.resolve("localhost")
            
        with self.assertRaises(OSError):
            await resolver.resolve("127.0.0.1")

        with self.assertRaises(OSError):
            await resolver.resolve("192.168.1.1")


if __name__ == "__main__":
    unittest.main()
