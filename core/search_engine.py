"""
RootSearch - Search Engine Core Module v2.5
محرك البحث الخارق: يدعم 22+ مصدر مجاني 100% بدون API keys
Engines: DuckDuckGo (full + lite + instant), Startpage, GitHub, SearXNG,
         Wikipedia (ar+en), Wikidata, arXiv, OpenAlex, Semantic Scholar,
         PubMed, CrossRef, CORE, DOAJ, Europe PMC, BASE, StackExchange,
         HackerNews, OpenLibrary, Internet Archive
All scraped/public APIs — no paid keys required ever.
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
from core.net import SafeResolver

EventCallback = Optional[Callable[[str, Dict[str, Any]], None]]


# Truthful display names per engine key. Several keys are historical aliases whose
# real backing source differs from the label (the original provider blocks
# scraping); showing the true provider keeps the UI and provenance honest.
ENGINE_DISPLAY_NAMES: Dict[str, str] = {
    "duckduckgo": "DuckDuckGo",
    "startpage": "Startpage",
    "bing": "DuckDuckGo Lite",
    "brave": "GitHub",
    "mojeek": "DDG Instant Answers",
    "qwant": "Europe PMC",
    "ecosia": "BASE (Bielefeld)",
    "searx": "SearXNG",
    "wikipedia": "Wikipedia",
    "wikidata": "Wikidata",
    "arxiv": "arXiv",
    "openalex": "OpenAlex",
    "semantic_scholar": "Semantic Scholar",
    "pubmed": "PubMed",
    "crossref": "CrossRef",
    "core": "CORE",
    "stackexchange": "Stack Exchange",
    "reddit": "DOAJ",
    "hackernews": "Hacker News",
    "openlibrary": "Open Library",
    "internet_archive": "Internet Archive",
    "jina": "CORE Open Access",
}


def engine_display_name(key: str) -> str:
    """Return the truthful, human-readable provider name for an engine key."""
    return ENGINE_DISPLAY_NAMES.get(key, key.replace("_", " ").title())


# ─────────────────────────────────────────────
#  SAFE DNS RESOLVER  (SSRF / DNS-Rebinding guard)
# ─────────────────────────────────────────────

# SafeResolver is defined once in core.net (single source of truth) and imported above.


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
            r.relevance_score = score
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
                     json_mode: bool = False,
                     retries: int = 2) -> Optional[Any]:
        """Unified HTTP fetch with configurable retries. Returns str or dict depending on json_mode."""
        session = await self._get_session()
        if headers is None:
            headers = self._browser_headers()
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        for attempt in range(max(1, retries)):
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
                        if attempt < retries - 1:
                            await asyncio.sleep(min(5 * (attempt + 1), 15))
                        else:
                            return None
                    elif resp.status in (403, 404, 410):
                        return None
                    else:
                        if attempt < retries - 1:
                            await asyncio.sleep(1 * (attempt + 1))
            except (asyncio.TimeoutError, aiohttp.ClientError):
                if attempt >= retries - 1:
                    return None
                await asyncio.sleep(1)
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
        """Startpage = Google results without anti-bot. Uses verified 2024+ selectors."""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://www.startpage.com/search"
            params = {"q": query, "language": "en", "cat": "web"}
            headers = self._browser_headers("https://www.startpage.com/")
            html = await self._fetch(url, headers=headers, params=params, timeout=12.0, retries=1)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            # Verified 2024+ Startpage selectors:
            # Container: .result  |  Title+href: a.result-title  |  Snippet: p.description
            for item in soup.select(".result"):
                if len(results) >= num_results:
                    break
                # The anchor a.result-title has a direct real href (no redirect needed)
                link_el = item.select_one("a.result-title")
                title_el = item.select_one("a.result-title h2, .wgl-title, a.result-title")
                snippet_el = item.select_one("p.description")
                if not link_el or not title_el:
                    continue
                href = link_el.get("href", "")
                if not href or not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title_el.get_text(strip=True),
                    url=href,
                    snippet=snippet_el.get_text(strip=True) if snippet_el else "",
                    source="startpage",
                ))
        except Exception:
            pass
        return results

    # ── 3. DuckDuckGo Lite (ultra-reliable scraping) ──────────
    async def search_bing(self, query: str, num_results: int = None) -> List[SearchResult]:
        """DuckDuckGo Lite — replaces Bing (blocked by captcha). Extremely scraper-friendly."""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://lite.duckduckgo.com/lite/"
            params = {"q": query, "kl": "en-us"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://lite.duckduckgo.com/",
            }
            html = await self._fetch(url, headers=headers, params=params, timeout=10.0, retries=1)
            if not html:
                return results
            soup = BeautifulSoup(html, "html.parser")
            # DDG Lite: results are in table rows with class 'result-link' or 'result-snippet'
            rows = soup.select("tr")
            current_title = current_href = current_snippet = ""
            for row in rows:
                link_el = row.select_one("a.result-link")
                snip_el = row.select_one(".result-snippet")
                if link_el:
                    if current_href and current_title:
                        results.append(SearchResult(
                            title=current_title,
                            url=current_href,
                            snippet=current_snippet,
                            source="duckduckgo_lite",
                        ))
                        if len(results) >= num_results:
                            break
                    current_title = link_el.get_text(strip=True)
                    href = link_el.get("href", "")
                    if "uddg=" in href:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = qs.get("uddg", [href])[0]
                    current_href = href
                    current_snippet = ""
                elif snip_el:
                    current_snippet = snip_el.get_text(strip=True)
            # Add last result
            if current_href and current_title and len(results) < num_results:
                results.append(SearchResult(
                    title=current_title,
                    url=current_href,
                    snippet=current_snippet,
                    source="duckduckgo_lite",
                ))
        except Exception:
            pass
        return results

    # ── 4. GitHub Code & Repo Search (free, no key needed) ────
    async def search_brave(self, query: str, num_results: int = None) -> List[SearchResult]:
        """GitHub Search — replaces Brave (rate-limited). Free JSON API, no key for basic."""
        if num_results is None:
            num_results = config.results_per_engine
        results: List[SearchResult] = []
        try:
            url = "https://api.github.com/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": str(min(num_results, 20)),
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (research tool)",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True, retries=1)
            if not data:
                return results
            for repo in data.get("items", [])[:num_results]:
                name = repo.get("full_name", "")
                desc = repo.get("description", "") or ""
                href = repo.get("html_url", "")
                stars = repo.get("stargazers_count", 0)
                if not href:
                    continue
                results.append(SearchResult(
                    title=name,
                    url=href,
                    snippet=f"⭐ {stars:,} stars — {desc[:200]}",
                    source="github",
                    content_type="code",
                    relevance_score=0.82,
                ))
        except Exception:
            pass
        return results

    # ── 5. DuckDuckGo Instant Answers (fast structured data) ──
    async def search_mojeek(self, query: str, num_results: int = None) -> List[SearchResult]:
        """DuckDuckGo Instant Answers — replaces Mojeek (captcha). Free JSON API."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "no_redirect": "1",
                "skip_disambig": "1",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=8.0, json_mode=True, retries=1)
            if not data:
                return results
            # Abstract (main entity summary)
            abstract = data.get("Abstract", "")
            abstract_url = data.get("AbstractURL", "")
            abstract_title = data.get("Heading", "")
            if abstract and abstract_url and abstract_title:
                results.append(SearchResult(
                    title=abstract_title,
                    url=abstract_url,
                    snippet=abstract[:300],
                    source="ddg_instant",
                    content_type="summary",
                    relevance_score=0.90,
                ))
            # Related topics
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict) and topic.get("FirstURL"):
                    text = topic.get("Text", "")
                    first_url = topic.get("FirstURL", "")
                    if not first_url.startswith("http"):
                        continue
                    results.append(SearchResult(
                        title=text[:80] if text else first_url,
                        url=first_url,
                        snippet=text[:250],
                        source="ddg_instant",
                        content_type="reference",
                        relevance_score=0.77,
                    ))
                    if len(results) >= num_results:
                        break
        except Exception:
            pass
        return results

    # ── 6. Europe PMC (open access biomedical) ─────────────────
    async def search_qwant(self, query: str, num_results: int = None) -> List[SearchResult]:
        """Europe PMC — replaces Qwant (JS-required). Free open-access biomedical literature API."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            params = {
                "query": query,
                "resultType": "core",
                "pageSize": str(min(num_results, 20)),
                "format": "json",
                "sort": "RELEVANCE",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True, retries=1)
            if not data:
                return results
            for item in data.get("resultList", {}).get("result", [])[:num_results]:
                title = item.get("title", "")
                pmcid = item.get("pmcid", "")
                pmid = item.get("id", "")
                doi = item.get("doi", "")
                href = ""
                if pmcid:
                    href = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
                elif doi:
                    href = f"https://doi.org/{doi}"
                elif pmid:
                    href = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                if not href or not title:
                    continue
                abstract = item.get("abstractText", "") or ""
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=abstract[:250],
                    source="europepmc",
                    content_type="academic",
                    relevance_score=0.86,
                ))
        except Exception:
            pass
        return results

    # ── 7. SearXNG (curated reliable instances) ───────────────
    async def _get_searx_instances(self) -> List[str]:
        """Returns a curated list of high-uptime SearXNG instances (no dynamic fetching)."""
        # Curated from searx.space — high uptime, JSON supported, public
        return [
            "https://searx.be",
            "https://priv.au",
            "https://paulgo.io",
            "https://search.sapti.me",
            "https://opnxng.com",
            "https://search.ononoki.org",
            "https://etsi.me",
            "https://searxng.site",
            "https://search.inetol.net",
            "https://search.rhscz.eu",
            "https://darmarit.org/searx",
            "https://search.mdosch.de",
        ]

    async def search_searx(self, query: str, num_results: int = None) -> List[SearchResult]:
        """SearXNG — parallel queries across curated reliable instances (fail-fast, no retries)"""
        if num_results is None:
            num_results = config.results_per_engine
        instances = await self._get_searx_instances()
        random.shuffle(instances)
        instances_to_try = instances[:8]  # fewer, but reliable
        session = await self._get_session()

        async def _query(instance: str) -> List[SearchResult]:
            try:
                # Use short timeout + no retries for fast fail-over
                async with session.get(
                    f"{instance}/search",
                    headers=self._json_headers(),
                    params={"q": query, "format": "json", "language": "en-US",
                            "categories": "general", "pageno": "1"},
                    timeout=aiohttp.ClientTimeout(total=5.0),
                ) as resp:
                    if resp.status == 200:
                        resp_data = await resp.json(content_type=None)
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
                            "srlimit": min(num_results, 40), "format": "json", "utf8": 1},
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
            num_results = min(config.results_per_engine, 40)
        results: List[SearchResult] = []
        try:
            url = "https://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "start": "0",
                "max_results": str(min(num_results, 40)),
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
            num_results = min(config.results_per_engine, 40)
        results: List[SearchResult] = []
        try:
            url = "https://api.openalex.org/works"
            params = {
                "search": query,
                "per-page": str(min(num_results, 40)),
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
        """Semantic Scholar — AI-powered academic search, free API (fail-fast, no retries to avoid rate-limit waits)"""
        if num_results is None:
            num_results = min(config.results_per_engine, 40)
        results: List[SearchResult] = []
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "limit": str(min(num_results, 40)),
                "fields": "title,abstract,url,externalIds,year",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            # retries=1: fail fast if rate limited (429) — other academic engines cover the gap
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=8.0, json_mode=True, retries=1)
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
            num_results = min(config.results_per_engine, 40)
        results: List[SearchResult] = []
        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": str(min(num_results, 40)),
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

    # ── 13. DOAJ — Directory of Open Access Journals (replaces Reddit) ─
    async def search_reddit(self, query: str, num_results: int = None) -> List[SearchResult]:
        """DOAJ — Directory of Open Access Journals. Replaces Reddit (403 blocked). Free API."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://doaj.org/api/search/articles"
            params = {
                "q": query,
                "pageSize": str(min(num_results, 20)),
                "page": "1",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True, retries=1)
            if not data:
                return results
            for item in data.get("results", [])[:num_results]:
                bibjson = item.get("bibjson", {})
                title = bibjson.get("title", "")
                links = bibjson.get("link", [])
                href = ""
                for lnk in links:
                    if lnk.get("type") == "fulltext":
                        href = lnk.get("url", "")
                        break
                if not href and links:
                    href = links[0].get("url", "")
                abstract = bibjson.get("abstract", "") or ""
                journal = bibjson.get("journal", {}).get("title", "")
                if not title or not href:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=abstract[:250] or f"Published in: {journal}",
                    source="doaj",
                    content_type="academic",
                    relevance_score=0.82,
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
                "retmax": str(min(num_results, 40)),
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
        """Wikidata — structured knowledge graph. Uses Wikimedia-compliant User-Agent (required)."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "limit": str(min(num_results, 20)),
                "format": "json",
                "type": "item",
            }
            # Wikimedia REQUIRES a descriptive User-Agent with contact info
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=8.0, json_mode=True, retries=1)
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

    # ── 21. Semantic Scholar (public feed) + OpenAlex combo ──────
    async def search_jina(self, query: str, num_results: int = None) -> List[SearchResult]:
        """CORE Open Access Search — replaces Jina (requires API key). 300M+ open-access docs."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            # Use CORE Open Access API v3 (no key required for basic)
            url = "https://api.core.ac.uk/v3/search/works"
            params = {
                "q": query,
                "limit": str(min(num_results, 20)),
                "offset": "0",
                "fields": "id,title,abstract,downloadUrl,sourceFulltextUrls,authors,yearPublished",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True, retries=1)
            if not data:
                return results
            for item in data.get("results", [])[:num_results]:
                title = item.get("title", "")
                href = item.get("downloadUrl", "")
                if not href:
                    src_urls = item.get("sourceFulltextUrls") or []
                    href = src_urls[0] if src_urls else ""
                if not title or not href:
                    continue
                abstract = (item.get("abstract") or "")[:250]
                year = item.get("yearPublished", "")
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=f"{year} — {abstract}" if year else abstract,
                    source="core_open",
                    content_type="academic",
                    relevance_score=0.83,
                ))
        except Exception:
            pass
        return results

    # ── 22. BASE — Bielefeld Academic Search Engine (replaces Ecosia) ─
    async def search_ecosia(self, query: str, num_results: int = None) -> List[SearchResult]:
        """BASE (Bielefeld Academic Search Engine) — replaces Ecosia (JS firewall). 300M+ docs, free."""
        if num_results is None:
            num_results = min(config.results_per_engine, 10)
        results: List[SearchResult] = []
        try:
            url = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"
            params = {
                "func": "PerformSearch",
                "query": query,
                "hits": str(min(num_results, 20)),
                "offset": "0",
                "format": "json",
            }
            headers = {
                "User-Agent": "FuckenSearch/2.0 (mohamedahmedmatany@gmail.com; research tool)",
                "Accept": "application/json",
            }
            data = await self._fetch(url, headers=headers, params=params,
                                     timeout=10.0, json_mode=True, retries=1)
            if not data:
                return results
            docs = data.get("response", {}).get("docs", [])
            for doc in docs[:num_results]:
                title = doc.get("dctitle", ["" ])
                title = title[0] if isinstance(title, list) else title
                href = doc.get("dcidentifier", [""])
                href = href[0] if isinstance(href, list) else href
                abstract = doc.get("dcdescription", [""])
                abstract = abstract[0] if isinstance(abstract, list) else abstract
                if not title or not href or not href.startswith("http"):
                    continue
                results.append(SearchResult(
                    title=title,
                    url=href,
                    snippet=(abstract or "")[:250],
                    source="base_search",
                    content_type="academic",
                    relevance_score=0.80,
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
            "europepmc": 0.91, "crossref": 0.90,
            "core": 0.89, "core_open": 0.88,
            "startpage": 0.87, "stackexchange": 0.86,
            "doaj": 0.85, "base_search": 0.84,
            "wikidata": 0.83, "ddg_instant": 0.82,
            "hackernews": 0.81, "github": 0.80,
            "duckduckgo": 0.79, "duckduckgo_lite": 0.78,
            "openlibrary": 0.75, "internet_archive": 0.74,
            "searx": 0.70,
        }

        for r in unique:
            base = 0.5
            for prefix, val in source_priority.items():
                if r.source.startswith(prefix):
                    base = val
                    break
            r.relevance_score = r.relevance_score * base

        unique.sort(key=lambda r: r.relevance_score, reverse=True)
        return unique[:config.max_final_results * 2]

    def engine_methods(self) -> Dict[str, Any]:
        """Single source of truth: engine name → bound search method.

        NOTE: several names are historical aliases whose implementation targets a
        different source than the label (e.g. 'bing'→DDG Lite, 'brave'→GitHub,
        'qwant'→Europe PMC, 'ecosia'→BASE, 'reddit'→DOAJ, 'jina'→CORE) because the
        original provider blocks scraping. Kept stable so config/UI keep working.
        """
        return {
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
            # Community & code
            "stackexchange": self.search_stackexchange,
            "reddit": self.search_reddit,
            "hackernews": self.search_hackernews,
            # Books & archive
            "openlibrary": self.search_openlibrary,
            "internet_archive": self.search_internet_archive,
            # AI-powered / CORE open
            "jina": self.search_jina,
        }

    def select_engines(self, query: str) -> Dict[str, Any]:
        """Intent-filtered engine map (∩ config.search_engines).

        Prevents general queries from being polluted by academic-only sources.
        Guard: if the intent filter empties the set, fall back to every enabled
        engine so a query is never left with zero sources.
        """
        methods = self.engine_methods()
        from core.intent import classify_query
        suggested = set(classify_query(query).suggested_engines)
        selected = {
            name: func for name, func in methods.items()
            if name in suggested
            and (not config.search_engines or name in config.search_engines)
        }
        if not selected:
            selected = {
                name: func for name, func in methods.items()
                if not config.search_engines or name in config.search_engines
            }
        return selected

    async def search_all(self, query: str, model: str = "fathom_s1",
                         deep_search: bool = False, k_trusted: bool = False) -> List[SearchResult]:
        """بحث متوازي في 22+ مصدر + GraphCrawler semantic prioritisation"""
        self.results = []

        self._emit("tree_node", {
            "nodeId": "source_discovery", "stage": "source_discovery",
            "status": "pending", "label": "Discovering sources (22+ engines)...",
            "parentId": "trigger",
        })

        # Engine map + intent-based selection come from the single source of truth
        # (engine_methods/select_engines), shared with the web streaming pipeline.
        search_methods = self.engine_methods()
        engines_to_use = list(self.select_engines(query).keys())

        # Timeout depends on model
        timeout_val = 20.0 if model == "fathom_max" else 10.0

        async def _run_engine(name: str, func) -> tuple:
            disp = engine_display_name(name)
            self._emit("tree_node", {
                "nodeId": f"engine_{name}", "stage": "source_discovery",
                "status": "fetching",
                "label": f"Querying {disp}...",
                "parentId": "source_discovery",
            })
            try:
                res = await asyncio.wait_for(func(query), timeout=timeout_val)
                res = res or []
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}",
                    "status": "success" if res else "failed",
                    "label": (
                        f"{disp}: {len(res)} results"
                        if res else f"{disp}: no results"
                    ),
                    "metadata": {"count": len(res)},
                })
                return name, res
            except asyncio.TimeoutError:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}", "status": "failed",
                    "label": f"{disp}: timed out",
                })
                return name, []
            except Exception as exc:
                self._emit("node_status_update", {
                    "nodeId": f"engine_{name}", "status": "failed",
                    "label": f"{disp}: {type(exc).__name__}",
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
                    if k_trusted:
                        from core.k_trusted import is_domain_authorized
                        res = [r for r in res if is_domain_authorized(r.url, query)]
                    all_results.extend(res)

        # GraphCrawler semantic prioritisation
        crawler = GraphCrawler(query=query, max_nodes=200, on_event=self._on_event)
        prioritised = crawler.prioritise(all_results)
        if k_trusted:
            from core.k_trusted import is_domain_authorized
            prioritised = [r for r in prioritised if is_domain_authorized(r.url, query)]
        # Return a local (not shared self.results) so a pooled/shared engine stays
        # correct under concurrent requests — a parallel call must not be able to
        # clobber the list this call is about to return.
        final_results = self.deduplicate_and_sort(prioritised)
        self.results = final_results
        return final_results

    async def close(self):
        """إغلاق الجلسة"""
        if self.session and not self.session.closed:
            await self.session.close()
