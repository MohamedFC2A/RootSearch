"""
Fucken Search - AI Analysis Module
محلل الذكاء الاصطناعي الخارق: يحلل، يلخص، ويستخرج المعلومات
"""

import asyncio
import re
import json
import base64
import aiohttp
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from config import config
from core.search_engine import SearchResult

# ─────────────────────────────────────────────────────────────
#  GLOBAL SHARED CONNECTION POOL FOR DEEPSEEK
# ─────────────────────────────────────────────────────────────
_session_lock = asyncio.Lock()
_global_session: Optional[aiohttp.ClientSession] = None

async def _get_global_session() -> aiohttp.ClientSession:
    """إرجاع جلسة اتصال HTTP مشتركة ومستقرة لإعادة استخدام اتصالات TCP"""
    global _global_session
    if _global_session is None or _global_session.closed:
        async with _session_lock:
            if _global_session is None or _global_session.closed:
                # حد أقصى للاتصالات المتزامنة 100 مع كاش DNS طويل
                connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
                _global_session = aiohttp.ClientSession(connector=connector)
    return _global_session

async def close_global_session():
    """إغلاق الجلسة المشتركة بشكل نظيف عند إيقاف السيرفر"""
    global _global_session
    if _global_session is not None and not _global_session.closed:
        async with _session_lock:
            if _global_session is not None and not _global_session.closed:
                await _global_session.close()
                _global_session = None


