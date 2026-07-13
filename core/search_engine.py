"""
RootSearch - Search Engine Core Module
محرك البحث الخارق: قلب نظام البحث في أعماق الإنترنت
يدعم محركات متعددة بدون API Keys — مع GraphCrawler وon_event hook للشجرة الحية
"""

from __future__ import annotations

import asyncio
import heapq
import math
import random
import re
import socket
import ipaddress
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
import time

import aiohttp
import aiohttp.abc
from bs4 import BeautifulSoup

try:
    from fake_useragent import UserAgent as _FakeUA
    _fua = _FakeUA()
except Exception:
    _fua = None

from config import config

EventCallback = Optional[Callable[[str, Dict[str, Any]], None]]


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


# ─────────────────────────────────────────────
#  GRAPH CRAWLER — BFS/DFS with Semantic Scoring
# ─────────────────────────────────────────────

class GraphCrawler:
    """
    Intelligent graph-based source-discovery crawler.
    Uses BFS with semantic relevance scoring to prioritise
    the most query-relevant URLs from a seed set.
    Score = TF-weighted keyword overlap + domain authority signal.
    """

    # High-authority TLD/domain suffixes (boost factor 1.4x)
    _AUTHORITY_BOOSTS: Dict[str, float] = {
        "wikipedia.org": 1.5, "britannica.com": 1.4, "reuters.com": 1.4,
        "bbc.com": 1.3, "nature.com": 1.4, "science.org": 1.4,
        "github.com": 1.3, "stackoverflow.com": 1.2, ".edu": 1.3, ".gov": 1.3,
    }

    def __init__(self, query: str, max_nodes: int = 60,
                 on_event: EventCallback = None):
        self._query_terms = self._tokenise(query)
        self._max_nodes = max_nodes
        self._visited: Set[str] = set()
        self._on_event = on_event

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        stop = {
            "the", "of", "and", "a", "to", "in", "is", "it", "was", "for",
            "من", "في", "على", "إلى", "عن", "مع", "هذا", "أن",
        }
        return [w.lower() for w in re.findall(r"\w+", text)
                if len(w) > 1 and w.lower() not in stop]

    def _semantic_score(self, url: str, title: str, snippet: str) -> float:
        """Compute relevance score for a candidate URL."""
        text = f"{title} {snippet} {url}".lower()
        tokens = self._tokenise(text)
        if not tokens:
            return 0.0
        token_freq: Dict[str, int] = defaultdict(int)
        for t in tokens:
            token_freq[t] += 1
        total = len(tokens)

        # TF-weighted overlap with query terms
        tf_sum = sum(
            math.log(1 + token_freq[qt]) / math.log(1 + total)
            for qt in self._query_terms if qt in token_freq
        )
        raw_score = tf_sum / max(len(self._query_terms), 1)

        # Domain authority boost
        domain = urllib.parse.urlparse(url).netloc.lower()
        authority = 1.0
        for suffix, boost in self._AUTHORITY_BOOSTS.items():
            if domain.endswith(suffix) or domain == suffix:
                authority = boost
                break

        return round(raw_score * authority, 4)

    def prioritise(self, candidates: List[SearchResult]) -> List[SearchResult]:
        """
        Score and return candidates sorted by semantic relevance (BFS frontier ordering).
        Uses a max-heap keyed by score for O(n log n) sorting.
        """
        scored: List[tuple] = []
        for r in candidates:
            if r.url in self._visited:
                continue
            score = self._semantic_score(r.url, r.title, r.snippet)
            r.relevance_score = max(r.relevance_score, score)
            heapq.heappush(scored, (-score, id(r), r))
            self._visited.add(r.url)

        sorted_results = []
        while scored and len(sorted_results) < self._max_nodes:
            neg_score, _, result = heapq.heappop(scored)
            sorted_results.append(result)

        if self._on_event:
            try:
                self._on_event("node_status_update", {
                    "nodeId": "source_discovery",
                    "status": "success",
                    "label": f"GraphCrawler scored {len(sorted_results)} sources",
                    "metadata": {"total_candidates": len(candidates)},
                })
            except Exception:
                pass

        return sorted_results


# ─────────────────────────────────────────────
#  SEARCH ENGINE
# ─────────────────────────────────────────────

