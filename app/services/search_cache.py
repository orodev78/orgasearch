from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from cachetools import TTLCache

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_memory_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=512, ttl=3600)
_redis_client = None


async def get_cached_search(cache_key: str) -> dict[str, Any] | None:
    settings = get_settings()
    if settings.cache_url:
        try:
            client = await _get_redis()
            raw = await client.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception:
            logger.warning("Redis cache read failed", exc_info=True)
    return _memory_cache.get(cache_key)


async def set_cached_search(cache_key: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if settings.cache_url:
        try:
            client = await _get_redis()
            await client.setex(cache_key, 3600, json.dumps(payload, default=str))
            return
        except Exception:
            logger.warning("Redis cache write failed", exc_info=True)
    _memory_cache[cache_key] = payload


def build_cache_key(
    q: str,
    langs: list[str],
    sources: list[str] | None,
    country: str | None,
    partner_type: str | None,
    expand: bool,
    merge: bool,
    limit: int,
    per_source: int,
) -> str:
    parts = {
        "q": q.lower().strip(),
        "langs": ",".join(sorted(langs)),
        "sources": ",".join(sorted(sources)) if sources else "*",
        "country": country or "",
        "type": partner_type or "",
        "expand": expand,
        "merge": merge,
        "limit": limit,
        "per_source": per_source,
    }
    digest = hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode()
    ).hexdigest()[:16]
    return f"search:{digest}"


def build_lookup_cache_key(
    source: str,
    partner_id: str,
    langs: list[str],
    expand: bool,
    merge: bool,
    limit: int,
    max_expansions: int,
) -> str:
    parts = {
        "source": source.lower().strip(),
        "id": partner_id.strip(),
        "langs": ",".join(sorted(langs)),
        "expand": expand,
        "merge": merge,
        "limit": limit,
        "max_expansions": max_expansions,
    }
    digest = hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode()
    ).hexdigest()[:16]
    return f"lookup:{digest}"


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis

        settings = get_settings()
        _redis_client = redis.from_url(settings.cache_url, decode_responses=True)
    return _redis_client
