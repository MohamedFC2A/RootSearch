"""
RootSearch - High-Performance Resilient Fetching Engine
محرك الجلب الخارق: Circuit Breaker + Proxy Rotation + Stealth Anti-Bot Framework
"""

from __future__ import annotations

import asyncio
import enum
import json
import math
import random
import re
import socket
import ipaddress
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

import aiohttp
import aiohttp.abc
from bs4 import BeautifulSoup
import trafilatura

try:
    from fake_useragent import UserAgent as _FakeUA
    _ua_pool = _FakeUA()
except Exception:
    _ua_pool = None

from config import config, proxy_config
from core.net import SafeResolver
from core.search_engine import SearchResult


# ─────────────────────────────────────────────
#  SAFE DNS RESOLVER  (SSRF / DNS-Rebinding guard)
# ─────────────────────────────────────────────

# SafeResolver is defined once in core.net (single source of truth) and imported above.


# ─────────────────────────────────────────────
#  EXPONENTIAL BACKOFF WITH FULL JITTER
# ─────────────────────────────────────────────

def _backoff_delay(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
    """
    Full-jitter exponential backoff:
        sleep = random(0, min(cap, base * 2^attempt))
    Prevents thundering-herd on shared proxies / rate-limited endpoints.
    """
    ceiling = min(cap, base * (2 ** attempt))
    return random.uniform(0, ceiling)


# ─────────────────────────────────────────────
#  CIRCUIT BREAKER
# ─────────────────────────────────────────────

class CBState(enum.Enum):
    CLOSED = "closed"       # normal operation
    OPEN = "open"           # blocking all calls
    HALF_OPEN = "half_open" # testing recovery


class CircuitBreaker:
    """
    Per-domain circuit breaker.
    States: CLOSED → (too many failures) → OPEN → (recovery timeout) → HALF_OPEN → (success) → CLOSED
    """

    def __init__(self, failure_threshold: int = 4,
                 recovery_timeout: float = 45.0,
                 success_threshold: int = 2):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold

        # per-domain tracking
        self._failures: Dict[str, int] = defaultdict(int)
        self._successes: Dict[str, int] = defaultdict(int)
        self._state: Dict[str, CBState] = defaultdict(lambda: CBState.CLOSED)
        self._opened_at: Dict[str, datetime] = {}

    def get_state(self, domain: str) -> CBState:
        state = self._state[domain]
        if state == CBState.OPEN:
            opened = self._opened_at.get(domain)
            if opened and (datetime.utcnow() - opened).total_seconds() >= self._recovery_timeout:
                self._state[domain] = CBState.HALF_OPEN
                self._successes[domain] = 0
                return CBState.HALF_OPEN
        return self._state[domain]

    def is_allowed(self, domain: str) -> bool:
        return self.get_state(domain) != CBState.OPEN

    def record_success(self, domain: str) -> None:
        state = self.get_state(domain)
        if state == CBState.HALF_OPEN:
            self._successes[domain] += 1
            if self._successes[domain] >= self._success_threshold:
                self._state[domain] = CBState.CLOSED
                self._failures[domain] = 0
        elif state == CBState.CLOSED:
            self._failures[domain] = max(0, self._failures[domain] - 1)

    def record_failure(self, domain: str) -> None:
        self._failures[domain] += 1
        state = self.get_state(domain)
        if state in (CBState.CLOSED, CBState.HALF_OPEN):
            if self._failures[domain] >= self._failure_threshold:
                self._state[domain] = CBState.OPEN
                self._opened_at[domain] = datetime.utcnow()

    def domain_status(self, domain: str) -> str:
        return self.get_state(domain).value


# Shared global circuit breaker (across all scraper instances)
_circuit_breaker = CircuitBreaker(failure_threshold=4, recovery_timeout=45.0)


# ─────────────────────────────────────────────
#  PROXY ROTATOR
# ─────────────────────────────────────────────

class ProxyRotator:
    """
    Round-robin proxy rotation with health tracking.
    Proxies are temporarily blacklisted after consecutive failures.
    """

    def __init__(self, proxies: Optional[List[str]] = None,
                 max_failures: int = 3,
                 blacklist_ttl: float = 120.0):
        self._pool: List[str] = list(proxies or [])
        self._index = 0
        self._failures: Dict[str, int] = defaultdict(int)
        self._blacklisted_until: Dict[str, float] = {}
        self._max_failures = max_failures
        self._blacklist_ttl = blacklist_ttl

    def _is_healthy(self, proxy: str) -> bool:
        until = self._blacklisted_until.get(proxy, 0)
        if until > asyncio.get_event_loop().time():
            return False
        return True

    def get_proxy(self) -> Optional[str]:
        """Return next healthy proxy or None (direct connection)."""
        if not self._pool:
            return None
        attempts = len(self._pool)
        for _ in range(attempts):
            proxy = self._pool[self._index % len(self._pool)]
            self._index += 1
            if self._is_healthy(proxy):
                return proxy
        return None  # all blacklisted — fall through to direct

    def record_failure(self, proxy: str) -> None:
        self._failures[proxy] += 1
        if self._failures[proxy] >= self._max_failures:
            loop_time = 0.0
            try:
                loop_time = asyncio.get_event_loop().time()
            except RuntimeError:
                import time
                loop_time = time.monotonic()
            self._blacklisted_until[proxy] = loop_time + self._blacklist_ttl
            self._failures[proxy] = 0

    def record_success(self, proxy: str) -> None:
        self._failures[proxy] = 0

    @property
    def has_proxies(self) -> bool:
        return bool(self._pool)


# Global proxy rotator (populated from proxy_config when enabled)
_proxy_rotator = ProxyRotator(
    proxies=list(proxy_config.proxies) if getattr(proxy_config, 'enabled', False) else []
)


# ─────────────────────────────────────────────
#  STEALTH HEADERS & TLS SPOOF
# ─────────────────────────────────────────────

# Realistic ordered Accept-* header sets mimicking Chrome 124 on Windows
_CHROME_HEADER_SETS: List[Dict[str, str]] = [
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
        "DNT": "1",
    },
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9,ar;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": '"Firefox";v="125", "Not:A-Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    },
]