class AIAnalyzer:
    """محلل الذكاء الاصطناعي - يعالج النصوص ويفهمها"""
    
    def __init__(self, on_event=None):
        self.on_event = on_event
        self.nlp_initialized = False
        self._init_lock = asyncio.Lock()
    
    async def initialize(self):
        """تهيئة نماذج الذكاء الاصطناعي (تحميل أول مرة)"""
        if self.nlp_initialized:
            return
        
        async with self._init_lock:
            if self.nlp_initialized:
                return
            
            try:
                # تهيئة الجلسة المشتركة مسبقاً
                await _get_global_session()
                
                if config.deepseek_api_key:
                    print(f"[*] تم تهيئة نموذج DeepSeek بنجاح كالمزود الأساسي: {config.deepseek_model}")
                else:
                    print("[!] تحذير: DEEPSEEK_API_KEY غير متوفر في الإعدادات.")
                
                self.nlp_initialized = True
                    
            except Exception as e:
                print(f"[!] تعذر تهيئة مزود الـ AI: {e}")
                self.nlp_initialized = True

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """استدعاء DeepSeek كنموذج أساسي وحيد للتحليل والتلخيص"""
        # 1. محاولة استخدام GLM Colab أولاً إذا تم اختياره وتوفر الرابط
        if config.llm_provider == "glm_colab" and config.glm_api_url:
            try:
                url = f"{config.glm_api_url.rstrip('/')}/v1/chat/completions"
                headers = {"Content-Type": "application/json"}
                if config.glm_api_key:
                    headers["Authorization"] = f"Bearer {config.glm_api_key}"
                
                payload = {
                    "model": "glm-4-9b-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
                
                session = await _get_global_session()
                async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        if content:
                            return content.strip()
                    else:
                        print(f"[⚠️] فشل الاتصال بخادم GLM Colab: رمز الحالة {response.status}")
            except Exception as e:
                print(f"[⚠️] خطأ أثناء الاتصال بـ GLM Colab: {e}")
            
            print("[ℹ/⚠️] محاولة الرجوع التلقائي إلى DeepSeek...")

        # 2. الاستدعاء الأساسي لـ DeepSeek
        if config.deepseek_api_key:
            return await self._call_deepseek(prompt)
        
        return None
    
    async def _call_deepseek(self, prompt: str) -> Optional[str]:
        """استدعاء DeepSeek عبر واجهة متوافقة مع OpenAI باستخدام الجلسة المشتركة"""
        if not config.deepseek_api_key:
            return None
        import random
        url = f"{config.deepseek_api_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.deepseek_api_key}",
        }
        payload = {
            "model": config.deepseek_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": False,
        }
        
        session = await _get_global_session()
        max_retries = 5
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=payload, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                        return None
                    # 429 تجاوز الحد — إعادة المحاولة مع تأخير متزايد
                    if response.status == 429 and attempt < max_retries - 1:
                        sleep_time = random.uniform(2.0, 4.0 * (2 ** attempt))
                        print(f"[⚠️] DeepSeek rate limit (429). Retrying in {sleep_time:.2f}s... ({attempt+1}/{max_retries})")
                        await asyncio.sleep(sleep_time)
                        continue
                    err = await response.text()
                    if config.deepseek_api_key:
                        err = err.replace(config.deepseek_api_key, "[REDACTED_API_KEY]")
                    print(f"[⚠️] فشل الاتصال بـ DeepSeek: رمز {response.status} — {err[:300]}")
                    return None
            except Exception as e:
                err_msg = str(e)
                if config.deepseek_api_key:
                    err_msg = err_msg.replace(config.deepseek_api_key, "[REDACTED_API_KEY]")
                print(f"[⚠️] خطأ أثناء الاتصال بـ DeepSeek: {err_msg}")
                # For network errors, retry as well if we have attempts left
                if attempt < max_retries - 1:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    continue
                return None
        return None
    
    def extract_keywords_tfidf(self, text: str, top_n: int = 20, idf_dict: Optional[Dict[str, float]] = None) -> List[str]:
        """استخراج الكلمات المفتاحية باستخدام TF-IDF حقيقي"""
        # كلمات إيقاف متعددة اللغات
        stop_words = set([
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'is', 'it', 'as', 'be', 'by', 'that', 'this', 'with', 'from',
            'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do',
            'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'shall', 'can', 'need', 'dare', 'ought', 'used', 'about', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'between',
            'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
            'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
            'not', 'if', 'because', 'while', 'although', 'though', 'after', 'until',
            # كلمات عربية
            'في', 'من', 'إلى', 'عن', 'على', 'كان', 'كانت', 'لم', 'لن', 'له', 'لها',
            'هم', 'هن', 'هو', 'هي', 'أن', 'إن', 'ما', 'لا', 'هل', 'بـ', 'ب', 'لـ',
            'ل', 'و', 'ف', 'ثم', 'أو', 'أي', 'ذلك', 'هذا', 'هذه', 'الذي', 'التي',
            'الذين', 'اللواتي', 'اللائي', 'اللذين', 'اللتين', 'به', 'بها', 'بهم',
            'منه', 'منها', 'منهم', 'عنه', 'عنها', 'عنهم', 'له', 'لها', 'لهم',
        ])
        
        # تنظيف النص
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # تصفية كلمات الإيقاف والكلمات القصيرة
        filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
        
        # حساب التردد TF
        word_freq = Counter(filtered_words)
        
        # حساب TF-IDF
        tfidf_scores = {}
        for word, count in word_freq.items():
            tf = count / len(filtered_words) if filtered_words else 0
            idf = idf_dict.get(word, 1.0) if idf_dict else 1.0
            tfidf_scores[word] = tf * idf
            
        # فرز حسب النتيجة
        sorted_words = sorted(tfidf_scores.items(), key=lambda item: item[1], reverse=True)
        
        # إرجاع أهم الكلمات
        return [word for word, _ in sorted_words[:top_n]]
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """استخراج الكيانات (أسماء، أماكن، تواريخ، إلخ) باستخدام تعابير منتظمة"""
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'urls': [],
            'emails': [],
            'phones': [],
            'money': [],
            'percentages': [],
        }
        
        # استخراج URLs
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        entities['urls'] = list(set(re.findall(url_pattern, text)))
        
        # استخراج الإيميلات
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities['emails'] = list(set(re.findall(email_pattern, text)))
        
        # استخراج أرقام الهواتف
        phone_pattern = r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        entities['phones'] = list(set(re.findall(phone_pattern, text)))
        
        # استخراج التواريخ
        date_patterns = [
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},?\s?\d{4}',
            r'\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}',
        ]
        for pattern in date_patterns:
            entities['dates'].extend(re.findall(pattern, text, re.IGNORECASE))
        
        # استخراج العملات
        money_pattern = r'[\$€£¥]\s?\d+(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:,\d{3})*(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|JPY|دولار|يورو|جنيه)'
        entities['money'] = list(set(re.findall(money_pattern, text)))
        
        # استخراج النسب المئوية
        pct_pattern = r'\d+(?:\.\d+)?\s?%'
        entities['percentages'] = list(set(re.findall(pct_pattern, text)))
        
        # استخراج أسماء الأشخاص (نمط بسيط: كلمة كبيرة + كلمة كبيرة)
        person_pattern = r'[A-Z][a-z]+ [A-Z][a-z]+'
        potential_persons = re.findall(person_pattern, text)
        # نأخذ فقط ما يظهر أكثر من مرة
        person_counts = Counter(potential_persons)
        entities['persons'] = [p for p, c in person_counts.most_common(10) if c > 1]
        
        # استخراج أسماء المنظمات (نمط: كلمات كبيرة)
        org_pattern = r'(?:[A-Z][a-z]* ){1,3}(?:Inc|Corp|LLC|Ltd|Company|Group|International|Foundation|Organization|Institute|University|Association|Agency|Bank|Fund)'
        entities['organizations'] = list(set(re.findall(org_pattern, text)))
        
        return entities
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """تحليل المشاعر (إيجابي/سلبي/محايد) باستخدام قاموس المشاعر مع دعم النفي والتحليلات العاطفية والموضوعية"""
        positive_words = set([
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'superb',
            'outstanding', 'remarkable', 'exceptional', 'magnificent', 'brilliant',
            'awesome', 'incredible', 'perfect', 'beautiful', 'love', 'best',
            'success', 'successful', 'achievement', 'breakthrough', 'innovation',
            'positive', 'growth', 'profit', 'benefit', 'advantage', 'improve',
            'improvement', 'progress', 'advance', 'development', 'opportunity',
            'happy', 'pleased', 'satisfied', 'impressive', 'efficient', 'effective',
            'ممتاز', 'رائع', 'جيد', 'عظيم', 'جميل', 'ناجح', 'مذهل', 'مبدع',
            'استثنائي', 'متفوق', 'أفضل', 'إنجاز', 'تقدم', 'نجاح', 'فرصة',
            'ممتازة', 'رائعة', 'جيدة', 'عظيمة', 'جميلة', 'ناجحة', 'مذهلة',
        ])
        
        negative_words = set([
            'bad', 'terrible', 'awful', 'horrible', 'dreadful', 'poor', 'worse',
            'worst', 'hateful', 'disgusting', 'revolting', 'abysmal', 'atrocious',
            'failure', 'failed', 'lose', 'lost', 'loss', 'damage', 'damaged',
            'destroy', 'destroyed', 'destruction', 'crisis', 'problem', 'problems',
            'issue', 'issues', 'difficult', 'struggle', 'struggling', 'suffer',
            'suffering', 'negative', 'decline', 'decrease', 'reduce', 'reduction',
            'threat', 'danger', 'dangerous', 'risk', 'warning', 'emergency',
            'سيء', 'سيئة', 'فظيع', 'مروع', 'كارثة', 'مشكلة', 'خطير', 'خطر',
            'فشل', 'فاشل', 'خسارة', 'تدمير', 'أزمة', 'صعب', 'معاناة', 'مشاكل',
            'ضعيف', 'متدهور', 'انهيار', 'ضرر', 'تهديد',
        ])
        
        negation_words = set([
            'not', 'no', 'never', 'none', 'neither', 'nor', 'hardly', 'scarcely',
            'لا', 'لم', 'لن', 'ليس', 'غير', 'دون', 'بدون'
        ])
        
        neutral_modifiers = set([
            'maybe', 'perhaps', 'possibly', 'probably', 'might', 'could',
            'ربما', 'قد', 'يمكن', 'يحتمل',
        ])
        
        # الكلمات الدالة على العواطف المتنوعة
        trust_words = set([
            'expert', 'proven', 'scientific', 'study', 'data', 'factual', 'trust', 'credible',
            'honest', 'reliable', 'authority', 'source', 'confirm', 'confirmed', 'evidence',
            'موثوق', 'علمي', 'دراسة', 'بيانات', 'مؤكد', 'خبير', 'أبحاث', 'صدق', 'حقيقة', 'أدلة',
            'مصدر', 'توثيق', 'ثقة', 'برهان', 'براهين'
        ])
        
        anger_words = set([
            'furious', 'disastrous', 'fail', 'scam', 'illegal', 'worst', 'angry', 'hate', 'fury',
            'rage', 'destroy', 'offend', 'offensive', 'attack', 'abuse', 'violence',
            'سيء', 'فشل', 'احتيال', 'غضب', 'أسوأ', 'تدمير', 'هجوم', 'عنف', 'كره', 'كراهية',
            'اعتداء', 'إساءة', 'مسيء'
        ])
        
        fear_words = set([
            'threat', 'dangerous', 'risk', 'crisis', 'scared', 'terror', 'anxiety', 'panic',
            'warning', 'scary', 'worry', 'afraid', 'unsafe', 'vulnerable',
            'خطر', 'أزمة', 'خوف', 'تهديد', 'قلق', 'تحذير', 'رعب', 'ذعر', 'مخاوف', 'مخيف',
            'هشاشة', 'ضعف', 'تهديدات'
        ])
        
        joy_words = set([
            'excited', 'breakthrough', 'success', 'praise', 'amazing', 'happy', 'wonderful',
            'delight', 'glad', 'celebrate', 'victory', 'optimistic', 'optimism', 'excellent',
            'نجاح', 'رائع', 'سعيد', 'تفاؤل', 'ممتاز', 'انتصار', 'فرح', 'بهجة', 'سرور',
            'احتفال', 'أمل', 'إيجابي'
        ])
        
        sadness_words = set([
            'sad', 'regret', 'lost', 'decline', 'depressed', 'sadness', 'grief', 'sorrow',
            'unfortunate', 'unfortunately', 'disappointed', 'disappointment',
            'حزين', 'خسارة', 'إحباط', 'أسف', 'تراجع', 'بؤس', 'كآبة', 'معاناة', 'ألم',
            'خيبة', 'للأسف'
        ])
        
        # الكلمات الدالة على الذاتية مقابل الموضوعية
        subjective_words = set([
            'i', 'we', 'my', 'our', 'me', 'us', 'think', 'believe', 'opinion', 'personally',
            'feel', 'guess', 'suppose', 'seems', 'view',
            'أعتقد', 'نرى', 'رأيي', 'شخصياً', 'في اعتقادي', 'أظن', 'أشعر', 'أرى', 'من وجهة نظري'
        ])
        
        objective_words = set([
            'percent', 'data', 'research', 'evidence', 'study', 'statistics', 'showed', 'results',
            'source', 'according', 'analysis', 'reported', 'document',
            'نسبة', 'دراسة', 'أبحاث', 'إحصائيات', 'أدلة', 'نتائج', 'وفقاً', 'تحليل', 'وثيقة',
            'تقرير', 'تقارير', 'مصادر'
        ])
        
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        # عداد العواطف
        trust_count = 0
        anger_count = 0
        fear_count = 0
        joy_count = 0
        sadness_count = 0
        
        # عداد الذاتية والموضوعية
        subj_count = 0
        obj_count = 0
        
        skip_next = False
        
        for i, w in enumerate(words):
            if skip_next:
                skip_next = False
                continue
                
            is_negated = False
            # Look behind up to 2 words for negations
            for j in range(max(0, i-2), i):
                if words[j] in negation_words:
                    is_negated = True
                    break
                    
            if w in positive_words:
                if is_negated:
                    negative_count += 1
                else:
                    positive_count += 1
            elif w in negative_words:
                if is_negated:
                    positive_count += 1
                else:
                    negative_count += 1
            elif w in neutral_modifiers:
                neutral_count += 1
                
            # عداد العواطف الدقيقة مع النفي
            if w in trust_words:
                trust_count += 1
            if w in anger_words:
                if is_negated:
                    joy_count += 1
                else:
                    anger_count += 1
            if w in fear_words:
                fear_count += 1
            if w in joy_words:
                if is_negated:
                    sadness_count += 1
                else:
                    joy_count += 1
            if w in sadness_words:
                if is_negated:
                    joy_count += 1
                else:
                    sadness_count += 1
                    
            # عداد الذاتية والموضوعية
            if w in subjective_words:
                subj_count += 1
            if w in objective_words:
                obj_count += 1
        
        total = positive_count + negative_count + neutral_count
        
        # حساب معدل الذاتية والموضوعية
        total_subj_obj = subj_count + obj_count
        if total_subj_obj > 0:
            subjectivity = subj_count / total_subj_obj
            objectivity = obj_count / total_subj_obj
        else:
            subjectivity = 0.3
            objectivity = 0.7
            
        if total == 0:
            return {
                'sentiment': 'neutral',
                'score': 0.0,
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'subjectivity': round(subjectivity, 2),
                'objectivity': round(objectivity, 2),
                'emotions': {
                    'trust': trust_count,
                    'anger': anger_count,
                    'fear': fear_count,
                    'joy': joy_count,
                    'sadness': sadness_count
                }
            }
        
        positive_score = positive_count / total
        negative_score = negative_count / total
        neutral_score = neutral_count / total
        
        # تحديد المشاعر السائدة
        if positive_score > negative_score and positive_score > neutral_score:
            sentiment = 'positive'
        elif negative_score > positive_score and negative_score > neutral_score:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        # درجة المشاعر من -1 إلى 1
        overall_score = (positive_count - negative_count) / (positive_count + negative_count + 1)
        overall_score = max(-1, min(1, overall_score))
        
        return {
            'sentiment': sentiment,
            'score': overall_score,
            'positive': positive_count,
            'negative': negative_count,
            'neutral': neutral_count,
            'subjectivity': round(subjectivity, 2),
            'objectivity': round(objectivity, 2),
            'emotions': {
                'trust': trust_count,
                'anger': anger_count,
                'fear': fear_count,
                'joy': joy_count,
                'sadness': sadness_count
            }
        }
    
    async def generate_direct_answer(
        self,
        query: str,
        top_results: list,
        all_content: str,
        k_trusted: bool = False,
    ) -> dict:
        """
        Generate a direct, authoritative, reference-grade answer for the given query.
        Returns a dict with keys:
          - 'answer':   str — the direct answer text (Markdown allowed, ≤5 sentences)
          - 'sources':  list of {title, url, domain} — top cited sources
          - 'verified': bool — True if K-Trust verified
          - 'confidence': float 0-1
        """
        if not top_results:
            return {'answer': '', 'sources': [], 'verified': k_trusted, 'confidence': 0.0}

        # Build a compact source block for the prompt (title + domain + snippet)
        from urllib.parse import urlparse
        source_lines = []
        cited_sources = []
        for i, r in enumerate(top_results[:8], 1):
            url   = getattr(r, 'url', '') or ''
            title = getattr(r, 'title', '') or ''
            snip  = (getattr(r, 'snippet', '') or getattr(r, 'content', '') or '')[:400]
            domain = urlparse(url).netloc or getattr(r, 'source', '')
            source_lines.append(f"[مصدر {i}] {title} ({domain})\n{snip}")
            cited_sources.append({'title': title, 'url': url, 'domain': domain})

        sources_block = "\n\n".join(source_lines)

        verification_clause = ""
        if k_trusted:
            verification_clause = (
                "\n⚠️ هام جداً - أنت في وضع K-Trust الصارم للتحقق الفائق:\n"
                "1. لا تذكر أي حقيقة أو رقم أو تاريخ أو حدث ما لم يكن مدعوماً ومثبتاً بشكل متطابق من مصدرين مستقلين وموثوقين على الأقل من المصادر أدناه.\n"
                "2. إذا وجد أي اختلاف أو تعارض بين المصادر في الأرقام أو التواريخ أو الأسماء، لا تحاول التخمين بل اذكر التعارض صراحةً بالتفصيل مع الإشارة للمصادر (مثال: 'تذكر بعض المصادر كذا بينما تذكر مصادر أخرى كذا').\n"
                "3. تجنب تماماً الصياغات العامة والإنشائية، وركز فقط على المعلومات الموثقة والمحققة بنسبة 100%."
            )

        prompt = f"""أنت محرك إجابات مرجعية فورية. مهمتك: قدّم الإجابة المباشرة والصحيحة لاستعلام المستخدم بناءً على المصادر أدناه.

قواعد صارمة لا تحيد عنها:
1. الإجابة يجب أن تكون مباشرة ودقيقة — ابدأ بالحقيقة فوراً، لا مقدمات ولا حشو.
2. الحد الأقصى 5 جمل موجزة. لا تشرح آلية عملك ولا تعيد صياغة السؤال.
3. اذكر الأرقام والحقائق الدقيقة (أوزان، أطوال، تواريخ، نسب) بوحداتها الصحيحة دائماً.
4. إذا كانت الإجابة غير موجودة في المصادر، قل: "لا تتوفر بيانات موثوقة كافية للإجابة على هذا الاستعلام."
5. لا تخترع ولا تستنتج ولا تضيف معلومات خارج المصادر المقدمة.
6. استخدم العربية الفصحى الواضحة.{verification_clause}

الاستعلام: {query}

المصادر:
{sources_block}

الإجابة المرجعية المباشرة:"""

        try:
            if not self.nlp_initialized:
                await self.initialize()
            answer_text = await self._call_llm(prompt)
            if answer_text:
                answer_text = answer_text.strip()
                # Confidence heuristic: high if we have many sources and k_trusted
                confidence = min(1.0, 0.6 + 0.05 * len(top_results) + (0.1 if k_trusted else 0))
                return {
                    'answer': answer_text,
                    'sources': cited_sources[:5],
                    'verified': k_trusted,
                    'confidence': round(confidence, 2),
                }
        except Exception as e:
            print(f"[!] generate_direct_answer failed: {e}")

        # Fallback: best snippet from top result
        if top_results:
            r = top_results[0]
            snip = (getattr(r, 'snippet', '') or '')[:350]
            from urllib.parse import urlparse
            domain = urlparse(getattr(r, 'url', '')).netloc or getattr(r, 'source', '')
            return {
                'answer': snip or 'لا تتوفر بيانات موثوقة كافية للإجابة على هذا الاستعلام.',
                'sources': cited_sources[:3],
                'verified': False,
                'confidence': 0.3,
            }
        return {'answer': '', 'sources': [], 'verified': False, 'confidence': 0.0}

    async def summarize_text(self, text: str, max_length: int = 300, min_length: int = 50, query: str = "", is_synthesis: bool = False) -> str:
        """تلخيص النص باستخدام AI (مع fallback لتقنية الاستخراج)"""
        if not text or len(text) < 100:
            return text
        
        # تنظيف النص
        text = text[:15000]  # حد أقصى 15k حرف
        
        # محاولة استخدام نموذج AI
        if config.use_ai_analysis:
            try:
                if not self.nlp_initialized:
                    await self.initialize()
                
                if is_synthesis:
                    prompt = f"""You are a master cognitive synthesizer for the RootSearch deep intelligence search engine.
Your task is to analyze the gathered search results for the query \"{query}\" and generate a highly organized, world-class synthesis report in modern Arabic.

Strictly organize the report using the following structure:

# التلخيص المعرفي والتحليل الشامل للموضوع: {query}

## النظرة العامة والتحليل التنفيذي (Executive Summary)
> [!NOTE]
> *اكتب فقرة مقتضبة، مركزة، وعالية القيمة تلخص صلب الموضوع وأهميته.*

## النقاط الرئيسية والحقائق المثبتة (Key Core Insights)
* **[نقطة رئيسية 1]**: تفصيل مختصر ومباشر مدعوم بالبيانات.
* **[نقطة رئيسية 2]**: تفصيل مختصر ومباشر مدعوم بالبيانات.
* **[نقطة رئيسية 3]**: تفصيل مختصر ومباشر مدعوم بالبيانات.

## السياق الدلالي والأبعاد المحيطة (Contextual Dimensions)
*اكتب تحليلاً للمحاور الجانبية المرتبطة بالاستعلام وكيف تتقاطع مع الموضوع الأساسي.*

---
*تأكد من استخدام تنسيق Markdown بشكل احترافي، وترك سطر فارغ بين كل فقرة أو عنصر لتفادي التصاق النصوص.*

المحتوى المجمع من المصادر:
{text}"""
                else:
                    # Expert Data Extraction and Fact-Checking Prompt
                    prompt = f"""You are an expert Data Extraction and Fact-Checking AI. Your task is to process scraped search engine snippets or webpage text, filter out low-quality web noise, and extract highly accurate, standardized data points based on the query: \"{query}\".

Strictly adhere to the following data engineering and pipeline rules:

1. ANTI-SEO & NOISE FILTERING:
- Strip away and completely ignore any boilerplate content, ads, navigation links, or completely regional/generic text.
- Focus solely on sentences/facts that directly answer the query.

2. UNIT STANDARDIZATION & HUMAN SANITY CHECKS:
- Convert and normalize all measurements into standard metrics (e.g., Height in centimeters/meters, Weight in kilograms).
- Perform logical physical boundary checks on human attributes. For example, if a human's height is stated as > 2.5 meters (like "187 meters"), automatically recognize this as a typo for centimeters and correct it to standard format (e.g., 187 cm or 1.87 m).
- Beware of common localization/translation bugs. For example, ensure the Arabic word "بورصة" (financial stock market) is contextualized and corrected to "inch/bouse" (بوصة) when processing measurement data.

3. CONFLICT RESOLUTION & WEIGHTED CONSENSUS:
- Prioritize globally recognized, structured databases and encyclopedias (like Wikipedia or official sports registries) over generic blogs or ad-heavy content sites. 
- Focus on extracting consensus values backed by high-authority sources.

4. STRICT CONTEXTUAL RELEVANCE (ANTI-BLEEDING):
- Ensure that the primary entity in the source matches the user's query intent. Do not extract data about a completely different entity.

5. OUTPUT STRUCTURING:
- Output your verified summary, key facts, or final structured data clearly in modern Arabic, free from typos, mixed units, or chaotic textual noise. Keep it concise, professional, and directly answering the query.

Webpage content to process:
{text}"""
                
                summary = await self._call_llm(prompt)
                if summary:
                    return summary.strip()
            except Exception as e:
                print(f"[!] AI processing failed: {e}")
        
        # Fallback: تلخيص بالاستخراج
        return self._extractive_summary(text, max_length)
    
    def _split_text(self, text: str, chunk_size: int = 1024) -> List[str]:
        """تقسيم النص إلى أجزاء متساوية"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_size += len(word) + 1
            if current_size > chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = len(word)
            else:
                current_chunk.append(word)
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks if chunks else [text]
    
    def _extractive_summary(self, text: str, max_length: int = 300) -> str:
        """تلخيص بالاستخراج - اختيار أهم الجمل"""
        # تقسيم إلى جمل مع دعم اللغة العربية وعلامات الاستفهام والسطور الجديدة
        sentences = re.split(r'(?<=[.!?؟\n])\s+', text)
        
        if len(sentences) <= 3:
            return text
        
        # حساب وزن كل جملة
        sentence_scores = []
        keywords = self.extract_keywords_tfidf(text, top_n=30)
        
        for i, sentence in enumerate(sentences):
            if len(sentence) < 10:
                continue
            
            score = 0
            sentence_lower = sentence.lower()
            
            # وزن بالكلمات المفتاحية
            for kw in keywords:
                if kw.lower() in sentence_lower:
                    score += 1
            
            # وزن بموقع الجملة (أول الجمل أهم)
            position_weight = 1 - (i / len(sentences)) * 0.5
            score *= position_weight
            
            # وزن بطول الجملة
            length_weight = min(1, len(sentence) / 150)
            score *= length_weight
            
            sentence_scores.append((score, sentence))
        
        # ترتيب حسب الأهمية
        sentence_scores.sort(reverse=True, key=lambda x: x[0])
        
        # اختيار أفضل الجمل مع الحفاظ على الطول المطلوب
        selected = []
        current_length = 0
        
        for score, sentence in sentence_scores:
            if current_length + len(sentence) <= max_length:
                selected.append(sentence)
                current_length += len(sentence)
        
        if not selected:
            selected = [sentence_scores[0][1]] if sentence_scores else [sentences[0]]
        
        # إعادة ترتيب حسب الظهور الأصلي
        selected.sort(key=lambda s: sentences.index(s) if s in sentences else 0)
        
        # تنسيق الجمل كنقاط رئيسية واضحة مفصولة بأسطر فارغة لمنع التصاق النصوص
        formatted = [f"* {s}" for s in selected]
        return "\n\n".join(formatted)
    
    async def analyze_result(self, result: SearchResult, idf_dict: Optional[Dict[str, float]] = None, use_llm_summary: bool = True) -> Dict[str, Any]:
        """تحليل شامل لنتيجة بحث واحدة"""
        analysis = {
            'url': result.url,
            'title': result.title,
            'basic_info': {
                'source': result.source,
                'relevance': result.relevance_score,
                'content_length': len(result.content or ''),
            }
        }
        
        content = result.content or result.snippet or ""
        if content and len(content) > 30:
            content = content[:50000]  # حد أقصى للتحليل
            
            # استخراج الكلمات المفتاحية باستخدام TF-IDF الحقيقي إذا توفر IDF
            analysis['keywords'] = self.extract_keywords_tfidf(content, 20, idf_dict=idf_dict)
            
            # استخراج الكيانات
            if config.enable_entity_extraction:
                analysis['entities'] = self.extract_entities(content)
            
            # تحليل المشاعر
            if config.enable_sentiment_analysis:
                analysis['sentiment'] = self.analyze_sentiment(content)
            
            # تلخيص
            if config.enable_summarization:
                if use_llm_summary:
                    summary = await self.summarize_text(content, query=result.metadata.get('subquery', '') or result.title, is_synthesis=False)
                else:
                    # تلخيص بالاستخراج محلياً ومجانياً لتسريع العملية ومنع أخطاء الـ 429
                    summary = self._extractive_summary(content, max_length=300)
                if summary:
                    analysis['summary'] = summary
        
        return analysis
    
    async def analyze_results_batch(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """تحليل مجموعة من النتائج بشكل متوازي مع ترشيد استخدام الـ LLM لتفادي الـ 429"""
        # تهيئة AI أولاً
        if config.use_ai_analysis:
            await self.initialize()
            
        # 1. بناء IDF Dictionary لكامل النتائج (Corpus)
        all_texts = []
        for r in results[:20]:
            content = r.content or r.snippet or ""
            text = re.sub(r'[^\w\s]', ' ', content.lower())
            all_texts.append(set(text.split()))
            
        import math
        N = len(all_texts)
        idf_dict = {}
        if N > 0:
            # حساب تردد كل كلمة في المستندات
            word_doc_count = Counter()
            for text_set in all_texts:
                word_doc_count.update(text_set)
                
            for word, count in word_doc_count.items():
                idf_dict[word] = math.log(N / (1 + count))
        
        # تحليل كل نتيجة بشكل متوازي لتسريع العملية
        tasks = []
        # نقوم بتلخيص أفضل 8 مصادر فقط باستخدام الـ LLM (DeepSeek) وتلخيص الباقي محلياً لتوفير الكاش وتفادي الـ 429
        for idx, result in enumerate(results[:20]):
            use_llm_summary = (idx < 8) and config.enable_summarization
            tasks.append(self.analyze_result(result, idf_dict=idf_dict, use_llm_summary=use_llm_summary))
        
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analyses = []
        for idx, res in enumerate(raw_results):
            if isinstance(res, Exception):
                analyses.append({'url': results[idx].url, 'error': f'Analysis failed: {str(res)}'})
            else:
                analyses.append(res)
        
        return analyses
    
    async def generate_aggregated_report(self, results: List[SearchResult], 
                                   analyses: List[Dict[str, Any]], 
                                   query: str,
                                   model: str = "fathom_s1",
                                   k_trusted: bool = False) -> Dict[str, Any]:
        """توليد تقرير شامل ومجمع عن نتائج البحث"""
        
        # تجميع كل المحتوى
        max_report_sources = 100 if model == "fathom_max" else 30
        all_content = ' '.join([
            r.content or r.snippet for r in results[:max_report_sources] if r.content or r.snippet
        ])
        
        # استخراج الكلمات المفتاحية الموحدة
        all_keywords = []
        all_entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'urls': [],
            'emails': [],
        }
        
        for analysis in analyses:
            if 'keywords' in analysis:
                all_keywords.extend(analysis['keywords'])
            if 'entities' in analysis:
                for category in all_entities:
                    all_entities[category].extend(
                        analysis['entities'].get(category, [])
                    )
        
        # إزالة التكرارات
        unique_keywords = list(dict.fromkeys(all_keywords))[:50]
        
        # حساب إحصائيات الكلمات المفتاحية الفريدة وتفاصيلها السياقية والتوزيع
        from urllib.parse import urlparse
        rich_keywords = []
        
        # تنظيف كل الكلمات من المحتوى لحساب الكثافة والتردد العام
        content_words = re.sub(r'[^\w\s]', ' ', all_content.lower()).split()
        total_words_len = len(content_words) if content_words else 1
        global_word_counts = Counter(content_words)
        
        for kw in unique_keywords[:35]: # نركز على أول 35 كلمة مفتاحية لتفادي إبطاء المعالجة
            kw_lower = kw.lower()
            kw_freq = global_word_counts.get(kw_lower, 0)
            if kw_freq == 0:
                kw_freq = all_content.lower().count(kw_lower)
            
            sites_list = []
            contexts_list = []
            sites_count = 0
            
            for res in results:
                res_content = (res.content or res.snippet or '').lower()
                if kw_lower in res_content:
                    sites_count += 1
                    res_words = re.sub(r'[^\w\s]', ' ', res_content).split()
                    res_freq = res_words.count(kw_lower)
                    if res_freq == 0:
                        res_freq = res_content.count(kw_lower)
                    
                    domain = urlparse(res.url).netloc or res.source
                    sites_list.append({
                        'site': domain,
                        'url': res.url,
                        'count': res_freq
                    })
                    
                    if len(contexts_list) < 5:
                        sentences = re.split(r'[.!?؟\n]', res.content or res.snippet or '')
                        for sentence in sentences:
                            sentence_clean = sentence.strip()
                            # فلترة مراجع ويكيبيديا والسطور غير المفهومة من السياقات النصية
                            if kw_lower in sentence_clean.lower():
                                s_low = sentence_clean.lower()
                                if any(marker in s_low for marker in ['lccn', 'oclc', 'qid', 'isbn', 'doi', '↑', 'cite', 'ref']):
                                    continue
                                letters_count = sum(1 for c in sentence_clean if c.isalpha())
                                if len(sentence_clean) > 0 and letters_count < len(sentence_clean) * 0.4:
                                    continue
                                
                                if len(sentence_clean) > len(kw) + 10:
                                    if len(sentence_clean) > 150:
                                        sentence_clean = sentence_clean[:147] + "..."
                                    if sentence_clean not in contexts_list:
                                        contexts_list.append(sentence_clean)
                                        if len(contexts_list) >= 5:
                                            break
            
            sites_list.sort(key=lambda x: x['count'], reverse=True)
            density = (kw_freq / total_words_len) * 100
            
            rich_keywords.append({
                'word': kw,
                'frequency': kw_freq,
                'sites_count': sites_count,
                'density': f"{density:.3f}%" if density > 0 else "0.01%",
                'distribution': sites_list[:8],
                'contexts': contexts_list[:5]
            })
            
        for category in all_entities:
            all_entities[category] = list(dict.fromkeys(all_entities[category]))[:10]
        
        # حساب الإحصائيات
        total_words = sum(r.metadata.get('word_count', 0) for r in results if r.content)
        total_results = len(results)
        sources = {}
        for r in results:
            sources[r.source] = sources.get(r.source, 0) + 1
        
        # إنشاء التقرير
        report = {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'total_results': total_results,
                'total_words_analyzed': total_words,
                'sources_used': sources,
                'engines_count': len(sources),
                'average_relevance': sum(r.relevance_score for r in results) / max(len(results), 1),
            },
            'keywords': rich_keywords,
            'entities': all_entities,
            'sentiment_overview': self._aggregate_sentiment(analyses),
            'top_results': [
                {
                    'title': r.title,
                    'url': r.url,
                    'source': r.source,
                    'relevance': r.relevance_score,
                    'summary': a.get('summary', r.snippet[:200]),
                }
                for r, a in zip(results[:10], analyses[:10])
            ],
        }
        
        # تهيئة قيم افتراضية لمنع فقدان المفاتيح في العرض
        report['overall_summary'] = 'لا يوجد محتوى كافٍ للتلخيص.'
        report['summary'] = 'لا يوجد محتوى كافٍ للتلخيص.'
        report['executive_summary'] = 'لا يوجد محتوى كافٍ للتلخيص.'
        report['deep_analysis'] = 'لا يوجد محتوى كافٍ للتحليل.'
        report['fuckenbase_analysis'] = 'لا يوجد محتوى كافٍ للتحليل.'
        
        # إضافة تلخيص شامل والتحليل المعرفي العميق
        if all_content:
            content_limit = 25000 if model == "fathom_max" else 15000
            try:
                summary = await self.summarize_text(all_content[:content_limit], 500, 100, query=query, is_synthesis=True)
                report['overall_summary'] = summary
                report['summary'] = summary
                report['executive_summary'] = summary
            except Exception:
                summary = self._extractive_summary(all_content[:content_limit], 500)
                report['overall_summary'] = summary
                report['summary'] = summary
                report['executive_summary'] = summary

            # إضافة تحليل عميق (ROOTBASE / Deep Analysis)
            if config.use_ai_analysis:
                try:
                    if k_trusted:
                        deep_prompt = f"""You are the K-Trusted Super-Verification AI Layer — an elite truth auditor, cognitive synthesizer, and data engineer.
