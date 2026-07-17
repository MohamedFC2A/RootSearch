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
from typing import Any, Dict, List

import aiohttp.abc


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
            raise OSError(
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
