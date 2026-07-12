"""
Fucken Search - Search Engine Core Module
محرك البحث الخارق: قلب نظام البحث في أعماق الإنترنت
يدعم محركات متعددة بدون API Keys
"""

import asyncio
import random
import re
import urllib.parse
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import time
import socket
import ipaddress

import aiohttp
import aiohttp.abc
from bs4 import BeautifulSoup

from config import config


class SafeResolver(aiohttp.abc.AbstractResolver):
    """محلل أسماء نطاقات آمن يمنع SSRF و DNS Rebinding بشكل مطلق"""
    
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        except Exception as e:
            raise OSError(f"DNS resolution failed for {host}: {e}")
            
        safe_infos = []
        for info in infos:
            ip = info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip)
                # منع العناوين المحلية والخاصة والمحجوزة
                if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_multicast or ip_obj.is_reserved:
                    continue
                safe_infos.append(info)
            except ValueError:
                continue
                
        if not safe_infos:
            raise OSError(f"Access denied: Private or invalid IP addresses are blocked for {host}")
            
        return [{
            "hostname": host,
            "host": item[4][0],
            "port": item[4][1],
            "family": item[0],
            "proto": item[2],
            "flags": socket.AI_NUMERICHOST,
        } for item in safe_infos]

    async def close(self) -> None:
        pass