Your task is to analyze the gathered search results for the query "{query}" and generate a world-class, 100% verified intelligence report in Arabic.
You are running under K-Trusted Mode. You must enforce these strict verification invariants:

1. Consensus Check: Cross-reference facts and numbers across a minimum of 5 independent authorized sources.
2. Contradiction Resolution & Table: 
   - You must construct a text-based ASCII/Markdown table comparing key claims, statistics, or facts.
   - The table must have these exact columns: [الادعاء / الحقيقة | المصادر والروابط | مستوى الموثوقية | حالة التوافق (إجماع / تعارض) | القيمة أو الحقيقة المؤكدة].
   - If a numerical metric or assertion lacks a clear cross-source consensus, you must EITHER:
     a) Omit the unverified claim entirely from the report.
     b) Clearly present the discrepancy in this table rather than stating a single unverified fact.
3. Absolute Dimensional & Translation Safeguards:
   - Prevent physical anomalies (e.g. human height 187 meters). Any out-of-boundary values must be auto-calibrated to correct units (e.g. 1.87 meters or 187 cm).
   - Eliminate homograph translation bugs: Units like "Inch/Inches" must translate strictly to "بوصة / بوصات" in Arabic, and NEVER to financial terms like "بورصة".
4. Layout Structure (Strictly in Arabic):
   - # التقرير المعرفي الفائق الموثق (K-Trusted Intelligence Report)
   - ## مصفوفة التحقق من صحة البيانات ومقارنة المصادر (Fact-Checking & Contradiction Matrix)
     - [Show the Markdown Table here]
     - Detail the consensus status of key claims.
   - ## التحليل والتقصي المعرفي الموثق 100% (Authoritative Truth Synthesis)
     - Comprehensive multi-paragraph analysis in Arabic containing only facts with verified cross-source consensus.
   - ## الخلاصة والتوصيات الاستراتيجية المؤكدة (Verified Recommendations)
     - Use > [!TIP] to outline action-oriented conclusions.