_WIKIPEDIA_UA = (
    "RootSearchBot/2.0 (https://rootsearch.app; bot@rootsearch.app) aiohttp/3.9"
)

# Plausible organic referers — make requests look like clicks from a search engine,
# which slips past naive Referer-based anti-bot checks.
_REFERER_POOL: List[str] = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://search.brave.com/",
    "https://www.google.com/search",
]


def _get_stealth_ua() -> str:
    """Return a realistic User-Agent string."""
    if _ua_pool:
        try:
            return _ua_pool.random
        except Exception:
            pass
    return random.choice(config.user_agents)


def _build_stealth_headers(url: str, is_wiki: bool = False,
                           referer: Optional[str] = None) -> Dict[str, str]:
    """Compose a randomised but coherent browser fingerprint header set."""
    if is_wiki:
        return {"User-Agent": _WIKIPEDIA_UA, "Accept": "*/*"}
    hset = random.choice(_CHROME_HEADER_SETS).copy()
    hset["User-Agent"] = _get_stealth_ua()
    # Present as organic navigation arriving from a search engine.
    hset["Referer"] = referer or random.choice(_REFERER_POOL)
    hset["Sec-Fetch-Site"] = "cross-site"
    return hset


# ─────────────────────────────────────────────
#  MAIN SCRAPER
# ─────────────────────────────────────────────

EventCallback = Optional[Callable[[str, Dict[str, Any]], None]]


