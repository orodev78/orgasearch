"""Shared SlowAPI limiter: global default + per-route overrides."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_global],
    )


limiter = _limiter()


def search_rate_limit() -> str:
    return get_settings().rate_limit_search


def read_rate_limit() -> str:
    return get_settings().rate_limit_read