Do NOT include any generic placeholders.

Gathered search data:
{all_content[:25000]}"""
                    elif model == "fathom_max":
                        deep_prompt = f"""You are the Fathom Max Ultimate Intelligence Engine — an elite cognitive synthesizer, data engineer, and truth verification analyst.
Your task is to analyze the gathered search results for the query "{query}" and generate a world-class, radically detailed intelligence report in Arabic.
You are a partner in designing this report's layout and TXT presentation format. You must dynamically adapt the report's design and structure based on the query domain (e.g., scientific research, code/architecture audits, financial analysis, or history).

Design requirements for Fathom Max:
1. Dynamic Report Structure: Design a layout that fits the query type. Ensure it feels highly professional, analytical, and rigorous.
2. Fact-Checking & Contradiction Resolution Matrix (جدول التحقق من البيانات والمصداقية):
   - You must design a text-based ASCII/Markdown table comparing key claims or stats extracted from different sources.
   - The table must list: the fact/claim, the source domain/URL, the authority level (Tier 1/2/3), the consensus status (Agree/Disagree/Contradiction), and the resolved/verified truth.
3. Detailed Sections in Arabic:
   - # [Dynamic Title Tailored to the Query Domain]
   - ## جدول التحقق من صحة البيانات ومصفوفة المصداقية (Data Validation & Authority Matrix)
     - [Show the Markdown/ASCII Table here]
     - Detail how numerical or factual contradictions between sources were resolved.
   - ## التحليل المعرفي والتحليل الشامل للموضوع (Comprehensive Cognitive Deep Analysis)
     - Multi-paragraph, extremely detailed and authoritative analysis of the data.
   - ## سلسلة التفكير المتبعة والحل الدلالي للتعارضات (Semantic Conflict Resolution & Reasoning Chain)
     - Explain your exact logic and step-by-step reasoning for validating the facts before writing.
   - ## الخلاصة الاستشرافية والتوصيات الاستراتيجية (Forward-Looking Summary & Strategic Recommendations)
     - Use > [!TIP] to outline action-oriented conclusions and recommendations.