@dataclass
class SearchResult:
    """نتيجة بحث واحدة"""
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float = 1.0
    content: Optional[str] = None
    content_type: str = "web"
    language: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class SearchEngine:
    """محرك البحث الأساسي - يدعم محركات متعددة"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[SearchResult] = []
        self._user_agent_index = 0
    
    def _get_next_user_agent(self) -> str:
        """تغيير وكيل المستخدم بشكل دوري للتخفي"""
        ua = config.user_agents[self._user_agent_index]
        self._user_agent_index = (self._user_agent_index + 1) % len(config.user_agents)
        return ua
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """الحصول على جلسة HTTP مع إعادة استخدام"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.request_timeout)
            resolver = SafeResolver()
            connector = aiohttp.TCPConnector(resolver=resolver)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.session
    
    async def _make_request(self, url: str, headers: Optional[Dict] = None, 
                           params: Optional[Dict] = None, method: str = "GET") -> Optional[str]:
        """إجراء طلب HTTP مع إعادة المحاولة"""
        session = await self._get_session()
        
        if headers is None:
            headers = {
                "User-Agent": self._get_next_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5,ar;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        
        for attempt in range(3):  # 3 محاولات كحد أقصى
            try:
                async with session.request(method, url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Rate limited
                        wait = min(5 * (attempt + 1), 30)
                        await asyncio.sleep(wait)
                    elif response.status in [403, 404]:
                        return None
                    else:
                        await asyncio.sleep(1 * (attempt + 1))
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt == 2:
                    return None
                await asyncio.sleep(2 * (attempt + 1))
        
        return None
    
    async def search_duckduckgo(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث عبر DuckDuckGo (بدون API Key)"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                # استخدام واجهة DuckDuckGo HTML (بدون API)
                url = f"https://html.duckduckgo.com/html/"
                params = {
                    "q": query,
                    "s": "0",
                    "o": "json",
                    "api": "/d.js",
                }
                
                headers = {
                    "User-Agent": self._get_next_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": "https://duckduckgo.com/",
                }
                
                html = await self._make_request(url, headers=headers, params=params)
                if not html:
                    if retry < max_retries - 1:
                        await asyncio.sleep(2 ** retry)
                        continue
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # استخراج النتائج من HTML
                for i, result_div in enumerate(soup.select('.result'), 1):
                    if len(results) >= num_results:
                        break
                    
                    title_elem = result_div.select_one('.result__title a')
                    snippet_elem = result_div.select_one('.result__snippet')
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url_link = title_elem.get('href', '')
                    
                    # تنظيف URL من DuckDuckGo redirect
                    if url_link and 'uddg=' in str(url_link):
                        parsed = urllib.parse.urlparse(str(url_link))
                        qs = urllib.parse.parse_qs(parsed.query)
                        url_link = qs.get('uddg', [url_link])[0]
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=url_link,
                        snippet=snippet,
                        source="duckduckgo",
                        language="auto",
                    ))
                
                if results:
                    break
                    
            except Exception as e:
                if retry < max_retries - 1:
                    await asyncio.sleep(2 ** retry)
                    continue
        
        return results
    
    async def search_google(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث عبر Google (بدون API - scraping)"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                url = "https://www.google.com/search"
                params = {
                    "q": query,
                    "num": min(num_results, 100),
                    "hl": "en",
                    "complete": "0",
                }
                
                html = await self._make_request(url, params=params)
                if not html:
                    if retry < max_retries - 1:
                        await asyncio.sleep(5 * (retry + 1))
                        continue
                    break
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Google results selector
                for g in soup.select('div.g'):
                    if len(results) >= num_results:
                        break
                    
                    title_elem = g.select_one('h3')
                    link_elem = g.select_one('a')
                    snippet_elem = g.select_one('div[data-sncf], span.aCOpRe, div.VwiC3b')
                    
                    if not title_elem or not link_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url_link = link_elem.get('href', '')
                    if url_link.startswith('/url?q='):
                        url_link = urllib.parse.parse_qs(urllib.parse.urlparse(url_link).query).get('q', [url_link])[0]
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=url_link,
                        snippet=snippet,
                        source="google",
                    ))
                
                if results:
                    break
                    
            except Exception as e:
                if retry < max_retries - 1:
                    await asyncio.sleep(5 * (retry + 1))
                    continue
        
        return results
    
    async def search_bing(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث عبر Bing"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        try:
            url = "https://www.bing.com/search"
            params = {
                "q": query,
                "count": min(num_results, 50),
            }
            
            html = await self._make_request(url, params=params)
            if not html:
                return results
            
            soup = BeautifulSoup(html, 'html.parser')
            
            for li in soup.select('#b_results > li.b_algo'):
                if len(results) >= num_results:
                    break
                
                title_elem = li.select_one('h2 a')
                snippet_elem = li.select_one('.b_caption p')
                
                if not title_elem:
                    continue
                
                results.append(SearchResult(
                    title=title_elem.get_text(strip=True),
                    url=title_elem.get('href', ''),
                    snippet=snippet_elem.get_text(strip=True) if snippet_elem else "",
                    source="bing",
                ))
                
        except Exception as e:
            pass
        
        return results
    
    async def search_brave(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث عبر Brave Search"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        try:
            url = "https://search.brave.com/search"
            params = {
                "q": query,
                "source": "web",
            }
            
            html = await self._make_request(url, params=params)
            if not html:
                return results
            
            soup = BeautifulSoup(html, 'html.parser')
            
            for snippet in soup.select('div[class*="snippet"]'):
                if len(results) >= num_results:
                    break
                
                title_elem = snippet.select_one('a[class*="title"]')
                desc_elem = snippet.select_one('div[class*="description"]')
                
                if not title_elem:
                    continue
                
                results.append(SearchResult(
                    title=title_elem.get_text(strip=True),
                    url=title_elem.get('href', ''),
                    snippet=desc_elem.get_text(strip=True) if desc_elem else "",
                    source="brave",
                ))
                
        except Exception as e:
            pass
        
        return results

    async def _get_searx_instances(self) -> List[str]:
        """الحصول على قائمة خواديم SearXNG العاملة مع التخزين المؤقت"""
        import os
        import json
        import time
        
        fallback_instances = [
            "https://searx.be",
            "https://opnxng.com",
            "https://priv.au",
            "https://search.anoni.net",
            "https://paulgo.io",
            "https://search.catboy.house",
            "https://ooglester.com",
            "https://failsearx.culturanerd.it",
            "https://search.bladerunn.in",
            "https://etsi.me"
        ]
        
        if hasattr(config, 'searx_cache_file') and os.path.exists(config.searx_cache_file):
            try:
                def read_cache():
                    with open(config.searx_cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                cache_data = await asyncio.to_thread(read_cache)
                
                if time.time() - cache_data.get("timestamp", 0) < config.searx_cache_ttl:
                    instances = cache_data.get("instances", [])
                    if instances:
                        return instances
            except Exception:
                pass
                
        try:
            url = "https://searx.space/data/instances.json"
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    instances_dict = data.get("instances", {})
                    
                    working = []
                    for inst_url, details in instances_dict.items():
                        if not details or not isinstance(details, dict):
                            continue
                        
                        http_details = details.get("http", {})
                        if not http_details or not isinstance(http_details, dict):
                            continue
                        if http_details.get("status_code", 0) != 200:
                            continue
                            
                        uptime_details = details.get("uptime", {})
                        uptime = 0.0
                        if uptime_details and isinstance(uptime_details, dict):
                            uptime = uptime_details.get("uptimeMonth", 0.0)
                        if uptime < 90.0:
                            continue
                            
                        json_details = details.get("json", {})
                        if json_details and isinstance(json_details, dict):
                            if not json_details.get("supported", False):
                                continue
                                
                        working.append(inst_url.rstrip('/'))
                        
                    if working:
                        cache_data = {
                            "timestamp": time.time(),
                            "instances": working
                        }
                        if hasattr(config, 'searx_cache_file'):
                            def write_cache():
                                with open(config.searx_cache_file, "w", encoding="utf-8") as f:
                                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                            await asyncio.to_thread(write_cache)
                        return working
        except Exception as e:
            print(f"[⚠️] خطأ أثناء جلب قائمة SearXNG الديناميكية: {e}")
            
        return fallback_instances

    async def search_searx(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث عبر SearXNG (نسخة عامة مجانية بديناميكية جلب الخواديم)"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        
        searx_instances = await self._get_searx_instances()
        random.shuffle(searx_instances)
        
        session = await self._get_session()
        success_count = 0
        for instance in searx_instances:
            if success_count >= 3:
                break
            try:
                search_url = f"{instance}/search"
                params = {
                    "q": query,
                    "format": "json",
                    "language": "en-US",
                    "categories": "general",
                    "pageno": "1",
                }
                
                headers = {
                    "User-Agent": self._get_next_user_agent(),
                    "Accept": "application/json",
                }
                
                async with session.get(search_url, params=params, headers=headers, 
                                       timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("results", [])
                        if items:
                            for item in items[:num_results]:
                                results.append(SearchResult(
                                    title=item.get("title", ""),
                                    url=item.get("url", ""),
                                    snippet=item.get("content", ""),
                                    source=f"searx_{item.get('engine', 'unknown')}",
                                ))
                            success_count += 1
            except Exception:
                continue
        
        return results

    async def search_wikipedia(self, query: str, num_results: int = None) -> List[SearchResult]:
        """البحث في Wikipedia (عربي وإنجليزي) كبديل مستقر فائق الأهمية"""
        if num_results is None:
            num_results = config.results_per_engine
            
        results = []
        languages = ["ar", "en"]
        
        for lang in languages:
            try:
                url = f"https://{lang}.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": min(num_results, 15),
                    "format": "json",
                    "utf8": 1
                }
                
                headers = {
                    "User-Agent": "FuckenSearchBot/1.0 (https://fuckensearch.org; bot-traffic@fuckensearch.org) httpx/0.26.0",
                }
                
                session = await self._get_session()
                async with session.get(url, params=params, headers=headers, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        search_items = data.get("query", {}).get("search", [])
                        
                        for item in search_items:
                            title = item.get("title", "")
                            pageid = item.get("pageid", "")
                            snippet_html = item.get("snippet", "")
                            snippet = re.sub(r'<[^>]*>', '', snippet_html)
                            
                            page_url = f"https://{lang}.wikipedia.org/?curid={pageid}"
                            
                            results.append(SearchResult(
                                title=title,
                                url=page_url,
                                snippet=snippet,
                                source=f"wikipedia_{lang}",
                                language=lang,
                                relevance_score=0.9,
                            ))
            except Exception as e:
                print(f"[⚠️] فشل البحث في ويكيبيديا ({lang}): {e}")
                
        return results
    
    def deduplicate_and_sort(self, all_results: List[SearchResult]) -> List[SearchResult]:
        """إزالة التكرارات وترتيب النتائج حسب أهمية المصادر"""
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if not result or not result.url:
                continue
            normalized_url = result.url.lower().rstrip('/')
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_results.append(result)
        
        # ترتيب حسب جودة المصادر
        source_priority = {
            "wikipedia_ar": 1.0,
            "wikipedia_en": 0.95,
            "google": 0.90,
            "bing": 0.85,
            "searx": 0.80,
            "brave": 0.75,
            "duckduckgo": 0.70,
        }
        
        for result in unique_results:
            score = 0.5
            for prefix, val in source_priority.items():
                if result.source.startswith(prefix):
                    score = val
                    break
            result.relevance_score = score
        
        # ترتيب تنازلي حسب الأهمية
        unique_results.sort(key=lambda r: r.relevance_score, reverse=True)
        return unique_results[:config.max_final_results * 2]

    async def search_all(self, query: str, deep_search: bool = False) -> List[SearchResult]:
        """البحث في جميع محركات البحث المتاحة بشكل متوازي"""
        self.results = []
        
        search_tasks = []
        
        search_methods = {
            "duckduckgo": self.search_duckduckgo,
            "google": self.search_google,
            "bing": self.search_bing,
            "brave": self.search_brave,
            "searx": self.search_searx,
            "wikipedia": self.search_wikipedia,
        }
        
        engines_to_use = [e for e in config.search_engines if e in search_methods]
        
        async def search_with_timeout(engine_name: str, func, query: str) -> list:
            try:
                return await asyncio.wait_for(func(query), timeout=15)
            except asyncio.TimeoutError:
                print(f"[⏰] Engine '{engine_name}' timed out")
                return []
            except Exception as e:
                print(f"[⚠️] Engine '{engine_name}' error: {type(e).__name__}")
                return []
        
        for engine in engines_to_use:
            search_tasks.append(search_with_timeout(engine, search_methods[engine], query))
        
        engine_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        all_results = []
        for results in engine_results:
            if isinstance(results, list):
                all_results.extend(results)
        
        self.results = self.deduplicate_and_sort(all_results)
        return self.results
    
    async def close(self):
        """إغلاق الجلسة"""
        if self.session and not self.session.closed:
            await self.session.close()
