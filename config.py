"""
Fucken Search - Configuration Module
الإعدادات العامة لمحرك البحث الخارق
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()


@dataclass
class SearchConfig:
    """إعدادات البحث المتقدمة"""
    
    # عدد النتائج من كل محرك بحث
    results_per_engine: int = 25
    
    # أقصى عمق للبحث (عدد الصفحات التي يتم تحليلها لكل رابط)
    max_scrape_depth: int = 3
    
    # المهلة الزمنية للطلبات بالثواني
    request_timeout: int = 30
    
    # أقصى عدد من الصفحات المتزامنة
    max_concurrent_requests: int = 50
    
    # وكلاء المستخدمين للتخفي
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    ])
    
    # وكلاء البحث (بدون API keys)
    # ملاحظة: Google, Bing, Brave قد تحظر الطلبات المباشرة أحياناً
    # DuckDuckGo و SearX يعملان بشكل موثوق
    search_engines: List[str] = field(default_factory=lambda: [
        "duckduckgo",
        "searx",
        "wikipedia",
        "google",
        "bing",
        "brave",
    ])
    
    # إعدادات الذكاء الاصطناعي
    # يعتمد التحليل الشامل على Google Gemini API أو GLM المستضاف على Colab
    use_ai_analysis: bool = True
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    gemini_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    
    # إعدادات نموذج GLM (Google Colab)
    glm_api_url: Optional[str] = field(default_factory=lambda: os.getenv("GLM_API_URL", ""))
    glm_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GLM_API_KEY", ""))
    
    enable_entity_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_summarization: bool = True
    
    # إعدادات كاش SearXNG الديناميكي
    searx_cache_file: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "searx_instances.json")
    searx_cache_ttl: int = 86400  # 24 ساعة بالثواني
    
    # إعدادات النتائج
    max_final_results: int = 50
    min_relevance_score: float = 0.1
    
    # إعدادات الخادم
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 6969))
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")


@dataclass
class ProxyConfig:
    """إعدادات البروكسي (اختياري)"""
    enabled: bool = False
    proxies: List[str] = field(default_factory=list)
    rotate: bool = True


# الإعدادات العامة
config = SearchConfig()
proxy_config = ProxyConfig()