Do NOT output any of the instruction placeholders or generic templates. Customize the content, tables, and design completely for this search.

Gathered search data:
{all_content[:25000]}"""
                    else:
                        deep_prompt = f"""You are an elite research director and intelligence analyst.
Perform a world-class deep cognitive analysis (ROOTBASE Analysis) for the query "{query}" based on the following search data.
You must construct an extremely rigorous, analytical, and highly structured report in Arabic. Do NOT output any of the instruction placeholders in brackets or asterisks verbatim; replace them entirely with your custom analytical paragraphs.

Strictly format the output using this template:

# التحليل المعرفي المتقدم لشبكة العلاقات (Deep Cognitive Report)

## الفرضية الأساسية والتوجهات العامة (Core Hypothesis & Trends)
Write your deep critical analysis of the core hypothesis and current trends here in detailed paragraphs in Arabic.

## مقارنة المصادر وتقييم المصداقية (Source Consensus & Contradiction)
* **نقاط الاتفاق المشتركة**: Write the consensus points between different sources here in clear points in Arabic.
* **نقاط التعارض والاختلاف**: Detail any differences, conflicts, or variations between sources here in Arabic.
* **تقييم موثوقية المعلومات**: Analyze the credibility, reliability, and bias of the sources here in Arabic.

## شبكة الترابط والعلاقات المعرفية (Cognitive Entity Linkage)
* **الكيانات الفاعلة**: Mention the key entities (people, organizations, concepts) and their influence here in Arabic.
* **العلاقات المتبادلة**: Explain how these entities connect and interact within this context here in Arabic.

