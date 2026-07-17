"""
Fucken Search - Configuration Module v2.0
الإعدادات العامة لمحرك البحث الخارق — 22+ مصدر مجاني
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SearchConfig:
    """إعدادات البحث المتقدمة"""

    # عدد النتائج من كل محرك بحث
    results_per_engine: int = 40

    # أقصى عمق للبحث
    max_scrape_depth: int = 3

    # المهلة الزمنية للطلبات بالثواني
    request_timeout: int = 30

    # أقصى عدد من الصفحات المتزامنة
    max_concurrent_requests: int = 50

    # حدود Fathom المحسنة
    fathom_s1_max_sources: int = 35
    fathom_max_nodes: int = 150
    fathom_max_depth: int = 4
    fathom_max_concurrency: int = 12

    # وكلاء المستخدمين للتخفي (تستخدم fake-useragent عند توفرها)
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ])

    # ─── محركات البحث المفعّلة ───────────────────────────────────────
    # مجموعة 1: محركات بحث عامة (web scraping)
    # مجموعة 2: APIs علمية مجانية 100%
    # مجموعة 3: مجتمعات ومنتديات
    # مجموعة 4: كتب وأرشيف
    search_engines: List[str] = field(default_factory=lambda: [
        # ── محركات بحث عامة ──────────────────────────────
        "duckduckgo",       # DuckDuckGo — HTML scraping محسّن
        "startpage",        # Startpage — Google proxy بدون CAPTCHA ✅ جديد
        "bing",             # Bing — محدّث selectors
        "brave",            # Brave — محدّث selectors
        "mojeek",           # Mojeek — محرك مستقل بدون Google ✅ جديد
        "qwant",            # Qwant — محرك أوروبي JSON API ✅ جديد
        "ecosia",           # Ecosia — محرك بيئي ✅ جديد
        "searx",            # SearXNG — meta-search موزع
        # ── موسوعات وبيانات هيكلية ────────────────────────
        "wikipedia",        # Wikipedia — عربي + إنجليزي (يعمل ✅)
        "wikidata",         # Wikidata — knowledge graph ✅ جديد
        # ── أبحاث علمية (APIs مجانية 100%) ───────────────
        "arxiv",            # arXiv — preprints علمية ✅ جديد
        "openalex",         # OpenAlex — 250M ورقة بحثية ✅ جديد
        "semantic_scholar", # Semantic Scholar — AI search ✅ جديد
        "pubmed",           # PubMed — أبحاث طبية ✅ جديد
        "crossref",         # CrossRef — 100M+ DOIs ✅ جديد
        "core",             # CORE — open access papers ✅ جديد
        # ── مجتمعات تقنية ─────────────────────────────────
        "stackexchange",    # Stack Exchange — SO + 170 موقع ✅ جديد
        "reddit",           # Reddit — JSON endpoint بدون key ✅ جديد
        "hackernews",       # Hacker News — Algolia API ✅ جديد
        # ── كتب وأرشيف ────────────────────────────────────
        "openlibrary",      # Open Library — ملايين الكتب ✅ جديد
        "internet_archive", # Internet Archive — أرشيف رقمي ✅ جديد
        # ── AI-powered ────────────────────────────────────
        "jina",             # Jina Search — AI-optimized ✅ محسّن
    ])

    # ── إعدادات الذكاء الاصطناعي ─────────────────────────────────────
    use_ai_analysis: bool = True
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek"))
    glm_api_url: Optional[str] = field(default_factory=lambda: os.getenv("GLM_API_URL", ""))
    glm_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GLM_API_KEY", ""))
    # ── DeepSeek (OpenAI-compatible API) ──
    deepseek_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_api_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com"))
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))

    enable_entity_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_summarization: bool = True

    # ── كاش SearXNG ───────────────────────────────────────────────────
    searx_cache_file: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "searx_instances.json"
    )
    searx_cache_ttl: int = 86400  # 24 ساعة

    # ── النتائج ───────────────────────────────────────────────────────
    max_final_results: int = 100   # زيادة من 50 → 100 مع 22 مصدر
    min_relevance_score: float = 0.1

    # ── الخادم ────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", 7860)))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "False").lower() in ("true", "1", "t"))


@dataclass
class ProxyConfig:
    """إعدادات البروكسي (اختياري)"""
    enabled: bool = False
    proxies: List[str] = field(default_factory=list)
    rotate: bool = True


# الإعدادات العامة
config = SearchConfig()
proxy_config = ProxyConfig()