class DeepScraper:
    """
    High-performance, resilient web scraper with:
    - Circuit Breaker per domain
    - Proxy rotation with health tracking
    - Exponential backoff + full jitter
    - TLS-spoof stealth headers
    - Per-domain cookie jar sessions
    - SSE event emission hook (on_event callback)
    - Graceful fallback to snippet/archive on total failure
    """

    def __init__(self, on_event: EventCallback = None):
        self._sessions: Dict[str, aiohttp.ClientSession] = {}   # per-domain
        self._cookie_jars: Dict[str, aiohttp.CookieJar] = {}
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._on_event = on_event
        self._cb = _circuit_breaker
        self._proxy = _proxy_rotator

    def _get_node_id(self, url: str) -> str:
        from urllib.parse import urlparse
        import hashlib
        domain = urlparse(url).netloc or url
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
        return f"scrape_{domain}_{url_hash}"

    # ── Event emission ────────────────────────────────────────────

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Fire SSE event to the registered callback (non-blocking)."""
        if self._on_event:
            try:
                self._on_event(event_type, payload)
            except Exception:
                pass

    # ── Session management (per-domain cookie isolation) ──────────

    async def _get_session(self, domain: str) -> aiohttp.ClientSession:
        if domain not in self._sessions or self._sessions[domain].closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._cookie_jars[domain] = jar
            timeout = aiohttp.ClientTimeout(
                total=config.request_timeout,
                connect=10,
                sock_read=20,
            )
            resolver = SafeResolver()
            conn = aiohttp.TCPConnector(
                limit=config.max_concurrent_requests,
                force_close=False,          # keep-alive enabled
                enable_cleanup_closed=True,
                resolver=resolver,
            )
            self._sessions[domain] = aiohttp.ClientSession(
                timeout=timeout,
                connector=conn,
                cookie_jar=jar,
            )
        return self._sessions[domain]

    # ── URL safety guard ─────────────────────────────────────────

    @staticmethod
    def _is_safe_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            h = (parsed.hostname or "").lower()
            if not h:
                return False
            if h in ("localhost", "127.0.0.1", "::1") or h.endswith(".local"):
                return False
            
            # Check if host is a numeric IP and verify it is not loopback/private/reserved
            try:
                ip = ipaddress.ip_address(h)
                if (ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_reserved):
                    return False
            except ValueError:
                # Host is not an IP address (e.g. domain name), which is normal and handled by SafeResolver
                pass
                
            return True
        except Exception:
            return False

    # ── Async DNS resolution (non-blocking, replaces socket.gethostbyname) ──

    @staticmethod
    async def _resolve_ip_async(hostname: Optional[str]) -> str:
        """Resolve a hostname to an IP without blocking the event loop."""
        if not hostname:
            return ""
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(
                hostname, None, family=socket.AF_INET, type=socket.SOCK_STREAM
            )
            if infos:
                return infos[0][4][0]
        except Exception:
            pass
        return ""

    # ── Core fetch with Circuit Breaker + Backoff + Proxy ────────

    async def fetch_page(self, url: str,
                         fallback_snippet: str = "") -> Optional[str]:
        """
        Fetch a URL with:
        1. Circuit breaker check (domain-level)
        2. Proxy rotation (if configured)
        3. Exponential backoff + full jitter on failure
        4. Graceful fallback to fallback_snippet if circuit is OPEN
        """
        nid = self._get_node_id(url)
        if not self._is_safe_url(url):
            self._emit("node_status_update", {
                "nodeId": nid,
                "status": "failed",
                "label": "SSRF blocked — unsafe URL",
            })
            return None

        domain = urlparse(url).netloc or url
        is_wiki = any(w in url.lower() for w in ["wikipedia.org", "wikimedia.org"])

        # ── Circuit Breaker guard ──
        if not self._cb.is_allowed(domain):
            self._emit("node_status_update", {
                "nodeId": nid,
                "status": "rerouted",
                "label": f"Circuit OPEN — using cached fallback for {domain}",
                "metadata": {"cb_state": "open"},
            })
            return fallback_snippet or None

        async with self.semaphore:
            session = await self._get_session(domain)

            for attempt in range(4):  # max 4 attempts
                proxy = self._proxy.get_proxy() if self._proxy.has_proxies else None
                # Each attempt rotates a fresh browser identity + referer for non-wiki
                # domains; only genuine wiki domains use the descriptive bot UA.
                headers = _build_stealth_headers(url, is_wiki=is_wiki)

                self._emit("node_status_update", {
                    "nodeId": nid,
                    "status": "fetching",
                    "label": f"Attempt {attempt + 1} — {domain}",
                    "metadata": {
                        "proxy": bool(proxy),
                        "stealth": True,
                        "attempt": attempt,
                    },
                })

                try:
                    kwargs: Dict[str, Any] = {
                        "headers": headers,
                        "allow_redirects": True,
                        "ssl": False,
                    }
                    if proxy:
                        kwargs["proxy"] = proxy

                    async with session.get(url, **kwargs) as resp:
                        if resp.status == 200:
                            ct = resp.headers.get("Content-Type", "")
                            if any(t in ct for t in ["text/html", "application/xhtml",
                                                      "application/json", "text/plain"]):
                                html = await resp.text(errors="replace")
                                self._cb.record_success(domain)
                                if proxy:
                                    self._proxy.record_success(proxy)
                                self._emit("node_status_update", {
                                    "nodeId": nid,
                                    "status": "success",
                                    "label": f"Fetched {len(html):,} chars from {domain}",
                                })
                                return html
                            else:
                                # non-text: try reading anyway
                                try:
                                    html = await resp.text(errors="replace")
                                    if html:
                                        self._cb.record_success(domain)
                                        return html
                                except Exception:
                                    pass

                        elif resp.status == 403:
                            self._emit("node_status_update", {
                                "nodeId": nid,
                                "status": "fetching",
                                "label": "Blocked (403) — rotating browser identity...",
                            })
                            # Do NOT switch to the bot UA here: the next loop iteration
                            # already rebuilds a fresh stealth identity + referer, which
                            # is what actually helps against Cloudflare/anti-bot walls.
                            delay = _backoff_delay(attempt, base=2.0, cap=12.0)
                            await asyncio.sleep(delay)

                        elif resp.status == 429:
                            self._emit("node_status_update", {
                                "nodeId": nid,
                                "status": "fetching",
                                "label": "Rate-limited — backing off...",
                            })
                            delay = _backoff_delay(attempt, base=3.0, cap=20.0)
                            await asyncio.sleep(delay)

                        elif resp.status in (404, 410):
                            # Permanent failure — don't retry
                            self._cb.record_failure(domain)
                            break

                        else:
                            delay = _backoff_delay(attempt, base=1.5, cap=15.0)
                            await asyncio.sleep(delay)

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if proxy:
                        self._proxy.record_failure(proxy)
                    err_msg = str(exc)
                    if "Access denied" in err_msg or "blocked" in err_msg:
                        self._emit("node_status_update", {
                            "nodeId": nid,
                            "status": "failed",
                            "label": f"SSRF guard blocked: {domain}",
                        })
                        return None

                    delay = _backoff_delay(attempt, base=1.5, cap=15.0)
                    await asyncio.sleep(delay)

                except Exception:
                    delay = _backoff_delay(attempt, base=1.0, cap=10.0)
                    await asyncio.sleep(delay)

            # Direct scraping failed — fallback to Jina Reader Network as a smart, fast backup!
            try:
                self._emit("node_status_update", {
                    "nodeId": nid,
                    "status": "fetching",
                    "label": f"Direct fetch failed — retrying via Reader Network...",
                })
                jina_url = f"https://r.jina.ai/{url}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "X-No-Cache": "true"
                }
                async with session.get(jina_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                    if resp.status == 200:
                        text_data = await resp.text(errors="replace")
                        if text_data and len(text_data) > 100:
                            self._cb.record_success(domain)
                            self._emit("node_status_update", {
                                "nodeId": nid,
                                "status": "success",
                                "label": f"Fetched {len(text_data):,} chars via Reader Network",
                            })
                            return text_data
            except Exception:
                pass

            # Tertiary fallback: Wayback Machine archived snapshot. Even when the
            # live origin blocks every request, an archived copy is usually reachable.
            try:
                wb_api = f"https://archive.org/wayback/available?url={url}"
                async with session.get(wb_api, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        snap = (data.get("archived_snapshots") or {}).get("closest") or {}
                        snap_url = snap.get("url")
                        if snap_url and snap.get("available"):
                            async with session.get(
                                snap_url,
                                headers=_build_stealth_headers(url),
                                timeout=aiohttp.ClientTimeout(total=12.0),
                            ) as r2:
                                if r2.status == 200:
                                    html = await r2.text(errors="replace")
                                    if html and len(html) > 200:
                                        self._cb.record_success(domain)
                                        self._emit("node_status_update", {
                                            "nodeId": nid,
                                            "status": "success",
                                            "label": f"Recovered {len(html):,} chars via Wayback archive",
                                        })
                                        return html
            except Exception:
                pass

            # All attempts exhausted — record failure
            self._cb.record_failure(domain)
            cb_state = self._cb.domain_status(domain)

            self._emit("node_status_update", {
                "nodeId": nid,
                "status": "failed" if cb_state != "open" else "rerouted",
                "label": (
                    f"Circuit OPEN — {domain} quarantined for 45s"
                    if cb_state == "open"
                    else f"All attempts failed — {domain}"
                ),
                "metadata": {"cb_state": cb_state, "can_retry": cb_state != "open"},
            })

            # Graceful fallback
            if fallback_snippet:
                return fallback_snippet
            return None

    # ── Content extraction pipeline ───────────────────────────────

    def extract_content_trafilatura(self, html: str, url: str) -> Dict[str, Any]:
        """Primary extractor — trafilatura (highest quality)."""
        try:
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format="json",
                with_metadata=True,
                max_tree_size=1_000_000,
                favor_precision=True,
            )
            if result:
                data = json.loads(result)
                return {
                    "title": data.get("title", ""),
                    "content": data.get("raw_text", ""),
                    "author": data.get("author", ""),
                    "date": data.get("date", ""),
                    "description": data.get("description", ""),
                    "site_name": data.get("sitename", ""),
                    "categories": data.get("categories", []),
                    "tags": data.get("tags", []),
                    "extraction_method": "trafilatura",
                }
        except Exception:
            pass
        return {}

    def extract_content_bs4(self, html: str, url: str) -> Dict[str, Any]:
        """Fallback extractor — BeautifulSoup."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            for el in soup(["script", "style", "nav", "header", "footer",
                            "iframe", "noscript", "svg", "form", "aside"]):
                el.decompose()

            title = soup.title.get_text(strip=True) if soup.title else ""

            description = ""
            m = soup.find("meta", attrs={"name": "description"}) or \
                soup.find("meta", attrs={"property": "og:description"})
            if m:
                description = m.get("content", "")

            content_parts: List[str] = []
            selectors = [
                "article", "main", '[role="main"]', ".post-content",
                ".article-content", ".entry-content", "#content", ".content",
                ".post", ".article", ".story-body", "[itemprop='articleBody']",
            ]
            for sel in selectors:
                try:
                    node = soup.select_one(sel)
                    if node:
                        for tag in node.find_all(
                                ["p", "h1", "h2", "h3", "h4", "h5", "h6",
                                 "li", "td", "th", "blockquote", "pre", "code"]):
                            t = tag.get_text(strip=True)
                            if t and len(t) > 20:
                                content_parts.append(t)
                        if content_parts:
                            break
                except Exception:
                    continue

            if not content_parts:
                for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
                    t = p.get_text(strip=True)
                    if t and len(t) > 30:
                        content_parts.append(t)

            content = "\n\n".join(content_parts)
            content = re.sub(r"\s+", " ", content)
            content = re.sub(r"\n{3,}", "\n\n", content)

            keywords: List[str] = []
            mk = soup.find("meta", attrs={"name": "keywords"})
            if mk:
                keywords = [k.strip() for k in mk.get("content", "").split(",") if k.strip()]

            return {
                "title": title,
                "content": content.strip()[:100_000],
                "description": description,
                "keywords": keywords,
                "extraction_method": "bs4",
            }
        except Exception as exc:
            return {"title": "", "content": "", "error": str(exc)}

    # ── Public API ─────────────────────────────────────────────────

    async def scrape_url(self, url: str,
                         fallback_snippet: str = "") -> Optional[Dict[str, Any]]:
        """Scrape a single URL — returns extracted content dict or None."""
        domain = urlparse(url).netloc or url
        nid = self._get_node_id(url)

        self._emit("tree_node", {
            "nodeId": nid,
            "stage": "extraction",
            "status": "pending",
            "label": domain,
            "parentId": "source_discovery",
        })

        html = await self.fetch_page(url, fallback_snippet=fallback_snippet)
        if not html:
            return None

        self._emit("node_status_update", {
            "nodeId": nid,
            "status": "processing",
            "label": "Extracting metadata...",
        })

        # Offload CPU-bound text extraction to background threads
        extracted = await asyncio.to_thread(self.extract_content_trafilatura, html, url)
        if not extracted.get("content"):
            extracted = await asyncio.to_thread(self.extract_content_bs4, html, url)

        if extracted.get("content"):
            extracted["url"] = url
            extracted["content_length"] = len(extracted["content"])
            extracted["word_count"] = len(extracted["content"].split())
            extracted["scrape_timestamp"] = datetime.now().isoformat()
            extracted["cb_state"] = self._cb.domain_status(domain)

            # Extract links in a background thread
            def get_links():
                from bs4 import BeautifulSoup
                links = []
                try:
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        full = urljoin(url, a["href"])
                        p = urlparse(full)
                        if (p.scheme in ("http", "https")
                                and not any(ext in p.path.lower()
                                            for ext in [".jpg", ".png", ".pdf", ".zip", ".mp4", ".gif", ".jpeg", ".svg", ".png", ".webp"])):
                            links.append(full.split('#')[0])
                except Exception:
                    pass
                return list(set(links))

            extracted["links"] = await asyncio.to_thread(get_links)

            extracted["resolved_ip"] = await self._resolve_ip_async(urlparse(url).hostname)

            self._emit("node_status_update", {
                "nodeId": nid,
                "status": "success",
                "label": f"Extracted {extracted['word_count']:,} words",
                "metadata": {
                    "method": extracted.get("extraction_method", ""),
                    "words": extracted["word_count"],
                    "cb_state": extracted["cb_state"],
                },
            })
            return extracted

        return None

    async def scrape_batch(self, results: List[SearchResult],
                           max_pages: int = 20, k_trusted: bool = False, query: str = "") -> List[SearchResult]:
        """Scrape a ranked list of results in parallel."""
        if k_trusted:
            from core.k_trusted import is_domain_authorized
            results = [r for r in results if is_domain_authorized(r.url, query)]
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        to_scrape = sorted_results[:max_pages]

        tasks = [
            self.scrape_url(r.url, fallback_snippet=r.snippet)
            for r in to_scrape
        ]
        scraped = await asyncio.gather(*tasks, return_exceptions=True)

        enriched = []
        for result, content in zip(to_scrape, scraped):
            if isinstance(content, dict) and content.get("content"):
                result.content = content["content"]
                result.metadata["scraped"] = True
                result.metadata["word_count"] = content.get("word_count", 0)
                result.metadata["extraction_method"] = content.get(
                    "extraction_method", "trafilatura")
                result.metadata["cb_state"] = content.get("cb_state", "closed")
            enriched.append(result)

        return enriched

    async def scrape_recursive(
        self,
        seeds: List[SearchResult],
        query: str,
        max_nodes: int = 40,
        max_depth: int = 3,
        concurrency: int = 5,
        aggregator = None,
        k_trusted: bool = False,
    ) -> List[SearchResult]:
        """
        Recursively trace hyperlinks up to max_depth,
        concurrently fetching pages and emitting dynamic nodes to the Live Tree.
        Bypasses rate limits using randomized jittered exponential backoffs,
        and incrementally yields results to the client (state hydration).
        """
        import hashlib
        from urllib.parse import urlparse
        import random
        
        def get_node_id(u: str) -> str:
            return "n_" + hashlib.md5(u.encode('utf-8')).hexdigest()[:8]

        if k_trusted:
            from core.k_trusted import is_domain_authorized
            seeds = [r for r in seeds if is_domain_authorized(r.url, query)]

        visited_urls = set()
        crawled_results: List[SearchResult] = []
        queued_urls = set()

        queue = asyncio.Queue()
        
        for idx, r in enumerate(seeds):
            norm = r.url.lower().rstrip('/')
            visited_urls.add(norm)
            queued_urls.add(norm)
            # Use the discovery node from metadata if available, else extraction
            parent_id = r.metadata.get("discovery_node", "extraction") if r.metadata else "extraction"
            await queue.put((r.url, 1, parent_id, r))


        async def worker():
            while True:
                try:
                    url, depth, parent_node_id, res_obj = await queue.get()
                except asyncio.CancelledError:
                    break
                
                if len(crawled_results) >= max_nodes:
                    queue.task_done()
                    continue

                node_id = get_node_id(url)
                domain = urlparse(url).netloc or url
                
                self._emit("tree_node", {
                    "nodeId": node_id,
                    "stage": "extraction",
                    "status": "pending",
                    "label": f"[{depth}] {domain}",
                    "parentId": parent_node_id,
                    "metadata": {"depth": depth}
                })

                self._emit("node_status_update", {
                    "nodeId": node_id,
                    "status": "fetching",
                    "label": f"Scanning Layer {depth}...",
                    "metadata": {"depth": depth}
                })

                scraped = None
                try:
                    scraped = await self.scrape_url(url, fallback_snippet=res_obj.snippet)
                except Exception as e:
                    self._emit("node_status_update", {
                        "nodeId": node_id,
                        "status": "failed",
                        "label": f"Error: {str(e)[:40]}"
                    })

                if scraped and scraped.get("content"):
                    res_obj.content = scraped["content"]
                    res_obj.metadata.update({
                        "scraped": True,
                        "word_count": scraped.get("word_count", 0),
                        "extraction_method": scraped.get("extraction_method", "trafilatura"),
                        "resolved_ip": scraped.get("resolved_ip", ""),
                        "cb_state": scraped.get("cb_state", "closed"),
                        "parent_url": res_obj.metadata.get("parent_url", ""),
                        "depth": depth
                    })
                    crawled_results.append(res_obj)

                    self._emit("node_status_update", {
                        "nodeId": node_id,
                        "status": "success",
                        "label": f"Extracted {scraped.get('word_count', 0):,} words",
                        "metadata": res_obj.metadata
                    })

                    # State Hydration update
                    if aggregator:
                        try:
                            report = await aggregator.aggregate(crawled_results.copy(), query, final_analysis=False)
                            self._emit("partial_results", report)
                        except Exception as ae:
                            print(f"[Hydration Error] {ae}")

                    if depth < max_depth and len(crawled_results) < max_nodes:
                        links = scraped.get("links", [])
                        if k_trusted:
                            from core.k_trusted import is_domain_authorized
                            links = [link for link in links if is_domain_authorized(link, query)]
                        random.shuffle(links)
                        enqueued = 0
                        for link in links:
                            if enqueued >= 3:
                                break
                            link_norm = link.lower().rstrip('/')
                            if link_norm not in queued_urls:
                                queued_urls.add(link_norm)
                                child_res = SearchResult(
                                    title=f"Subpage of {domain}",
                                    url=link,
                                    snippet=f"Discovered via link trace on {domain}",
                                    source="link_trace",
                                    relevance_score=res_obj.relevance_score * 0.8
                                )
                                child_res.metadata["parent_url"] = url
                                await queue.put((link, depth + 1, node_id, child_res))
                                enqueued += 1
                else:
                    self._emit("node_status_update", {
                        "nodeId": node_id,
                        "status": "failed",
                        "label": f"Extraction failed"
                    })
                
                queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await queue.join()
        for t in tasks:
            t.cancel()

        return crawled_results

    async def deep_scrape(self, url: str, max_depth: int = 2) -> Dict[str, Any]:
        """Recursively scrape a URL and its internal links (bounded depth)."""
        result: Dict[str, Any] = {
            "main_page": None,
            "related_pages": [],
            "all_content": "",
        }

        main_content = await self.scrape_url(url)
        if not main_content:
            return result

        result["main_page"] = main_content
        result["all_content"] = main_content.get("content", "")

        if max_depth > 1:
            html = await self.fetch_page(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                base_domain = urlparse(url).netloc
                internal_links: List[str] = []

                for a in soup.find_all("a", href=True):
                    full = urljoin(url, a["href"])
                    p = urlparse(full)
                    if (p.netloc == base_domain
                            and p.scheme in ("http", "https")
                            and not any(ext in p.path.lower()
                                        for ext in [".jpg", ".png", ".pdf",
                                                    ".zip", ".mp4", ".gif"])):
                        internal_links.append(full)

                for link in list(set(internal_links))[:5]:
                    c = await self.scrape_url(link)
                    if c:
                        result["related_pages"].append(c)
                        result["all_content"] += "\n\n" + c.get("content", "")

        return result

    async def close(self) -> None:
        """Close all open sessions."""
        for session in self._sessions.values():
            if not session.closed:
                await session.close()
        self._sessions.clear()