## الخلاصة الاستشرافية والتوصيات (Forward-Looking Summary & Recommendations)
> [!TIP]
> Write action-oriented conclusions and future forecasts for this topic here in detailed paragraphs in Arabic.

---
Ensure professional markdown formatting, using empty lines between paragraphs to avoid text overlapping.

المحتوى المجمع:
{all_content[:15000]}"""
                    deep_analysis_text = await self._call_llm(deep_prompt)
                    if deep_analysis_text:
                        report['deep_analysis'] = deep_analysis_text
                        report['fuckenbase_analysis'] = deep_analysis_text
                except Exception as e:
                    print(f"[!] فشل إنشاء التحليل العميق بواسطة الـ AI: {e}")

            if 'deep_analysis' not in report or not report['deep_analysis'] or report['deep_analysis'] == 'لا يوجد محتوى كافٍ للتحليل.':
                fallback_deep = "### التحليل التقليدي للمصادر\n\n" + "\n\n".join([
                    f"**[{i+1}] {r.title}** (الدرجة: {r.relevance_score})\n\n{r.snippet}" for i, r in enumerate(results[:5])
                ])
                report['deep_analysis'] = fallback_deep
                report['fuckenbase_analysis'] = fallback_deep
        
        # ─── الإجابة المرجعية المباشرة (RootSearch AI Direct Answer) ───
        report['direct_answer'] = {'answer': '', 'sources': [], 'verified': k_trusted, 'confidence': 0.0}
        if results:
            try:
                direct = await self.generate_direct_answer(
                    query=query,
                    top_results=results[:8],
                    all_content=all_content[:8000],
                    k_trusted=k_trusted,
                )
                report['direct_answer'] = direct
            except Exception as e:
                print(f"[!] فشل إنشاء الإجابة المباشرة: {e}")
        
        return report

    
    def _aggregate_sentiment(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """تجميع تحليل المشاعر عبر جميع النتائج"""
        sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
        total_score = 0
        count = 0
        
        # مجاميع المشاعر والعواطف المتقدمة
        total_subjectivity = 0.0
        total_objectivity = 0.0
        emotions_sums = {'trust': 0, 'anger': 0, 'fear': 0, 'joy': 0, 'sadness': 0}
        
        for analysis in analyses:
            if 'sentiment' in analysis:
                sent = analysis['sentiment']
                if isinstance(sent, dict):
                    sentiments[sent.get('sentiment', 'neutral')] += 1
                    total_score += sent.get('score', 0)
                    total_subjectivity += sent.get('subjectivity', 0.3)
                    total_objectivity += sent.get('objectivity', 0.7)
                    
                    # تجميع العواطف
                    em_dict = sent.get('emotions', {})
                    for em in emotions_sums:
                        emotions_sums[em] += em_dict.get(em, 0)
                        
                    count += 1
        
        avg_score = total_score / max(count, 1)
        avg_subjectivity = total_subjectivity / max(count, 1)
        avg_objectivity = total_objectivity / max(count, 1)
        
        # حساب التوزيع النسبي للعواطف
        total_emotions = sum(emotions_sums.values())
        emotions_dist = {}
        if total_emotions > 0:
            for em, val in emotions_sums.items():
                emotions_dist[em] = round(val / total_emotions, 2)
        else:
            # توزيع افتراضي متوازن
            emotions_dist = {'trust': 0.4, 'anger': 0.1, 'fear': 0.1, 'joy': 0.2, 'sadness': 0.2}
        
        # تحديد المشاعر العامة
        if sentiments['positive'] > sentiments['negative'] and sentiments['positive'] > sentiments['neutral']:
            overall = 'إيجابي'
        elif sentiments['negative'] > sentiments['positive'] and sentiments['negative'] > sentiments['neutral']:
            overall = 'سلبي'
        else:
            overall = 'محايد'
        
        return {
            'overall': overall,
            'score': round(avg_score, 2),
            'distribution': sentiments,
            'subjectivity': round(avg_subjectivity, 2),
            'objectivity': round(avg_objectivity, 2),
            'emotions': emotions_dist
        }
        
    async def explain_keyword(self, query: str, keyword: str, results: List[Dict[str, Any]]) -> str:
        """تقديم توضيح بسيط ومختصر للكلمة المفتاحية في سياق الاستعلام"""
        # محاولة استخدام الـ AI
        if config.use_ai_analysis:
            try:
                if not self.nlp_initialized:
                    await self.initialize()
                prompt = f"""قم بتقديم تعريف سياقي فائق الوضوح والجودة للكلمة أو المفهوم "{keyword}" في سياق موضوع البحث "{query}".
