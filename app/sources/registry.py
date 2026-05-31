from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from app.core.config import CONFIG_DIR, get_settings
from app.sources.protocol import PartnerSource, SourceConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

BUILTIN_SOURCES = ("ror", "wikidata", "hal", "openalex")


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, PartnerSource] = {}
        self._config: dict[str, SourceConfig] = {}

    def load(self) -> None:
        self._config = _load_sources_yaml()
        self._sources.clear()
        for source_id in BUILTIN_SOURCES:
            try:
                module = importlib.import_module(f"app.sources.{source_id}")
                source: PartnerSource = module.get_source()
                self._sources[source_id] = source
            except Exception:
                logger.exception("Failed to load source %s", source_id)

    def get(self, source_id: str) -> PartnerSource | None:
        return self._sources.get(source_id)

    def all(self) -> list[PartnerSource]:
        return list(self._sources.values())

    def config(self, source_id: str) -> SourceConfig:
        return self._config.get(source_id, SourceConfig())

    def valid_ids(self) -> list[str]:
        return sorted(self._sources.keys())

    def is_available(self, source_id: str) -> bool:
        source = self._sources.get(source_id)
        if source is None:
            return False
        cfg = self._config.get(source_id, SourceConfig())
        if not cfg.enabled:
            return False
        if not source.enabled():
            return False
        for env_key in cfg.requires_env:
            if not _env_present(env_key):
                return False
        return True

    def active(self, requested: list[str] | None = None) -> list[PartnerSource]:
        if requested:
            unknown = [s for s in requested if s not in self._sources]
            if unknown:
                raise ValueError(
                    f"Unknown sources: {', '.join(unknown)}. "
                    f"Valid: {', '.join(self.valid_ids())}"
                )
            ids = requested
        else:
            ids = self.valid_ids()
        return [
            self._sources[sid]
            for sid in ids
            if sid in self._sources and self.is_available(sid)
        ]

    def list_sources(self) -> list[dict]:
        items = []
        for sid in self.valid_ids():
            source = self._sources[sid]
            cfg = self._config.get(sid, SourceConfig())
            requires = [
                k
                for k in cfg.requires_env
                if not _env_present(k)
            ]
            items.append(
                {
                    "id": sid,
                    "display_name": source.display_name,
                    "enabled": cfg.enabled and source.enabled() and not requires,
                    "requires_config": requires,
                    "timeout_seconds": cfg.timeout_seconds,
                    "default_per_source": cfg.default_per_source,
                }
            )
        return items


_registry: SourceRegistry | None = None


def get_registry() -> SourceRegistry:
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
        _registry.load()
    return _registry


def _load_sources_yaml() -> dict[str, SourceConfig]:
    path = CONFIG_DIR / "sources.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    result: dict[str, SourceConfig] = {}
    for sid, raw in (data.get("sources") or {}).items():
        result[sid] = SourceConfig(
            enabled=raw.get("enabled", True),
            timeout_seconds=float(raw.get("timeout_seconds", 5)),
            default_per_source=int(raw.get("default_per_source", 10)),
            requires_env=list(raw.get("requires_env") or []),
        )
    return result


def _env_present(key: str) -> bool:
    settings = get_settings()
    mapping = {
        "OPENALEX_API_KEY": settings.openalex_api_key,
        "WIKIDATA_USER_AGENT": settings.wikidata_user_agent,
    }
    val = mapping.get(key)
    if val is not None:
        return bool(val.strip())
    import os

    return bool(os.environ.get(key, "").strip())
