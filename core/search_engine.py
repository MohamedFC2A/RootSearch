"""
RootSearch - Search Engine Core Module v2.0
محرك البحث الخارق: يدعم 22+ مصدر مجاني 100% بدون API keys
Fixed: Google → Startpage, Bing selectors, Brave selectors, DDG parsing
New: arXiv, OpenAlex, StackExchange, Reddit, HackerNews, PubMed,
     Wikidata, OpenLibrary, CrossRef, CORE, Semantic Scholar,
     Mojeek, Qwant, Ecosia, Jina (improved), Internet Archive
"""

from __future__ import annotations

import asyncio
import heapq
import math
import random
import re
import socket
import ipaddress
import json
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


# ─────────────────────────────────────────────
#  SAFE DNS RESOLVER  (SSRF / DNS-Rebinding guard)
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
#  SEARCH RESULT DATACLASS
# ─────────────────────────────────────────────

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

    _AUTHORITY_BOOSTS: Dict[str, float] = {
        "wikipedia.org": 1.5, "britannica.com": 1.4, "reuters.com": 1.4,
        "bbc.com": 1.3, "nature.com": 1.4, "science.org": 1.4,
        "arxiv.org": 1.5, "pubmed.ncbi.nlm.nih.gov": 1.4,
        "semanticscholar.org": 1.4, "openalex.org": 1.3,
        "stackoverflow.com": 1.3, "stackexchange.com": 1.2,
        "reddit.com": 1.1, "github.com": 1.3,
        "core.ac.uk": 1.3, "crossref.org": 1.2,
        ".edu": 1.3, ".gov": 1.3, ".ac.uk": 1.2,
    }

    def __init__(self, query: str, max_nodes: int = 120,
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
        text = f"{title} {snippet} {url}".lower()
        tokens = self._tokenise(text)
        if not tokens:
            return 0.0
        token_freq: Dict[str, int] = defaultdict(int)
        for t in tokens:
            token_freq[t] += 1
        total = len(tokens)

        tf_sum = sum(
            math.log(1 + token_freq[qt]) / math.log(1 + total)
            for qt in self._query_terms if qt in token_freq
        )
        raw_score = tf_sum / max(len(self._query_terms), 1)

        domain = urllib.parse.urlparse(url).netloc.lower()
        authority = 1.0
        for suffix, boost in self._AUTHORITY_BOOSTS.items():
            if domain.endswith(suffix) or domain == suffix:
                authority = boost
                break

        return round(raw_score * authority, 4)

    def prioritise(self, candidates: List[SearchResult]) -> List[SearchResult]:
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
#  SEARCH ENGINE — 22+ Sources
# ─────────────────────────────────────────────

class SearchEngine:
    """محرك البحث الأساسي — يدعم 22+ مصدر مجاني 100%"""

    # ── Anti-bot: rotating user agents ────────
    _DESKTOP_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ]

    def __init__(self, on_event: EventCallback = None):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[SearchResult] = []
        self._ua_index = 0
        self._on_event = on_event

    # ── Event emission ────────────────────────
    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._on_event:
            try:
                self._on_event(event_type, payload)
            except Exception:
                pass

    def _get_next_user_agent(self) -> str:
        if _fua:
            try:
                return _fua.random
            except Exception:
                pass
        ua = self._DESKTOP_UAS[self._ua_index % len(self._DESKTOP_UAS)]
        self._ua_index += 1
        return ua

    def _browser_headers(self, referer: str = "") -> Dict[str, str]:
        """Full browser-like headers to reduce bot detection"""
        h = {
            "User-Agent": self._get_next_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        if referer:
            h["Referer"] = referer
            h["Sec-Fetch-Site"] = "same-origin"
        return h

    def _json_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "FuckenSearch/2.0 (Python; research tool)",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=config.request_timeout)
            resolver = SafeResolver()
            connector = aiohttp.TCPConnector(resolver=resolver, ssl=False)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
        return self.session

    async def _fetch(self, url: str, headers: Optional[Dict] = None,
                     params: Optional[Dict] = None,
                     data: Optional[Dict] = None,
                     method: str = "GET",
                     timeout: float = 12.0,
                     json_mode: bool = False) -> Optional[Any]:
        """Unified HTTP fetch with retries. Returns str or dict depending on json_mode."""
        session = await self._get_session()
        if headers is None:
            headers = self._browser_headers()
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        for attempt in range(3):
            try:
                async with session.request(
                    method, url, headers=headers,
                    params=params, data=data,
                    timeout=client_timeout
                ) as resp:
                    if resp.status == 200:
                        if json_mode:
                            return await resp.json(content_type=None)
                        return await resp.text()
                    elif resp.status == 429:
                        await asyncio.sleep(min(10 * (attempt + 1), 30))
                    elif resp.status in (403, 404, 410):
                        return None
                    else:
                        await asyncio.sleep(2 * (attempt + 1))
            except (asyncio.TimeoutError, aiohttp.ClientError):
                if attempt == 2:
                    return None
                await asyncio.sleep(2 * (attempt + 1))
            except Exception:
                return None
        return None

    # ═══════════════════════════════════════════════════════════
    #  SEARCH ENGINE METHODS
    # ═══════════════════════════════════════════════════════════

    # ── 1. DuckDuckGo (improved) ──────────────────────────────
    async def search_duckduckgo(self, query: str, num_results: int = None) -> List[SearchResult]:
        """DuckDuckGo HTML scraping — improved vqd extraction & pagination"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        seen_urls: Set[str] = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://html.duckduckgo.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        url = "https://html.duckduckgo.com/html/"
        html = await self._fetch(url, headers=headers, params={"q": query}, timeout=10.0)
        vqd = None
        if html:
            vqd = self._parse_ddg_html(html, results, seen_urls)

        if vqd and len(results) < num_results:
            for page_offset in ["10", "24", "38"]:
                if len(results) >= num_results:
                    break
                try:
                    post_data = {
                        "q": query, "s": page_offset, "v": "l",
                        "o": "json", "dc": page_offset,
                        "api": "d.js", "vqd": vqd, "kl": "wt-wt",
                    }
                    html = await self._fetch(url, headers=headers, data=post_data, method="POST", timeout=10.0)
                    if html:
                        self._parse_ddg_html(html, results, seen_urls)
                    await asyncio.sleep(0.3)
                except Exception:
                    break

        return results[:num_results]

    def _parse_ddg_html(self, html: str, results: List[SearchResult], seen_urls: Set[str]) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        for div in soup.select(".result, .web-result"):
            title_el = div.select_one(".result__title a, .result__a")
            snippet_el = div.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if "uddg=" in str(href):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(str(href)).query)
                href = qs.get("uddg", [href])[0]
            norm = str(href).lower().rstrip("/")
            if not norm or norm in seen_urls:
                continue
            seen_urls.add(norm)
            results.append(SearchResult(
                title=title,
                url=str(href),
                snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                source="duckduckgo",
            ))
        vqd_el = soup.find("input", {"name": "vqd"})
        return vqd_el.get("value") if vqd_el else None

    # ── 2. Startpage (Google proxy — no CAPTCHA) ──────────────
    async def search_startpage(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Startpage = Google results without anti-bot. Reliable free alternative."""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://www.startpage.com/search"
            params = {"q": query, "language": "en", "cat": "web"}
            headers = self._browser_headers("https://www.startpage.com/")
            html = await self._fetch(url, headers=headers, params=params, timeout=12.0)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            # Startpage result containers
            for item in soup.select(".w-gl__result, .result, article.result"):
                if len(results) >= num_results:
                    break
                title_el = item.select_one("h3, .w-gl__result-title, a.w-gl__result-url")
                link_el = item.select_one("a.w-gl__result-title, a[href*='startpage.com/do/search']") or \
                           item.select_one("h3 a, a[data-testid='result-title-a']")
                snippet_el = item.select_one(".w-gl__description, p.description, .result-description")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = ""
                if link_el:
                    href = link_el.get("href", "")
                    # Decode startpage redirect URL
                    if "startpage.com" in href:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = qs.get("url", [href])[0]
                if not href or not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                    source="startpage",
                ))
        except Exception:
            pass
        return results

    # ── 3. Bing (fixed selectors) ─────────────────────────────
    async def search_bing(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Bing — updated selectors + improved headers"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://www.bing.com/search"
            params = {"q": query, "count": min(num_results, 50), "setlang": "en"}
            headers = self._browser_headers("https://www.bing.com/")
            headers["Cookie"] = "SRCHHPGUSR=SRCHLANG=en; _EDGE_S=ui=en-us"
            html = await self._fetch(url, headers=headers, params=params, timeout=12.0)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            # Multiple selectors for robustness
            for li in soup.select("#b_results > li.b_algo"):
                if len(results) >= num_results:
                    break
                title_el = li.select_one("h2 a")
                snippet_el = li.select_one(".b_caption p, .b_snippet, p.b_lineclamp2")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                if not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=href,
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                    source="bing",
                ))
        except Exception:
            pass
        return results

    # ── 4. Brave Search (fixed selectors) ─────────────────────
    async def search_brave(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Brave Search — updated CSS selectors"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://search.brave.com/search"
            params = {"q": query, "source": "web", "offset": "0"}
            headers = self._browser_headers("https://search.brave.com/")
            headers["Cookie"] = "safesearch=off"
            html = await self._fetch(url, headers=headers, params=params, timeout=12.0)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            # Brave search result selectors (2024+)
            for item in soup.select('[data-type="web"], .snippet, div.fdb'):
                if len(results) >= num_results:
                    break
                title_el = item.select_one("a .title, .title a, h3 a, a[data-testid='result-title']")
                link_el = item.select_one("a[href^='http']")
                desc_el = item.select_one(".snippet-description, .description, p.body")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                if not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=href,
                    snippet=desc_el.get_text(strip=True) if desc_el else "",
                    source="brave",
                ))
        except Exception:
            pass
        return results

    # ── 5. Mojeek (independent index) ─────────────────────────
    async def search_mojeek(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Mojeek — independent search engine, no Google/Bing dependency"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://www.mojeek.com/search"
            params = {"q": query, "s": "0", "fmt": "1"}
            headers = self._browser_headers("https://www.mojeek.com/")
            html = await self._fetch(url, headers=headers, params=params, timeout=10.0)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select("ul.results li.result, li.result"):
                if len(results) >= num_results:
                    break
                title_el = item.select_one("a.title, h2 a, h3 a")
                snippet_el = item.select_one("p.s, .s, p.f, .desc")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.mojeek.com" + href
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=href,
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                    source="mojeek",
                ))
        except Exception:
            pass
        return results

    # ── 6. Qwant (European search engine) ─────────────────────
    async def search_qwant(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Qwant — French privacy search engine, JSON API available"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://api.qwant.com/v3/search/web"
            params = {
                "q": query,
                "count": min(num_results, 20),
                "locale": "en_US",
                "offset": "0",
                "device": "desktop",
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.qwant.com/",
            }
            data = await self._fetch(url, headers=headers, params=params, timeout=10.0, json_mode=True)
            if not data:
                return results
            items = (data.get("data", {}).get("result", {}).get("items", {}).get("mainline", []))
            for group in items:
                if group.get("type") == "web":
                    for item in group.get("items", []):
                        if len(results) >= num_results:
                            break
                        href = item.get("url", "")
                        if not href:
                            continue
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=href,
                            snippet=item.get("desc", ""),
                            source="qwant",
                        ))
        except Exception:
            pass
        return results

    # ── 7. SearXNG (improved) ─────────────────────────────────
    async def _get_searx_instances(self) -> List[str]:
        fallback = [
            "https://searx.be",
            "https://search.sapti.me",
            "https://priv.au",
            "https://paulgo.io",
            "https://search.ononoki.org",
            "https://opnxng.com",
            "https://search.pabloferreiro.es",
            "https://search.catboy.house",
            "https://etsi.me",
            "https://darmarit.org/searx",
            "https://search.rhscz.eu",
            "https://search.bus-hit.me",
            "https://searxng.site",
            "https://search.mdosch.de",
            "https://search.inetol.net",
        ]
        if hasattr(config, "searx_cache_file"):
            import os
            if os.path.exists(config.searx_cache_file):
                try:
                    def _read():
                        with open(config.searx_cache_file, "r", encoding="utf-8") as f:
                            return json.load(f)
                    cache = await asyncio.to_thread(_read)
                    if time.time() - cache.get("timestamp", 0) < config.searx_cache_ttl:
                        inst = cache.get("instances", [])
                        if inst:
                            return inst
                except Exception:
                    pass
        try:
            url = "https://searx.space/data/instances.json"
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    raw = await resp.json(content_type=None)
                    working = []
                    for inst_url, details in raw.get("instances", {}).items():
                        if not isinstance(details, dict):
                            continue
                        http_ok = details.get("http", {}).get("status_code", 0) == 200
                        uptime = details.get("uptime", {}).get("uptimeMonth", 0.0)
                        json_ok = details.get("json", {}).get("supported", False)
                        if http_ok and uptime >= 85.0 and json_ok:
                            working.append(inst_url.rstrip("/"))
                    if working:
                        if hasattr(config, "searx_cache_file"):
                            def _write():
                                with open(config.searx_cache_file, "w", encoding="utf-8") as f:
                                    json.dump({"timestamp": time.time(), "instances": working}, f)
                            await asyncio.to_thread(_write)
                        return working
        except Exception:
            pass
        return fallback

    async def search_searx(self, query: str, num_results: int = None) -> List[SearchResult]:
        """SearXNG — parallel queries across 15 instances"""
        if num_results is None:
            num_results = config.results_per_engine
        instances = await self._get_searx_instances()
        random.shuffle(instances)
        instances_to_try = instances[:15]
        session = await self._get_session()

        async def _query(instance: str) -> List[SearchResult]:
            try:
                resp_data = await self._fetch(
                    f"{instance}/search",
                    headers=self._json_headers(),
                    params={"q": query, "format": "json", "language": "en-US",
                            "categories": "general", "pageno": "1"},
                    timeout=5.0, json_mode=True,
                )
                if resp_data:
                    out = []
                    for item in resp_data.get("results", [])[:num_results]:
                        if item.get("url"):
                            out.append(SearchResult(
                                title=item.get("title", ""),
                                url=item["url"],
                                snippet=item.get("content", ""),
                                source=f"searx_{item.get('engine', 'meta')}",
                            ))
                    return out
            except Exception:
                pass
            return []

        tasks = [asyncio.create_task(_query(i)) for i in instances_to_try]
        all_results: List[SearchResult] = []
        seen: Set[str] = set()
        for coro in asyncio.as_completed(tasks):
            res = await coro
            for r in res:
                norm = r.url.lower().rstrip("/")
                if norm not in seen:
                    seen.add(norm)
                    all_results.append(r)
            if len(all_results) >= num_results:
                break
        for t in tasks:
            if not t.done():
                t.cancel()
        return all_results[:num_results]

    # ── 8. Wikipedia (working — improved) ─────────────────────
    async def search_wikipedia(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Wikipedia API — عربي وإنجليزي"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        for lang in ("ar", "en"):
            try:
                data = await self._fetch(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    headers={"User-Agent": "FuckenSearch/2.0 (https://github.com/fuckensearch; research bot)"},
                    params={"action": "query", "list": "search", "srsearch": query,
                            "srlimit": min(num_results, 15), "format": "json", "utf8": 1},
                    timeout=10.0, json_mode=True,
                )
                if data:
                    for item in data.get("query", {}).get("search", []):
                        title = item.get("title", "")
                        pageid = item.get("pageid", "")
                        snippet = re.sub(r"<[^>]*>", "", item.get("snippet", ""))
                        results.append(SearchResult(
                            title=title,
                            url=f"https://{lang}.wikipedia.org/?curid={pageid}",
                            snippet=snippet,
                            source=f"wikipedia_{lang}",
                            language=lang,
                            relevance_score=0.92,
                        ))
            except Exception:
                pass
        return results

    # ── 9. arXiv (scientific papers) ──────────────────────────
    async def search_arxiv(self, query: str, num_results: int = None) -> List[SearchResult]:
        """arXiv.org — Free scientific preprints API (no key needed)"""
        if num_results is None:
            num_results = min(config.results_per_engine, 15)
        results: List[SearchResult] = []
        try:
            url = "https://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "start": "0",
                "max_results": str(min(num_results, 20)),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            xml_text = await self._fetch(url, headers=self._json_headers(), params=params, timeout=12.0)
            if not xml_text:
                return results
            # Parse Atom XML
            soup = BeautifulSoup(xml_text, "xml")
            for entry in soup.find_all("entry")[:num_results]:
                title = entry.find("title")
                summary = entry.find("summary")
                link = entry.find("link", {"type": "text/html"}) or entry.find("id")
                if not title:
                    continue
                href = link.get("href", "") if hasattr(link, "get") else (link.text if link else "")
                if not href:
                    continue
                results.append(SearchResult(
                    title=title.get_text(strip=True),
                    url=href.strip(),
                    snippet=(summary.get_text(strip=True)[:300] if summary else ""),
                    source="arxiv",
                    content_type="academic",
                    relevance_score=0.88,
                ))
        except Exception:
            pass
        return results

    # ── 10. OpenAlex (academic graph) ─────────────────────────
    async def search_openalex(self, query: str, num_results: int = None) -> List[SearchResult]:
        """OpenAlex — 250M+ academic works, completely free API"""
        if num_results is None:
            num_results = min(config.results_per_engine, 15)
        results: List[SearchResult] = []
        try:
            url = "https://api.openalex.org/works"
            params = {
                "search": query,
                "per-page": str(min(num_results, 25)),
                "select": "title,doi,abstract_inverted_index,open_access,primary_location",
                "mailto": "fuckensearch@research.org",  # polite pool — faster
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for item in data.get("results", [])[:num_results]:
                title = item.get("title", "")
                doi = item.get("doi", "")
                if doi and not doi.startswith("http"):
                    doi = f"https://doi.org/{doi}"
                loc = item.get("primary_location", {}) or {}
                landing = loc.get("landing_page_url", "") or doi
                if not landing:
                    continue
                # Reconstruct abstract from inverted index
                abstract = ""
                inv = item.get("abstract_inverted_index")
                if inv:
                    idx_words = sorted(((pos, word) for word, positions in inv.items()
                                        for pos in positions), key=lambda x: x[0])
                    abstract = " ".join(w for _, w in idx_words[:50])
                results.append(SearchResult(
                    title=title,
                    url=landing,
                    snippet=abstract[:300],
                    source="openalex",
                    content_type="academic",
                    relevance_score=0.87,
                ))
        except Exception:
            pass
        return results

    # ── 11. Semantic Scholar ───────────────────────────────────
    async def search_semantic_scholar(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Semantic Scholar — AI-powered academic search, free API"""
        if num_results is None:
            num_results = min(config.results_per_engine, 15)
        results: List[SearchResult] = []
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "limit": str(min(num_results, 20)),
                "fields": "title,abstract,url,externalIds,year",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for item in data.get("data", [])[:num_results]:
                title = item.get("title", "")
                paper_url = item.get("url", "")
                doi = item.get("externalIds", {}).get("DOI", "")
                href = paper_url or (f"https://doi.org/{doi}" if doi else "")
                if not href:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=(item.get("abstract") or "")[:300],
                    source="semantic_scholar",
                    content_type="academic",
                    relevance_score=0.86,
                ))
        except Exception:
            pass
        return results

    # ── 12. Stack Exchange (SO + all sites) ───────────────────
    async def search_stackexchange(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Stack Exchange API — free, covers Stack Overflow + 170 sites"""
        if num_results is None:
            num_results = min(config.results_per_engine, 15)
        results: List[SearchResult] = []
        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": str(min(num_results, 25)),
                "filter": "withbody",
                "key": "",  # without key: 300 req/day (with key: 10k)
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for item in data.get("items", [])[:num_results]:
                title = item.get("title", "")
                link = item.get("link", "")
                if not link:
                    continue
                body = re.sub(r"<[^>]+>", " ", item.get("body", ""))[:300]
                results.append(SearchResult(
                    title=title,
                    url=link,
                    snippet=body,
                    source="stackexchange",
                    content_type="qa",
                    relevance_score=0.83,
                ))
        except Exception:
            pass
        return results

    # ── 13. Reddit (JSON API — no key) ────────────────────────
    async def search_reddit(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Reddit search — official JSON endpoint, no API key required"""
        if num_results is None:
            num_results = min(config.results_per_engine, 15)
        results: List[SearchResult] = []
        try:
            url = "https://www.reddit.com/search.json"
            params = {
                "q": query,
                "sort": "relevance",
                "t": "year",
                "limit": str(min(num_results, 25)),
                "type": "link",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (python:research:v2.0 by /u/fuckensearch)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True)
            if not data:
                return results
            for item in data.get("data", {}).get("children", [])[:num_results]:
                post = item.get("data", {})
                title = post.get("title", "")
                permalink = post.get("permalink", "")
                href = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
                selftext = post.get("selftext", "")[:200]
                if not href:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=selftext,
                    source="reddit",
                    content_type="community",
                    relevance_score=0.78,
                ))
        except Exception:
            pass
        return results

    # ── 14. Hacker News (Algolia API) ─────────────────────────
    async def search_hackernews(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Hacker News via Algolia — completely free, no key"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "query": query,
                "hitsPerPage": str(min(num_results, 20)),
                "tags": "story",
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=8.0, json_mode=True)
            if not data:
                return results
            for item in data.get("hits", [])[:num_results]:
                title = item.get("title", "")
                url_val = item.get("url", "")
                hn_id = item.get("objectID", "")
                href = url_val or f"https://news.ycombinator.com/item?id={hn_id}"
                if not href:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=item.get("story_text", "")[:200] if item.get("story_text") else "",
                    source="hackernews",
                    content_type="community",
                    relevance_score=0.79,
                ))
        except Exception:
            pass
        return results

    # ── 15. PubMed (medical research) ─────────────────────────
    async def search_pubmed(self, query: str, num_results: int = None) -> List[SearchResult]:
        """PubMed / NCBI — free API for medical & life science research"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            # Step 1: eSearch to get PMIDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed", "term": query,
                "retmax": str(min(num_results, 15)),
                "retmode": "json", "sort": "relevance",
                "tool": "FuckenSearch", "email": "fuckensearch@research.org",
            }
            data = await self._fetch(search_url, headers=self._json_headers(),
                                     params=params, timeout=10.0, json_mode=True)
            if not data:
                return results
            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return results

            # Step 2: eSummary to get titles
            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            sum_params = {
                "db": "pubmed", "id": ",".join(ids),
                "retmode": "json",
                "tool": "FuckenSearch", "email": "fuckensearch@research.org",
            }
            sum_data = await self._fetch(summary_url, headers=self._json_headers(),
                                          params=sum_params, timeout=10.0, json_mode=True)
            if not sum_data:
                return results
            summaries = sum_data.get("result", {})
            for pmid in ids[:num_results]:
                s = summaries.get(pmid, {})
                title = s.get("title", "")
                if not title:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    snippet=f"Authors: {', '.join([a.get('name', '') for a in s.get('authors', [])[:3]])} | {s.get('fulljournalname', '')} | {s.get('pubdate', '')}",
                    source="pubmed",
                    content_type="academic",
                    relevance_score=0.85,
                ))
        except Exception:
            pass
        return results

    # ── 16. Wikidata SPARQL ────────────────────────────────────
    async def search_wikidata(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Wikidata — structured knowledge graph via SPARQL"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            # Use Wikidata search API (simpler than SPARQL for general queries)
            url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "limit": str(min(num_results, 20)),
                "format": "json",
                "type": "item",
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=8.0, json_mode=True)
            if not data:
                return results
            for item in data.get("search", [])[:num_results]:
                qid = item.get("id", "")
                label = item.get("label", "")
                desc = item.get("description", "")
                if not qid:
                    continue
                results.append(SearchResult(
                    title=label,
                    url=f"https://www.wikidata.org/wiki/{qid}",
                    snippet=desc,
                    source="wikidata",
                    content_type="structured",
                    relevance_score=0.80,
                ))
        except Exception:
            pass
        return results

    # ── 17. OpenLibrary (Internet Archive) ────────────────────
    async def search_openlibrary(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Open Library — millions of books, completely free API"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://openlibrary.org/search.json"
            params = {
                "q": query,
                "limit": str(min(num_results, 20)),
                "fields": "key,title,author_name,first_sentence,subject",
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=10.0, json_mode=True)
            if not data:
                return results
            for doc in data.get("docs", [])[:num_results]:
                title = doc.get("title", "")
                key = doc.get("key", "")
                if not title or not key:
                    continue
                authors = doc.get("author_name", [])
                first_sent = doc.get("first_sentence", [])
                snippet_parts = []
                if authors:
                    snippet_parts.append(f"By: {', '.join(authors[:2])}")
                if first_sent:
                    snippet_parts.append(first_sent[0][:150] if isinstance(first_sent, list) else str(first_sent)[:150])
                results.append(SearchResult(
                    title=title,
                    url=f"https://openlibrary.org{key}",
                    snippet=" | ".join(snippet_parts),
                    source="openlibrary",
                    content_type="book",
                    relevance_score=0.76,
                ))
        except Exception:
            pass
        return results

    # ── 18. CrossRef (DOI & publications) ─────────────────────
    async def search_crossref(self, query: str, num_results: int = None) -> List[SearchResult]:
        """CrossRef — 100M+ scholarly publications DOI search, free"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://api.crossref.org/works"
            params = {
                "query": query,
                "rows": str(min(num_results, 20)),
                "select": "title,URL,abstract,author,published,container-title",
                "mailto": "fuckensearch@research.org",
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for item in data.get("message", {}).get("items", [])[:num_results]:
                titles = item.get("title", [])
                title = titles[0] if titles else ""
                href = item.get("URL", "")
                if not title or not href:
                    continue
                abstract = item.get("abstract", "")
                abstract = re.sub(r"<[^>]+>", " ", abstract)[:250]
                journal = item.get("container-title", [""])[0]
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=abstract or f"Published in: {journal}",
                    source="crossref",
                    content_type="academic",
                    relevance_score=0.84,
                ))
        except Exception:
            pass
        return results

    # ── 19. CORE (open access papers) ─────────────────────────
    async def search_core(self, query: str, num_results: int = None) -> List[SearchResult]:
        """CORE — 200M+ open access research papers, free API (no key needed for basic)"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://api.core.ac.uk/v3/search/works"
            params = {"q": query, "limit": str(min(num_results, 20)), "offset": "0"}
            headers = {
                "User-Agent": "FuckenSearch/2.0 (research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for item in data.get("results", [])[:num_results]:
                title = item.get("title", "")
                href = item.get("downloadUrl", "") or item.get("sourceFulltextUrls", [None])[0]
                if not title or not href:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=(item.get("abstract") or "")[:250],
                    source="core",
                    content_type="academic",
                    relevance_score=0.82,
                ))
        except Exception:
            pass
        return results

    # ── 20. Internet Archive (Wayback search) ─────────────────
    async def search_internet_archive(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Internet Archive Full-Text Search — free, no key"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://archive.org/advancedsearch.php"
            params = {
                "q": query,
                "fl[]": ["identifier", "title", "description", "subject"],
                "rows": str(min(num_results, 20)),
                "page": "1",
                "output": "json",
                "save": "yes",
            }
            data = await self._fetch(url, headers=self._json_headers(), params=params,
                                     timeout=12.0, json_mode=True)
            if not data:
                return results
            for doc in data.get("response", {}).get("docs", [])[:num_results]:
                title = doc.get("title", "")
                ident = doc.get("identifier", "")
                if not title or not ident:
                    continue
                desc = doc.get("description", "")
                if isinstance(desc, list):
                    desc = " ".join(desc[:2])
                results.append(SearchResult(
                    title=title,
                    url=f"https://archive.org/details/{ident}",
                    snippet=str(desc)[:250],
                    source="internet_archive",
                    content_type="archive",
                    relevance_score=0.74,
                ))
        except Exception:
            pass
        return results

    # ── 21. Jina AI Reader + Search (improved) ────────────────
    async def search_jina(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Jina Search — free endpoint, AI-optimized results"""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = f"https://s.jina.ai/{urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "X-Return-Format": "json",
            }
            data = await self._fetch(url, headers=headers, timeout=10.0, json_mode=True)
            if data:
                items = data if isinstance(data, list) else data.get("data", [])
                for item in items[:num_results]:
                    href = item.get("url", "")
                    if not href:
                        continue
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=href,
                        snippet=item.get("description", item.get("snippet", ""))[:250],
                        source="jina",
                    ))
            else:
                # Text/markdown fallback
                text = await self._fetch(url, headers={**headers, "Accept": "text/plain"}, timeout=10.0)
                if text:
                    matches = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)\n*([^\[\n]+)?", text)
                    for m in matches[:num_results]:
                        title, href, snippet = m
                        results.append(SearchResult(
                            title=title.strip(),
                            url=href.strip(),
                            snippet=(snippet or "").strip()[:200],
                            source="jina",
                        ))
        except Exception:
            pass
        return results

    # ── 22. Ecosia (eco-friendly, Bing-based) ─────────────────
    async def search_ecosia(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Ecosia — privacy search engine, tree-planting"""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://www.ecosia.org/search"
            params = {"q": query, "addon": "opera"}
            headers = self._browser_headers("https://www.ecosia.org/")
            html = await self._fetch(url, headers=headers, params=params, timeout=10.0)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select("article.result, .result__body, [class*='mainline__result']"):
                if len(results) >= num_results:
                    break
                title_el = item.select_one("a.result__title, .result__title a, h2 a")
                snippet_el = item.select_one(".result__description, .result__snippet, p")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.ecosia.org" + href
                # Decode ecosia redirect
                if "ecosia.org" in href and "url=" in href:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = qs.get("url", [href])[0]
                if not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=href,
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                    source="ecosia",
                ))
        except Exception:
            pass
        return results

    # ═══════════════════════════════════════════════════════════
    #  DEDUP + SORT + SEARCH ALL
    # ═══════════════════════════════════════════════════════════

    def deduplicate_and_sort(self, all_results: List[SearchResult]) -> List[SearchResult]:
        """إزالة التكرارات وترتيب النتائج حسب أهمية المصادر"""
        seen_urls: Set[str] = set()
        unique: List[SearchResult] = []
        for r in all_results:
            if not r or not r.url:
                continue
            norm = r.url.lower().rstrip("/")
            if norm not in seen_urls:
                seen_urls.add(norm)
                unique.append(r)

        source_priority = {
            "wikipedia_ar": 1.00, "wikipedia_en": 0.97,
            "arxiv": 0.95, "pubmed": 0.94,
            "semantic_scholar": 0.93, "openalex": 0.92,
            "crossref": 0.90, "core": 0.88,
            "startpage": 0.87, "stackexchange": 0.86,
            "google": 0.85, "bing": 0.84,
            "wikidata": 0.83,
            "hackernews": 0.82, "jina": 0.81,
            "brave": 0.80, "duckduckgo": 0.79,
            "qwant": 0.78, "mojeek": 0.77,
            "reddit": 0.76, "openlibrary": 0.75,
            "internet_archive": 0.74, "ecosia": 0.72,
            "searx": 0.70,
        }

        for r in unique:
            base = 0.5
            for prefix, val in source_priority.items():
                if r.source.startswith(prefix):
                    base = val
                    break
            r.relevance_score = max(r.relevance_score, base)

        unique.sort(key=lambda r: r.relevance_score, reverse=True)
        return unique[:config.max_final_results * 2]

    async def search_all(self, query: str, model: str = "fathom_s1",
                         deep_search: bool = False) -> List[SearchResult]:
        """بحث متوازي في 22+ مصدر + GraphCrawler semantic prioritisation"""
        self.results = []

        self._emit("tree_node", {
            "nodeId": "source_discovery", "stage": "source_discovery",
            "status": "pending", "label": "Discovering sources (22+ engines)...",
            "parentId": "trigger",
        })

        # All search methods — grouped by category
        search_methods: Dict[str, Any] = {
            # General search engines
            "duckduckgo": self.search_duckduckgo,
            "startpage": self.search_startpage,
            "bing": self.search_bing,
            "brave": self.search_brave,
            "mojeek": self.search_mojeek,
            "qwant": self.search_qwant,
            "ecosia": self.search_ecosia,
            "searx": self.search_searx,
            # Encyclopedia & structured
            "wikipedia": self.search_wikipedia,
            "wikidata": self.search_wikidata,
            # Academic sources
            "arxiv": self.search_arxiv,
            "openalex": self.search_openalex,
            "semantic_scholar": self.search_semantic_scholar,
            "pubmed": self.search_pubmed,
            "crossref": self.search_crossref,
            "core": self.search_core,
            # Community
            "stackexchange": self.search_stackexchange,
            "reddit": self.search_reddit,
            "hackernews": self.search_hackernews,
            # Books & archive
            "openlibrary": self.search_openlibrary,
            "internet_archive": self.search_internet_archive,
            # AI-powered
            "jina": self.search_jina,
        }

        # Filter by config (if config.search_engines is set, only use those)
        engines_to_use = [
            e for e in search_methods
            if not config.search_engines or e in config.search_engines
        ]

        # Timeout depends on model
        timeout_val = 20.0 if model == "fathom_max" else 10.0

        async def _run_engine(name: str, func) -> tuple:
            self._emit("tree_node", {
                "nodeId": f"engine_{name}", "stage": "source_discovery",
                "status": "fetching",
                "label": f"Querying {name.replace('_', ' ').title()}...",
                "parentId": "source_discovery",
            })
            try:
                res = await asyncio.wait_for(func(query), timeout=timeout_val)
                res = res or []
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}",
                    "status": "success" if res else "failed",
                    "label": (
                        f"{name.replace('_', ' ').title()}: {len(res)} results"
                        if res else f"{name.replace('_', ' ').title()}: no results"
                    ),
                    "metadata": {"count": len(res)},
                })
                return name, res
            except asyncio.TimeoutError:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}", "status": "failed",
                    "label": f"{name}: timed out",
                })
                return name, []
            except Exception as exc:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}", "status": "failed",
                    "label": f"{name}: {type(exc).__name__}",
                })
                return name, []

        tasks = [
            asyncio.create_task(_run_engine(name, search_methods[name]))
            for name in engines_to_use
        ]
        engine_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: List[SearchResult] = []
        for item in engine_results:
            if isinstance(item, tuple):
                _, res = item
                if isinstance(res, list):
                    all_results.extend(res)

        # GraphCrawler semantic prioritisation
        crawler = GraphCrawler(query=query, max_nodes=200, on_event=self._on_event)
        prioritised = crawler.prioritise(all_results)
        self.results = self.deduplicate_and_sort(prioritised)
        return self.results

    async def close(self):
        """إغلاق الجلسة"""
        if self.session and not self.session.closed:
            await self.session.close()