اكتب جملة واحدة بليغة ومباشرة (لا تزيد عن 20 كلمة) تلخص ماهية هذا المفهوم باللغة العربية الفصحى. لا تستخدم أي مقدمات أو هوامش، اكتب التعريف مباشرة."""
                explanation = await self._call_llm(prompt)
                if explanation:
                    return explanation
            except Exception as e:
                print(f"[⚠️] فشل تفسير الكلمة بواسطة نموذج الـ AI: {e}")
                
        # Fallback: استخلاص سياق توضيحي محلي من النصوص الممسوحة
        explanation = ""
        keyword_lower = keyword.lower()
        for res in results:
            content = (res.get('content') or '') + ' ' + (res.get('snippet') or '')
            # البحث عن جمل تحتوي الكلمة وتصلح كتعريف
            sentences = re.split(r'[.!?؟\n]', content)
            for sentence in sentences:
                sentence_clean = sentence.strip()
                if keyword_lower in sentence_clean.lower():
                    # التحقق من أن الجملة لا تحتوي على مراجع مشوهة أو أرقام كثيرة (مثل LCCN, OCLC, OL, QID, ↑)
                    s_low = sentence_clean.lower()
                    if any(marker in s_low for marker in ['lccn', 'oclc', 'qid', 'isbn', 'doi', '↑', 'cite', 'ref', 'dspace', 'pmid']):
                        continue
                    # التأكد من أن نسبة الحروف الأبجدية كافية (لتجنب سطور الأرقام والرموز)
                    letters_count = sum(1 for c in sentence_clean if c.isalpha())
                    if len(sentence_clean) > 0 and letters_count < len(sentence_clean) * 0.4:
                        continue
                    
                    if len(sentence_clean) > len(keyword) + 10 and len(sentence_clean) < 300:
                        # نفضل الجمل التي تحتوي على أدوات تعريف أو روابط مثل "هو"، "هي"، "عبارة عن"، "is", "was"
                        indicators = [" هو ", " هي ", " عبارة عن ", " يعتبر ", " تعتبر ", " is ", " was ", " definition ", " يعني "]
                        if any(ind in sentence_clean.lower() for ind in indicators):
                            return sentence_clean[:150] + "..."
                        # كاحتياطي أول جملة مناسبة
                        if not explanation:
                            explanation = sentence_clean[:150] + "..."
                        
        if explanation:
            return explanation
        return f"مفهوم مرتبط بموضوع البحث: {query}."

    async def expand_query(self, query: str, model: str = "fathom_s1") -> List[str]:
        """توسيع الاستعلام إلى 3 (S1) أو 5 (Max) استعلامات فرعية أكثر تخصصاً وتفرعاً"""
        await self.initialize()
        num_subqueries = 5 if model == "fathom_max" else 3
        # استنتاج النية لحقن قيد النطاق في المطالبة (تقليل التشعّب).
        try:
            from core.intent import classify_query
            intent_category = classify_query(query).category
        except Exception:
            intent_category = "general"
        try:
            prompt = (
                f"You are part of a deep search engine called RootSearch. "
                f"Given the user search query: '{query}', generate exactly {num_subqueries} distinct, highly targeted, "
                f"and relevant sub-queries or search terms to explore different angles of the query "
                f"for a comprehensive search. "
                f"STRICT RULES:\n"
                f"1. Focus strictly on resolving the user's precise query and intent. Do NOT generate broad, generic, or unrelated subqueries.\n"
                f"2. Do NOT branch out into general biography, net worth, career, or unrelated aspects. All subqueries must be laser-focused on the exact subject of the query.\n"
                f"3. Stay strictly within the query domain/intent: '{intent_category}'. Do NOT drift into other domains.\n"
                f"4. Return ONLY a JSON list of strings, with no explanation and no markdown block.\n"
                f"Example: [\"term 1\", \"term 2\", \"term 3\"]"
            )
            text = await self._call_llm(prompt)
            if text:
                text = text.strip()
                # Clean code blocks if LLM ignored instructions
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n|\n```$", "", text, flags=re.MULTILINE).strip()
                
                # Robust extraction of JSON array
                match = re.search(r'\[\s*".*?"\s*(?:,\s*".*?"\s*)*\]', text, re.DOTALL)
                if match:
                    json_str = match.group(0)
                else:
                    json_str = text
                
                try:
                    subqueries = json.loads(json_str)
                except Exception:
                    subqueries = re.findall(r'"([^"]+)"', json_str)
                
                if isinstance(subqueries, list) and len(subqueries) > 0:
                    return [str(q).strip() for q in subqueries[:num_subqueries]]
        except Exception as e:
            print(f"[⚠️] Failed to expand query using AI model: {e}")
        
        # Fallback: heuristics based on query language
        words = [w for w in re.findall(r"\w+", query) if len(w) > 2]
        if not words:
            return []
            
        # Check if Arabic
        is_arabic = bool(re.search(r"[\u0600-\u06FF]", query))
        
        # Check if physical attributes are present
        query_lower = query.lower()
        physical_keywords = ["height", "tall", "stature", "طول", "قامة", "weight", "وزن"]
        
        if any(pk in query_lower for pk in physical_keywords):
            if is_arabic:
                exts = ["بالسنتمتر", "إحصائيات رسمية", "الوزن الحقيقي", "الارتفاع الفعلي", "مقارنة قياسات"] if model == "fathom_max" else ["بالسنتمتر", "إحصائيات رسمية", "الوزن الحقيقي"]
            else:
                exts = ["in cm", "official stats", "exact weight", "height measurement", "official profile"] if model == "fathom_max" else ["in cm", "official stats", "exact weight"]
            return [f"{query} {ext}" for ext in exts[:num_subqueries]]

        # Fallback متحفّظ: عند فشل الـLLM لا نولّد لواحق عامة توسّع النية؛
        # الاستعلام الأصلي مضمون دائماً في مسار البحث، فإرجاع قائمة فارغة أسلم من التشتيت.
        return []

