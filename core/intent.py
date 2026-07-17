"""
Fucken Search - Query Intent Classifier
مُصنِّف نية الاستعلام: طبقة خفيفة قائمة على القواعد (< 1ms، بدون تبعيات خارجية)
تُوحّد اختيار المصادر عبر search_all و web/app.py وتمنع تلوث النتائج بمصادر
غير متعلقة (خصوصاً قواعد الأبحاث الأكاديمية للاستعلامات العامة).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────
#  ENGINE GROUPS  (أسماء المحركات كما في SearchEngine.search_all)
# ─────────────────────────────────────────────

# محركات عامة + موسوعات (تُستخدم لكل الاستعلامات تقريباً)
GENERAL_ENGINES: List[str] = [
    "duckduckgo", "startpage", "bing", "brave", "mojeek",
    "searx", "wikipedia", "wikidata",
]

# محركات أكاديمية/بحثية (تُشغَّل فقط عند نية بحثية)
ACADEMIC_ENGINES: List[str] = [
    "arxiv", "openalex", "semantic_scholar", "pubmed", "crossref",
    "core", "qwant", "ecosia", "jina", "reddit",
    "openlibrary", "internet_archive",
]

# محركات مجتمعات/كود
COMMUNITY_ENGINES: List[str] = ["stackexchange", "hackernews"]

# قاعدة أمان: تُضاف دائماً مهما كانت النية لضمان عدم انهيار التغطية
ALWAYS_ON_ENGINES: List[str] = ["duckduckgo", "startpage", "wikipedia"]


# ─────────────────────────────────────────────
#  KEYWORD SIGNALS
# ─────────────────────────────────────────────

_ACADEMIC_KEYWORDS = {
    # English
    "paper", "papers", "study", "studies", "research", "journal", "arxiv",
    "doi", "theorem", "dataset", "citation", "peer-reviewed", "preprint",
    "thesis", "dissertation", "publication", "scholar",
    # Arabic
    "بحث", "أبحاث", "دراسة", "دراسات", "ورقة", "نظرية", "مرجع",
    "استشهاد", "أطروحة", "منشور", "علمي",
}

_CODE_KEYWORDS = {
    # English
    "code", "python", "javascript", "java", "rust", "golang", "api",
    "library", "framework", "github", "npm", "pip", "compile", "function",
    "bug", "error", "exception", "stacktrace", "regex", "sql",
    # Arabic
    "كود", "برمجة", "دالة", "مكتبة", "خطأ", "استثناء",
}

_NEWS_KEYWORDS = {
    "news", "breaking", "headline", "report",
    "أخبار", "خبر", "عاجل", "تقرير",
}

_PHYSICAL_KEYWORDS = {
    "height", "tall", "stature", "weight", "dimensions", "size",
    "طول", "قامة", "وزن", "حجم", "أبعاد",
}

_TEMPORAL_KEYWORDS = {
    "latest", "recent", "newest", "current", "today", "now",
    "أحدث", "احدث", "جديد", "جديده", "جديدة", "أخبار", "الآن", "اليوم",
}

# كلمات إيقاف مبسّطة (إنجليزي + عربي) لاستخراج الكلمات الأساسية
_STOP_WORDS = {
    "the", "of", "and", "a", "to", "in", "is", "it", "was", "for", "on",
    "with", "at", "by", "an", "or", "as", "be", "that", "this", "who",
    "what", "how", "why", "when", "where",
    "من", "في", "على", "إلى", "عن", "مع", "هذا", "هذه", "أن", "هو", "هي",
    "ما", "هل", "كيف", "لماذا", "متى", "أين", "الذي", "التي",
}


def _normalize(text: str) -> str:
    """تطبيع عربي بسيط (يماثل aggregator._tokenize_and_normalize)."""
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    return text


def _tokenize(text: str) -> List[str]:
    """تفكيك مع إزالة الترقيم والتطبيع (نسخة مستقلة لتفادي الاستيراد الدائري)."""
    if not text:
        return []
    punc = ".,?!،؟:;()[]{}'\"-_/\\«»"
    for p in punc:
        text = text.replace(p, " ")
    text = _normalize(text)
    return text.lower().split()


@dataclass
class QueryIntent:
    """نتيجة تصنيف نية الاستعلام."""
    category: str = "general"          # general | academic | news | code | factual | physical
    is_temporal: bool = False
    query_years: List[int] = field(default_factory=list)
    core_terms: List[str] = field(default_factory=list)
    language: str = "en"               # ar | en | mixed
    suggested_engines: List[str] = field(default_factory=list)


def _detect_language(query: str) -> str:
    has_ar = bool(re.search(r"[\u0600-\u06FF]", query))
    has_en = bool(re.search(r"[A-Za-z]", query))
    if has_ar and has_en:
        return "mixed"
    if has_ar:
        return "ar"
    return "en"


def _dedupe_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def classify_query(query: str) -> QueryIntent:
    """
    تصنيف الاستعلام إلى نية واختيار مجموعة المحركات المناسبة.
    القاعدة الافتراضية: نية عامة (تُستبعد المصادر الأكاديمية) ما لم تظهر إشارات بحثية.
    """
    query = (query or "").strip()
    tokens = _tokenize(query)
    token_set = set(tokens)

    # الكلمات الأساسية (بعد إزالة كلمات الإيقاف)
    normalized_stop = {_normalize(w).lower() for w in _STOP_WORDS}
    core_terms = [t for t in tokens if len(t) > 1 and t not in normalized_stop]

    # كشف زمني + سنوات
    is_temporal = False
    query_years: List[int] = []
    for t in tokens:
        if t in _TEMPORAL_KEYWORDS:
            is_temporal = True
        if re.match(r"^(19\d\d|20\d\d)$", t):
            is_temporal = True
            query_years.append(int(t))

    language = _detect_language(query)

    # تحديد الفئة (بأولوية: أكاديمي > كود > فيزيائي > أخبار > عام)
    def _has(keywords) -> bool:
        return any(k in token_set for k in keywords) or any(k in query.lower() for k in keywords)

    if _has(_ACADEMIC_KEYWORDS):
        category = "academic"
    elif _has(_CODE_KEYWORDS):
        category = "code"
    elif _has(_PHYSICAL_KEYWORDS):
        category = "physical"
    elif is_temporal or _has(_NEWS_KEYWORDS):
        category = "news"
    else:
        category = "general"

    # خريطة الفئة → المحركات
    if category == "academic":
        engines = GENERAL_ENGINES + ACADEMIC_ENGINES + COMMUNITY_ENGINES
    elif category == "code":
        engines = ["duckduckgo", "startpage", "brave", "searx", "wikipedia"] + COMMUNITY_ENGINES
    elif category == "physical":
        engines = GENERAL_ENGINES + ["wikidata"]
    else:  # general | news | factual
        engines = list(GENERAL_ENGINES)
        if category == "news":
            engines = engines + ["hackernews"]

    # ضمان محركات الأمان دائماً
    engines = _dedupe_preserve(engines + ALWAYS_ON_ENGINES)

    return QueryIntent(
        category=category,
        is_temporal=is_temporal,
        query_years=query_years,
        core_terms=core_terms,
        language=language,
        suggested_engines=engines,
    )
