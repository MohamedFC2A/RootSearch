"""
Fucken Search - Result Aggregator Module
مجمع النتائج الخارق: يدمج، يرتب، ويصنف النتائج من جميع المصادر
"""

import re
import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

from config import config
from core.search_engine import SearchResult
from core.analyzer import AIAnalyzer


class ResultAggregator:
    """مجمع النتائج - يدمج ويرتب ويصنف"""
    
    def __init__(self):
        self.analyzer = AIAnalyzer()
    
    def normalize_url(self, url: str) -> str:
        """تطبيع URL لإزالة التكرارات"""
        parsed = urlparse(url)
        # إزالة www.
        netloc = parsed.netloc.replace('www.', '')
        # إزالة '/' النهائي
        path = parsed.path.rstrip('/') if parsed.path != '/' else ''
        # إزالة tracking parameters
        query = parsed.query
        track_params = ['utm_', 'fbclid', 'gclid', 'ref', 'source', 'si']
        if query:
            params = query.split('&')
            clean_params = [p for p in params if not any(t in p for t in track_params)]
            query = '&'.join(clean_params) if clean_params else ''
        
        normalized = f"{parsed.scheme}://{netloc}{path}"
        if query:
            normalized += f"?{query}"
        
        return normalized.lower()
    
    def merge_duplicates(self, results: List[SearchResult]) -> List[SearchResult]:
        """دمج النتائج المكررة (نفس الرابط)"""
        merged = {}
        
        for result in results:
            norm_url = self.normalize_url(result.url)
            
            if norm_url in merged:
                existing = merged[norm_url]
                # دمج المعلومات (أخذ أفضل سنبت وعنوان)
                if len(result.snippet) > len(existing.snippet):
                    existing.snippet = result.snippet
                if len(result.title) > len(existing.title):
                    existing.title = result.title
                # ترقية مصدر التكرار
                existing.source = f"{existing.source}|{result.source}"
                # زيادة درجة الأهمية
                existing.relevance_score = max(existing.relevance_score, result.relevance_score)
                # دمج المحتوى
                if result.content and not existing.content:
                    existing.content = result.content
                elif result.content and existing.content and len(result.content) > len(existing.content):
                    existing.content = result.content
            else:
                merged[norm_url] = result
        
        return list(merged.values())
    
    def score_by_domain_authority(self, url: str) -> float:
        """تقدير سلطة المجال (بدون API خارجي)"""
        domain = urlparse(url).netloc.lower()
        
        # نطاقات عالية الثقة
        high_trust = [
            'wikipedia.org', 'britannica.com', 'reuters.com', 'apnews.com',
            'bbc.com', 'bbc.co.uk', 'nytimes.com', 'wsj.com', 'economist.com',
            'nature.com', 'science.org', 'sciencedaily.com', 'who.int',
            'un.org', 'worldbank.org', 'imf.org', 'oecd.org', 'nasa.gov',
            'nih.gov', 'cdc.gov', 'edu', 'gov', 'ac.uk', 'ac.ae',
        ]
        
        # نطاقات متوسطة الثقة
        medium_trust = [
            'cnn.com', 'theguardian.com', 'washingtonpost.com', 'bloomberg.com',
            'forbes.com', 'techcrunch.com', 'wired.com', 'arstechnica.com',
            'github.com', 'stackoverflow.com', 'medium.com', 'researchgate.net',
            'scholar.google.com', 'pubmed.ncbi.nlm.nih.gov',
        ]
        
        for tld in high_trust:
            if domain.endswith(tld) or domain == tld:
                return 1.0
        
        for tld in medium_trust:
            if domain.endswith(tld) or domain == tld:
                return 0.8
        
        # نطاقات .com العامة
        if domain.endswith('.com'):
            return 0.5
        
        # نطاقات وطنية أخرى
        if domain.endswith(('.org', '.net', '.io', '.ai')):
            return 0.6
        
        return 0.3
    
    def score_content_quality(self, content: Optional[str], snippet: str) -> float:
        """تقدير جودة المحتوى"""
        if not content and not snippet:
            return 0.0
        
        score = 0.0
        text = content or snippet
        
        # طول المحتوى
        word_count = len(text.split())
        if word_count > 1000:
            score += 0.3
        elif word_count > 500:
            score += 0.2
        elif word_count > 100:
            score += 0.1
        
        # وجود أرقام وإحصائيات
        numbers = len(re.findall(r'\d+', text))
        if numbers > 10:
            score += 0.15
        elif numbers > 5:
            score += 0.1
        
        # وجود روابط ومصادر
        links = len(re.findall(r'https?://', text))
        if links > 5:
            score += 0.15
        elif links > 2:
            score += 0.1
        
        # تنوع الكلمات
        unique_words = len(set(text.lower().split()))
        total_words = len(text.split())
        if total_words > 0:
            diversity = unique_words / total_words
            if diversity > 0.5:
                score += 0.1
        
        return min(score, 1.0)
    
    def calculate_bm25_scores(self, texts: List[str], query: str) -> List[float]:
        """تطبيق خوارزمية Okapi BM25 القياسية لترتيب النتائج"""
        if not texts:
            return []
            
        query_terms = [t.lower() for t in query.split() if len(t) > 1]
        if not query_terms:
            return [0.5] * len(texts)
            
        stop_words = {
            'من', 'في', 'على', 'إلى', 'عن', 'مع', 'هذا', 'هذه', 'أن', 'هو', 'هي', 'تم', 'كان',
            'the', 'of', 'and', 'a', 'to', 'in', 'is', 'you', 'that', 'it', 'he', 'was', 'for', 'on'
        }
        semantic_terms = [t for t in query_terms if t not in stop_words]
        if not semantic_terms:
            semantic_terms = query_terms
            
        # Tokenize and compute corpus statistics
        tokenized_texts = [text.lower().split() for text in texts]
        doc_lengths = [len(doc) for doc in tokenized_texts]
        avgdl = sum(doc_lengths) / len(texts) if texts else 1.0
        N = len(texts)
        
        # Calculate IDF for each query term
        idf = {}
        for term in semantic_terms:
            df = sum(1 for doc in tokenized_texts if term in doc)
            # BM25 IDF formula
            idf[term] = math.log(((N - df + 0.5) / (df + 0.5)) + 1)
            
        k1 = 1.5
        b = 0.75
        
        scores = []
        for i, doc in enumerate(tokenized_texts):
            score = 0.0
            dl = doc_lengths[i]
            for term in semantic_terms:
                if term not in doc:
                    continue
                tf = doc.count(term)
                # BM25 TF formula
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (dl / avgdl))
                score += idf[term] * (numerator / denominator)
                
            # Boost for exact phrase matches
            text_str = texts[i].lower()
            phrase_matches = 0
            for j in range(len(query_terms) - 1):
                phrase = ' '.join(query_terms[j:j+2])
                if phrase in text_str:
                    phrase_matches += 1
            
            phrase_boost = (phrase_matches / max(len(query_terms) - 1, 1)) * 2.0
            scores.append(score + phrase_boost)
            
        # Normalize scores to 0-1 range
        max_score = max(scores) if scores else 0
        if max_score > 0:
            scores = [s / max_score for s in scores]
            
        return scores
    
    async def rank_results(self, results: List[SearchResult], query: str) -> List[SearchResult]:
        """ترتيب وتصفية النتائج بدقة فائقة حسب الترابط اللفظي وتجاوز العشوائية"""
        
        # 1. استخراج الكلمات الأساسية من الاستعلام (استبعاد كلمات الإيقاف والرموز)
        stop_words = {
            'من', 'في', 'على', 'إلى', 'عن', 'مع', 'هذا', 'هذه', 'أن', 'هو', 'هي', 'تم', 'كان', 'كانت',
            'the', 'of', 'and', 'a', 'to', 'in', 'is', 'you', 'that', 'it', 'he', 'was', 'for', 'on', 'with', 'at', 'by'
        }
        query_words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 1]
        core_query_terms = [w for w in query_words if w not in stop_words]
        if not core_query_terms:
            core_query_terms = query_words
            
        # Calculate BM25 scores for all results at once
        texts_to_score = [f"{r.title} {r.snippet} {r.content or ''}" for r in results]
        bm25_scores = self.calculate_bm25_scores(texts_to_score, query)
        
        ranked_results = []
        
        for i, result in enumerate(results):
            title_lower = result.title.lower()
            snippet_lower = result.snippet.lower()
            content_lower = (result.content or '').lower()
            full_text = f"{title_lower} {snippet_lower} {content_lower}"
            
            # حساب نسبة الكلمات المطابقة
            matched_terms = [term for term in core_query_terms if term in full_text]
            match_ratio = len(matched_terms) / len(core_query_terms) if core_query_terms else 1.0
            
            # إقصاء حازم: إذا كان الاستعلام مركباً من 3 كلمات أساسية فأكثر، ونسبة المطابقة أقل من 60%، نستبعد النتيجة تماماً
            if len(core_query_terms) >= 3 and match_ratio < 0.6:
                continue
                
            # حساب التواجد المشترك في نفس الجملة (Co-occurrence)
            sentences = re.split(r'[.!?؟\n]', full_text)
            max_co_occurring = 0
            for sentence in sentences:
                sentence_matches = sum(1 for term in core_query_terms if term in sentence)
                if sentence_matches > max_co_occurring:
                    max_co_occurring = sentence_matches
            
            # معامل العقوبة عند تشتت الكلمات (مثلاً: وجود الكلمة الأولى دون الثانية في الاستعلامات الثنائية)
            penalty = 1.0
            if len(core_query_terms) >= 2 and len(matched_terms) < len(core_query_terms):
                penalty = 0.15
                
            # معامل التجاوز والربط المشترك (Proximity/Co-occurrence Boost)
            boost = 1.0
            if len(core_query_terms) >= 2 and max_co_occurring >= 2:
                boost = 1.0 + (max_co_occurring / len(core_query_terms)) * 1.8
            
            # دمج جميع عوامل التقييم
            authority_score = self.score_by_domain_authority(result.url)
            quality_score = self.score_content_quality(result.content, result.snippet)
            relevance_score = bm25_scores[i] if i < len(bm25_scores) else 0.0
            
            # الوزن النهائي المطور بالفلترة المتقدمة والعقوبات
            final_score = (
                relevance_score * 0.40 +
                authority_score * 0.25 +
                quality_score * 0.20 +
                result.relevance_score * 0.15  # وزن المصدر الأصلي
            )
            
            # تطبيق العقوبات والتحفيزات
            final_score = final_score * penalty * boost
            
            result.relevance_score = round(final_score, 4)
            ranked_results.append(result)
        
        # ترتيب حسب النتيجة النهائية
        ranked_results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        return ranked_results
    
    async def categorize_results(self, results: List[SearchResult]) -> Dict[str, List[SearchResult]]:
        """تصنيف النتائج إلى فئات"""
        categories = {
            'articles': [],
            'videos': [],
            'social': [],
            'academic': [],
            'news': [],
            'code': [],
            'products': [],
            'other': [],
        }
        
        for result in results:
            url = result.url.lower()
            domain = urlparse(url).netloc.lower()
            
            # تصنيف حسب المحتوى والنطاق
            if any(site in url for site in ['youtube.com', 'vimeo.com', 'dailymotion.com', 'twitch.tv']):
                categories['videos'].append(result)
            elif any(site in url for site in ['facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'reddit.com', 'tiktok.com', 'linkedin.com']):
                categories['social'].append(result)
            elif any(site in url for site in ['scholar.google.com', 'pubmed.', 'arxiv.org', 'researchgate.net', 'academia.edu', 'doi.org', '.edu', '.ac.']):
                categories['academic'].append(result)
            elif any(site in url for site in ['github.com', 'gitlab.com', 'stackoverflow.com', 'pypi.org', 'npmjs.com']):
                categories['code'].append(result)
            elif any(site in url for site in ['amazon.com', 'ebay.com', 'walmart.com', 'etsy.com', 'aliexpress.com']) or any(ext in url for ext in ['/product/', '/shop/', '/buy/']):
                categories['products'].append(result)
            elif any(site in url for site in ['news', 'cnn.com', 'bbc.com', 'reuters.com', 'apnews.com']) or '/news/' in url:
                categories['news'].append(result)
            elif any(ext in url for ext in ['/article/', '/blog/', '/post/', '/story/']):
                categories['articles'].append(result)
            else:
                categories['other'].append(result)
        
        # إزالة الفئات الفارغة
        return {k: v for k, v in categories.items() if v}
    
    async def aggregate(self, results: List[SearchResult], query: str, final_analysis: bool = True) -> Dict[str, Any]:
        """تجميع كامل للنتائج مع التحليل والتصنيف"""
        
        # 1. دمج المكررات
        results = self.merge_duplicates(results)
        
        if not results:
            return {
                'query': query,
                'results': [],
                'total_results': 0,
                'categories': {},
                'analysis': None,
                'message': 'لم يتم العثور على نتائج',
            }
        
        # 2. ترتيب النتائج
        ranked_results = await self.rank_results(results, query)
        
        # 3. تصنيف النتائج
        categorized = await self.categorize_results(ranked_results)
        
        top_results = ranked_results[:config.max_final_results]
        
        if final_analysis:
            # 4. تحليل أفضل النتائج بالذكاء الاصطناعي
            analyses = await self.analyzer.analyze_results_batch(top_results)
            # 5. إنشاء تقرير شامل
            report = await self.analyzer.generate_aggregated_report(top_results, analyses, query)
        else:
            # تقرير مبدئي سريع للتحديث التراكمي الحي
            report = {
                'summary': 'جاري استخراج ودمج البيانات المعرفية في الخلفية...',
                'executive_summary': 'جاري استخراج ودمج البيانات المعرفية في الخلفية...',
                'deep_analysis': 'جاري بناء الشبكة المعرفية...',
                'keywords': self.analyzer.extract_keywords_tfidf(" ".join([r.title + " " + r.snippet for r in top_results]), 12) if top_results else [],
                'statistics': {
                    'sources_used': {r.source: 1 for r in top_results}
                }
            }
        
        return {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'total_results': len(ranked_results),
            'total_unique': len(results),
            'results': [self._result_to_dict(r) for r in top_results],
            'categories': {k: [self._result_to_dict(r) for r in v] for k, v in categorized.items()},
            'analysis': report,
        }
    
    def _result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        """تحويل نتيجة إلى قاموس"""
        return {
            'title': result.title,
            'url': result.url,
            'snippet': result.snippet,
            'source': result.source,
            'relevance_score': result.relevance_score,
            'content': result.content or '',
            'content_preview': (result.content or '')[:500] if result.content else '',
            'content_length': len(result.content or ''),
            'content_type': result.content_type,
            'metadata': result.metadata,
        }
