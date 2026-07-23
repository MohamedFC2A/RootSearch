"""
RootSearch - Shared networking primitives
أدوات الشبكة المشتركة: محلل أسماء نطاقات آمن ضد SSRF / DNS Rebinding

Single source of truth for the SSRF-guarding DNS resolver used by both the
search engine and the scraper, so the guard cannot drift between modules.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any, Dict, List, Optional

import aiohttp
import aiohttp.abc
from config import config


class SSRFValidationError(OSError):
    """Raised when a resolved IP address violates SSRF security boundaries."""
    pass


class SafeResolver(aiohttp.abc.AbstractResolver):
    """Blocks loopback, private, multicast, and reserved IPs at DNS resolution time."""

    async def resolve(self, host: str, port: int = 0,
                      family: int = socket.AF_INET) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, family=family,
                                           type=socket.SOCK_STREAM)
        except Exception as exc:
            raise OSError(f"DNS resolution failed for {host}: {exc}")

        safe: List[Any] = []
        for info in infos:
            ip = info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip)
                if (ip_obj.is_loopback or ip_obj.is_private
                        or ip_obj.is_multicast or ip_obj.is_reserved):
                    continue
                safe.append(info)
            except ValueError:
                continue

        if not safe:
            raise SSRFValidationError(
                f"Access denied: Private or invalid IP addresses are blocked for {host}"
            )

        return [{
            "hostname": host,
            "host": item[4][0],
            "port": item[4][1],
            "family": item[0],
            "proto": item[2],
            "flags": socket.AI_NUMERICHOST,
        } for item in safe]

    async def close(self) -> None:
        pass


_MAX_DOMAIN_SESSIONS = 500
_GLOBAL_SESSIONS: Dict[str, aiohttp.ClientSession] = {}
_GLOBAL_SESSIONS_LOCK = asyncio.Lock()

_SEARCH_ENGINE_SESSION: Optional[aiohttp.ClientSession] = None
_SEARCH_ENGINE_LOCK = asyncio.Lock()

_ANALYZER_SESSION: Optional[aiohttp.ClientSession] = None
_ANALYZER_LOCK = asyncio.Lock()


async def get_global_session(domain: str) -> aiohttp.ClientSession:
    """Retrieve or create a globally shared ClientSession per domain for scraping."""
    async with _GLOBAL_SESSIONS_LOCK:
        # Bounded LRU-style eviction if max capacity reached
        if len(_GLOBAL_SESSIONS) >= _MAX_DOMAIN_SESSIONS and domain not in _GLOBAL_SESSIONS:
            oldest_domain, oldest_session = next(iter(_GLOBAL_SESSIONS.items()))
            if not oldest_session.closed:
                await oldest_session.close()
            del _GLOBAL_SESSIONS[oldest_domain]

        session = _GLOBAL_SESSIONS.get(domain)
        if session is None or session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            conn = aiohttp.TCPConnector(
                limit=1000,
                limit_per_host=20,
                force_close=False,
                enable_cleanup_closed=True,
                resolver=SafeResolver(),
            )
            timeout = aiohttp.ClientTimeout(
                total=config.request_timeout,
                connect=10,
                sock_read=20,
            )
            session = aiohttp.ClientSession(
                timeout=timeout,
                connector=conn,
                cookie_jar=jar,
            )
            _GLOBAL_SESSIONS[domain] = session
        return session


async def get_search_engine_session() -> aiohttp.ClientSession:
    """Retrieve or create a globally shared ClientSession for all search engines."""
    global _SEARCH_ENGINE_SESSION
    if _SEARCH_ENGINE_SESSION is None or _SEARCH_ENGINE_SESSION.closed:
        async with _SEARCH_ENGINE_LOCK:
            if _SEARCH_ENGINE_SESSION is None or _SEARCH_ENGINE_SESSION.closed:
                conn = aiohttp.TCPConnector(
                    limit=1000,
                    limit_per_host=50,
                    force_close=False,
                    enable_cleanup_closed=True,
                    resolver=SafeResolver(),
                )
                timeout = aiohttp.ClientTimeout(total=config.request_timeout)
                _SEARCH_ENGINE_SESSION = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=conn,
                )
    return _SEARCH_ENGINE_SESSION


async def get_analyzer_session() -> aiohttp.ClientSession:
    """Retrieve or create a globally shared ClientSession for LLM requests."""
    global _ANALYZER_SESSION
    if _ANALYZER_SESSION is None or _ANALYZER_SESSION.closed:
        async with _ANALYZER_LOCK:
            if _ANALYZER_SESSION is None or _ANALYZER_SESSION.closed:
                connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
                _ANALYZER_SESSION = aiohttp.ClientSession(connector=connector)
    return _ANALYZER_SESSION


async def close_global_sessions() -> None:
    """Gracefully close all globally cached sessions at application shutdown."""
    async with _GLOBAL_SESSIONS_LOCK:
        for domain, session in list(_GLOBAL_SESSIONS.items()):
            if not session.closed:
                await session.close()
        _GLOBAL_SESSIONS.clear()

    global _SEARCH_ENGINE_SESSION
    async with _SEARCH_ENGINE_LOCK:
        if _SEARCH_ENGINE_SESSION is not None and not _SEARCH_ENGINE_SESSION.closed:
            await _SEARCH_ENGINE_SESSION.close()
        _SEARCH_ENGINE_SESSION = None

    global _ANALYZER_SESSION
    async with _ANALYZER_LOCK:
        if _ANALYZER_SESSION is not None and not _ANALYZER_SESSION.closed:
            await _ANALYZER_SESSION.close()
        _ANALYZER_SESSION = None



