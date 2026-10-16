from __future__ import annotations

import ipaddress
import json
import time
import urllib.request
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .settings import GEOIP_API_TIMEOUT, GEOIP_API_URL, GEOIP_CACHE_TTL, TRUSTED_PROXY_CIDRS

_geoip_cache: dict[str, tuple[float, tuple[str | None, str | None, str | None]]] = {}
_rate_buckets: dict[str, deque] = defaultdict(deque)
_login_failures: dict[str, deque] = defaultdict(deque)
_login_lockouts: dict[str, float] = {}


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        trusted = [ipaddress.ip_network(cidr.strip()) for cidr in TRUSTED_PROXY_CIDRS if cidr.strip()]
        def is_trusted(value):
            address = ipaddress.ip_address(value)
            return any(address in network for network in trusted)
        if not is_trusted(peer):
            return peer
        # Walk from the direct peer toward the client, stopping at the first untrusted hop.
        # Client-supplied prefixes must not override an address appended by the real proxy.
        chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        for address in reversed(chain):
            if not is_trusted(address):
                return address
        return chain[0] if chain else peer
    except ValueError:
        return peer


def client_ipv4(request: Request) -> str:
    value = client_ip(request)
    try:
        return value if ipaddress.ip_address(value).version == 4 else ""
    except ValueError:
        return ""


def _geoip_cache_get(ip: str) -> tuple[str | None, str | None, str | None] | None:
    entry = _geoip_cache.get(ip)
    if not entry:
        return None
    ts, value = entry
    if (time.time() - ts) > GEOIP_CACHE_TTL:
        _geoip_cache.pop(ip, None)
        return None
    return value


def _geoip_cache_set(ip: str, value: tuple[str | None, str | None, str | None]) -> None:
    _geoip_cache[ip] = (time.time(), value)


def _geoip_api_lookup(ip: str) -> tuple[str | None, str | None, str | None]:
    if not GEOIP_API_URL:
        return None, None, None
    cached = _geoip_cache_get(ip)
    if cached is not None:
        return cached
    if "{ip}" in GEOIP_API_URL:
        url = GEOIP_API_URL.replace("{ip}", ip)
    elif GEOIP_API_URL.endswith("/"):
        url = f"{GEOIP_API_URL}{ip}"
    else:
        url = f"{GEOIP_API_URL}/{ip}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShiftPilot/GeoIP"})
        with urllib.request.urlopen(req, timeout=GEOIP_API_TIMEOUT) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(payload) if payload else {}
    except Exception:
        return None, None, None
    city = data.get("city") or data.get("city_name")
    region = (
        data.get("region")
        or data.get("region_name")
        or data.get("state")
        or data.get("subdivision")
        or data.get("subdivision_name")
    )
    country = (
        data.get("country_code")
        or data.get("country")
        or data.get("country_name")
        or data.get("countryCode")
    )
    result = (city or None, region or None, country or None)
    _geoip_cache_set(ip, result)
    return result


def _geoip_location(ip: str) -> tuple[str | None, str | None, str | None]:
    if not ip:
        return None, None, None
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
            return None, None, None
    except ValueError:
        return None, None, None
    return _geoip_api_lookup(ip)


def client_location(request: Request) -> str:
    city, region, country = _geoip_location(client_ip(request))
    return ", ".join(str(value) for value in (city, region, country) if value)


def request_meta(request: Request) -> tuple[str, str, str, str]:
    return (
        client_ip(request),
        client_ipv4(request),
        request.headers.get("user-agent", ""),
        client_location(request),
    )


def rate_limit(key: str, *, limit: int, window_seconds: int):
    async def _guard(request: Request):
        now = time.time()
        bucket_key = f"{key}:{client_ip(request)}"
        bucket = _rate_buckets[bucket_key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests")
        bucket.append(now)

    return _guard


def login_key(request: Request, username: str) -> str:
    return f"{username.lower()}:{client_ip(request)}"


def is_locked_out(key: str) -> bool:
    until = _login_lockouts.get(key)
    if not until:
        return False
    if until <= time.time():
        _login_lockouts.pop(key, None)
        return False
    return True


def record_login_failure(key: str, *, limit: int = 5, window_seconds: int = 900, lockout_seconds: int = 900):
    now = time.time()
    bucket = _login_failures[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    bucket.append(now)
    if len(bucket) >= limit:
        _login_lockouts[key] = now + lockout_seconds


def clear_login_failures(key: str):
    _login_failures.pop(key, None)
    _login_lockouts.pop(key, None)