class SearchEngine:
    """محرك البحث الأساسي — يدعم 6 محركات مع on_event hook وGraphCrawler"""

    def __init__(self, on_event: EventCallback = None):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[SearchResult] = []
        self._ua_index = 0
        self._on_event = on_event

    # ── Event emission ────────────────────────────────────────────

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._on_event:
            try:
                self._on_event(event_type, payload)
            except Exception:
                pass

    def _get_next_user_agent(self) -> str:
        """Platform-aware UA cycling via fake-useragent, falls back to config list."""
        if _fua:
            try:
                return _fua.random
            except Exception:
                pass
        ua = config.user_agents[self._ua_index]
        self._ua_index = (self._ua_index + 1) % len(config.user_agents)
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
                           params: Optional[Dict] = None, data: Optional[Dict] = None,
                           method: str = "GET") -> Optional[str]:
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
                async with session.request(method, url, headers=headers, params=params, data=data) as response:
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
        """البحث عبر DuckDuckGo (بدون API Key مع دعم التصفح المتعدد المتقدم)"""
        if num_results is None:
            num_results = config.results_per_engine
        
        results = []
        seen_urls = set()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://html.duckduckgo.com/",
        }
        
        # 1. جلب الصفحة الأولى (GET)
        vqd = None
        try:
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}
            html = await self._make_request(url, headers=headers, params=params, method="GET")
            if html:
                vqd = self._parse_ddg_html(html, results, seen_urls)
        except Exception:
            pass
            
        # 2. جلب الصفحات التالية (POST) باستخدام vqd المستخرج لزيادة عدد النتائج
        if vqd and len(results) < num_results:
            for page_offset in ["10", "24"]:
                if len(results) >= num_results:
                    break
                try:
                    data = {
                        "q": query,
                        "s": page_offset,
                        "v": "l",
                        "o": "json",
                        "dc": page_offset,
                        "api": "d.js",
                        "vqd": vqd,
                        "kl": "wt-wt"
                    }
                    html = await self._make_request(url, headers=headers, data=data, method="POST")
                    if html:
                        self._parse_ddg_html(html, results, seen_urls)
                    await asyncio.sleep(0.5) # تجنب الحظر السريع
                except Exception:
                    break
                    
        return results[:num_results]

    def _parse_ddg_html(self, html: str, results: List[SearchResult], seen_urls: set) -> Optional[str]:
        """تحليل الـ HTML المستخرج من DuckDuckGo واستخراج النتائج والـ vqd"""
        soup = BeautifulSoup(html, 'html.parser')
        
        for result_div in soup.select('.result'):
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
            
            normalized_url = url_link.lower().rstrip('/')
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            
            results.append(SearchResult(
                title=title,
                url=url_link,
                snippet=snippet,
                source="duckduckgo",
                language="auto",
            ))
            
        # استخراج vqd للاستخدام اللاحق
        vqd_input = soup.find('input', {'name': 'vqd'})
        return vqd_input.get('value') if vqd_input else None
    
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
        """البحث عبر SearXNG (نسخة عامة مجانية مع استعلام متوازي سريع ومقاوم للتأخير)"""
        if num_results is None:
            num_results = config.results_per_engine
        
        searx_instances = await self._get_searx_instances()
        random.shuffle(searx_instances)
        
        # استعلام حتى 15 خادم في نفس الوقت لضمان السرعة وتخطي الخوادم المحجوبة
        instances_to_try = searx_instances[:15]
        session = await self._get_session()
        
        async def query_instance(instance: str) -> List[SearchResult]:
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
                                       timeout=aiohttp.ClientTimeout(total=4.5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("results", [])
                        results_list = []
                        for item in items[:num_results]:
                            url = item.get("url", "")
                            if url:
                                results_list.append(SearchResult(
                                    title=item.get("title", ""),
                                    url=url,
                                    snippet=item.get("content", ""),
                                    source=f"searx_{item.get('engine', 'unknown')}",
                                ))
                        return results_list
            except Exception:
                pass
            return []

        tasks = [asyncio.create_task(query_instance(inst)) for inst in instances_to_try]
        
        all_results = []
        seen_urls = set()
        
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                for r in res:
                    norm_url = r.url.lower().rstrip('/')
                    if norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        all_results.append(r)
                if len(seen_urls) >= num_results:
                    break
                    
        # إلغاء المهام المتبقية فور توفر نتائج كافية
        for t in tasks:
            if not t.done():
                t.cancel()
                
        return all_results[:num_results]

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

    async def search_all(self, query: str, model: str = "fathom_s1", deep_search: bool = False) -> List[SearchResult]:
        """بحث متوازي في كل المحركات + GraphCrawler semantic prioritisation"""
        self.results = []

        self._emit("tree_node", {
            "nodeId": "source_discovery",
            "stage": "source_discovery",
            "status": "pending",
            "label": "Discovering sources...",
            "parentId": "trigger",
        })

        search_methods = {
            "duckduckgo": self.search_duckduckgo,
            "google": self.search_google,
            "bing": self.search_bing,
            "brave": self.search_brave,
            "searx": self.search_searx,
            "wikipedia": self.search_wikipedia,
        }
        engines_to_use = [e for e in config.search_engines if e in search_methods]
        timeout_val = 15.0 if model == "fathom_max" else 6.0

        async def search_with_timeout(engine_name: str, func) -> tuple:
            self._emit("tree_node", {
                "nodeId": f"engine_{engine_name}",
                "stage": "source_discovery",
                "status": "fetching",
                "label": f"Querying {engine_name.capitalize()}...",
                "parentId": "source_discovery",
            })
            try:
                res = await asyncio.wait_for(func(query), timeout=timeout_val)
                res = res or []
                self._emit("node_status_update", {
                    "nodeId": f"engine_{engine_name}",
                    "status": "success" if res else "failed",
                    "label": (
                        f"{engine_name.capitalize()}: {len(res)} results"
                        if res else f"{engine_name.capitalize()}: no results / blocked"
                    ),
                    "metadata": {"count": len(res)},
                })
                return engine_name, res
            except asyncio.TimeoutError:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{engine_name}",
                    "status": "failed",
                    "label": f"{engine_name.capitalize()}: timed out",
                })
                return engine_name, []
            except Exception as exc:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{engine_name}",
                    "status": "failed",
                    "label": f"{engine_name.capitalize()}: {type(exc).__name__}",
                })
                return engine_name, []

        tasks = [
            asyncio.create_task(search_with_timeout(name, fn))
            for name, fn in search_methods.items()
            if name in engines_to_use
        ]
        engine_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: List[SearchResult] = []
        for item in engine_results:
            if isinstance(item, tuple):
                _, res = item
                if isinstance(res, list):
                    all_results.extend(res)

        # ── GraphCrawler semantic prioritisation ──
        crawler = GraphCrawler(query=query, max_nodes=120, on_event=self._on_event)
        prioritised = crawler.prioritise(all_results)

        self.results = self.deduplicate_and_sort(prioritised)
        return self.results
    
    async def close(self):
        """إغلاق الجلسة"""
        if self.session and not self.session.closed:
            await self.session.close()
