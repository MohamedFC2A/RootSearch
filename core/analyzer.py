"""
Fucken Search - AI Analysis Module
محلل الذكاء الاصطناعي الخارق: يحلل، يلخص، ويستخرج المعلومات
"""

import asyncio
import re
import json
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from config import config
from core.search_engine import SearchResult


class AIAnalyzer:
    """محلل الذكاء الاصطناعي - يعالج النصوص ويفهمها"""
    
    def __init__(self):
        self.gemini_model = None
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
                # تهيئة Gemini دائماً إذا كان المفتاح متوفراً ليكون كخيار احتياطي (Fallback)
                if config.gemini_api_key:
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=config.gemini_api_key)
                        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                        print("[✨] تم تهيئة Google Gemini API بنجاح كخيار احتياطي/أساسي")
                    except Exception as ge:
                        print(f"[⚠️] تعذر تهيئة Gemini API: {ge}")

                if config.llm_provider == "glm_colab":
                    if config.glm_api_url:
                        print(f"[✨] تم ربط خادم البحث بنموذج GLM المستضاف على Colab: {config.glm_api_url}")
                    else:
                        print("[⚠️] تم اختيار GLM Colab ولكن رابط GLM_API_URL غير متوفر في الإعدادات.")
                
                self.nlp_initialized = True
                    
            except Exception as e:
                print(f"[⚠️] تعذر تهيئة مزود الـ AI: {e}")
                print("[ℹ️] سيتم استخدام التحليل التقليدي عند الحاجة")
                self.nlp_initialized = True

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """استدعاء نموذج اللغة المختار (GLM Colab أو Gemini) مع الرجوع التلقائي عند الفشل"""
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
                
                import aiohttp
                async with aiohttp.ClientSession() as session:
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
            
            print("[ℹ/⚠️] محاولة الرجوع التلقائي إلى Google Gemini API...")

        # 2. استخدام Google Gemini API كخيار أساسي أو كاحتياطي عند فشل Colab
        if self.gemini_model:
            try:
                response = await self.gemini_model.generate_content_async(prompt)
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[⚠️] فشل الاتصال بـ Gemini API: {e}")
        
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
    
    async def summarize_text(self, text: str, max_length: int = 300, min_length: int = 50) -> str:
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
                
                prompt = f"""You are a master cognitive synthesizer for the RootSearch deep intelligence search engine.
Your task is to analyze the gathered search results for the query "{query}" and generate a highly organized, world-class synthesis report in modern Arabic.

Strictly organize the report using the following structure:

# 📊 التلخيص المعرفي والتحليل الشامل للموضوع: {query}

## 🔍 النظرة العامة والتحليل التنفيذي (Executive Summary)
> [!NOTE]
> *اكتب فقرة مقتضبة، مركزة، وعالية القيمة تلخص صلب الموضوع وأهميته.*

## 💡 النقاط الرئيسية والحقائق المثبتة (Key Core Insights)
* **[نقطة رئيسية 1]**: تفصيل مختصر ومباشر مدعوم بالبيانات.
* **[نقطة رئيسية 2]**: تفصيل مختصر ومباشر مدعوم بالبيانات.
* **[نقطة رئيسية 3]**: تفصيل مختصر ومباشر مدعوم بالبيانات.

## 🧭 السياق الدلالي والأبعاد المحيطة (Contextual Dimensions)
*اكتب تحليلاً للمحاور الجانبية المرتبطة بالاستعلام وكيف تتقاطع مع الموضوع الأساسي.*

---
*تأكد من استخدام تنسيق Markdown بشكل احترافي، وترك سطر فارغ بين كل فقرة أو عنصر لتفادي التصاق النصوص.*

المحتوى المجمع من المصادر:
{text}"""
                
                summary = await self._call_llm(prompt)
                if summary:
                    return summary
            except Exception as e:
                print(f"[⚠️] فشل التلخيص بواسطة نموذج الـ AI: {e}")
        
        # Fallback: تلخيص بالاستخراج
        
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
    
    async def analyze_result(self, result: SearchResult, idf_dict: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
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
        
        if result.content and len(result.content) > 50:
            content = result.content[:50000]  # حد أقصى للتحليل
            
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
                summary = await self.summarize_text(content)
                if summary:
                    analysis['summary'] = summary
        
        return analysis
    
    async def analyze_results_batch(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """تحليل مجموعة من النتائج بشكل متوازي"""
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
        
        # تحليل كل نتيجة
        analyses = []
        for result in results[:20]:  # أقصى 20 نتيجة للتحليل
            try:
                analysis = await self.analyze_result(result, idf_dict=idf_dict)
                analyses.append(analysis)
            except Exception:
                analyses.append({'url': result.url, 'error': 'Analysis failed'})
        
        return analyses
    
    async def generate_aggregated_report(self, results: List[SearchResult], 
                                   analyses: List[Dict[str, Any]], 
                                   query: str) -> Dict[str, Any]:
        """توليد تقرير شامل ومجمع عن نتائج البحث"""
        
        # تجميع كل المحتوى
        all_content = ' '.join([
            r.content or r.snippet for r in results[:30] if r.content or r.snippet
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
            try:
                summary = await self.summarize_text(all_content[:15000], 500, 100)
                report['overall_summary'] = summary
                report['summary'] = summary
                report['executive_summary'] = summary
            except Exception:
                summary = self._extractive_summary(all_content[:15000], 500)
                report['overall_summary'] = summary
                report['summary'] = summary
                report['executive_summary'] = summary

            # إضافة تحليل عميق (ROOTBASE / Deep Analysis)
            if config.use_ai_analysis:
                try:
                    deep_prompt = f"""You are an elite research director and intelligence analyst.
Perform a world-class deep cognitive analysis (ROOTBASE Analysis) for the query "{query}" based on the following search data.
You must construct an extremely rigorous, analytical, and highly structured report in Arabic.

Strictly format the output using this template:

# 🧠 التحليل المعرفي المتقدم لشبكة العلاقات (Deep Cognitive Report)

## 📌 الفرضية الأساسية والتوجهات العامة (Core Hypothesis & Trends)
*اكتب تحليلاً نقدياً للفرضية الأساسية للموضوع وتوجهاته الحالية.*

## ⚖️ مقارنة المصادر وتقييم المصداقية (Source Consensus & Contradiction)
* **نقاط الاتفاق المشتركة**: [اكتب نقاط التوافق بين المصادر المختلفة في نقاط واضحة].
* **نقاط التعارض والاختلاف**: [اكتب الاختلافات أو التناقضات بين المصادر بالتفصيل].
* **تقييم موثوقية المعلومات**: [تحليل مدى صدق وموثوقية المصادر المجمعة].

## ⛓️ شبكة الترابط والعلاقات المعرفية (Cognitive Entity Linkage)
* **الكيانات الفاعلة**: [الشخصيات، المؤسسات، أو المفاهيم الأساسية وتأثيرها].
* **العلاقات المتبادلة**: [كيف تترابط الكيانات ببعضها البعض ضمن هذا السياق].

## 🎯 الخلاصة الاستشرافية والتوصيات (Forward-Looking Summary & Recommendations)
> [!TIP]
> *استنتاجات جوهرية عملية وتوقعات مستقبلية للموضوع.*

---
*تأكد من فصل الأقسام بوضوح باستخدام أسطر فارغة وعلامات Markdown المناسبة لمنع أي تداخل للنصوص.*

المحتوى المجمع:
{all_content[:15000]}"""
                    deep_analysis_text = await self._call_llm(deep_prompt)
                    if deep_analysis_text:
                        report['deep_analysis'] = deep_analysis_text
                        report['fuckenbase_analysis'] = deep_analysis_text
                except Exception as e:
                    print(f"[⚠️] فشل إنشاء التحليل العميق بواسطة الـ AI: {e}")

            if 'deep_analysis' not in report or not report['deep_analysis'] or report['deep_analysis'] == 'لا يوجد محتوى كافٍ للتحليل.':
                fallback_deep = "### التحليل التقليدي للمصادر\n\n" + "\n\n".join([
                    f"**[{i+1}] {r.title}** (الدرجة: {r.relevance_score})\n\n{r.snippet}" for i, r in enumerate(results[:5])
                ])
                report['deep_analysis'] = fallback_deep
                report['fuckenbase_analysis'] = fallback_deep
        
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

    async def expand_query(self, query: str) -> List[str]:
        """توسيع الاستعلام إلى 3 استعلامات فرعية أكثر تخصصاً وتفرعاً"""
        await self.initialize()
        try:
            prompt = (
                f"You are part of a deep search engine called RootSearch. "
                f"Given the user search query: '{query}', generate exactly 3 distinct, highly targeted, "
                f"and relevant sub-queries or search terms to explore different angles of the query "
                f"for a comprehensive search. "
                f"Return ONLY a JSON list of strings, with no explanation and no markdown block. "
                f"Example: [\"term 1\", \"term 2\", \"term 3\"]"
            )
            text = await self._call_llm(prompt)
            if text:
                text = text.strip()
                # Clean code blocks if LLM ignored instructions
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n|\n```$", "", text, flags=re.MULTILINE).strip()
                subqueries = json.loads(text)
                if isinstance(subqueries, list) and len(subqueries) > 0:
                    return [str(q).strip() for q in subqueries[:3]]
        except Exception as e:
            print(f"[⚠️] Failed to expand query using AI model: {e}")
        
        # Fallback: heuristics based on query language
        words = [w for w in re.findall(r"\w+", query) if len(w) > 2]
        if not words:
            return []
            
        # Check if Arabic
        is_arabic = bool(re.search(r"[\u0600-\u06FF]", query))
        if is_arabic:
            exts = ["تفاصيل وتحليل", "تطبيقات وأمثلة", "أحدث التطورات"]
            return [f"{query} {ext}" for ext in exts]
        else:
            exts = ["detailed analysis", "applications and examples", "latest developments"]
            return [f"{query} {ext}" for ext in exts]

