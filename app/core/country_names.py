"""Resolve ISO 3166-1 alpha-2 codes to display names (static lookup, no extra runtime deps)."""

from __future__ import annotations

import json
from functools import lru_cache

from app.core.config import CONFIG_DIR

_NAMES_PATH = CONFIG_DIR / "country_names.json"


@lru_cache(maxsize=1)
def _iso_names() -> dict[str, str]:
    if not _NAMES_PATH.exists():
        return {}
    with _NAMES_PATH.open(encoding="utf-8") as f:
        return {k.upper(): v for k, v in json.load(f).items()}


@lru_cache(maxsize=256)
def country_name_from_iso_code(code: str) -> str | None:
    return _iso_names().get(code.upper())
