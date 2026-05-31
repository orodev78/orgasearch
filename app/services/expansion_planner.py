from __future__ import annotations

from dataclasses import dataclass

import yaml

from app.core.config import CONFIG_DIR
from app.models.partner import PartnerResult
from app.sources.registry import SourceRegistry

ROR_PREFIX = "https://ror.org/"


@dataclass(frozen=True)
class ExpansionJob:
    target_source: str
    id_key: str
    id_value: str


class ExpansionPlanner:
    def __init__(self) -> None:
        self._config = _load_expansion_config()

    def plan(
        self,
        phase1_results: list[PartnerResult],
        registry: SourceRegistry,
        requested_sources: list[str] | None,
        max_expansions: int,
        expand_enabled: bool,
    ) -> list[ExpansionJob]:
        if not expand_enabled or not self._config.get("enabled", True):
            return []

        max_lookups = min(
            max_expansions,
            int(self._config.get("max_lookups_per_request", 24)),
        )
        max_per_key = int(self._config.get("max_ids_per_key", 8))
        rules = self._config.get("rules") or []

        satisfied = _satisfied_lookups(phase1_results)
        collected: dict[str, set[str]] = {}

        for result in phase1_results:
            for key, value in (result.external_ids or {}).items():
                if not value:
                    continue
                norm = _normalize_value(key, value)
                collected.setdefault(key, set()).add(norm)

        jobs: list[ExpansionJob] = []
        active_ids = {s.id for s in registry.active(requested_sources)}

        for rule in rules:
            id_key = rule.get("id_key")
            if not id_key:
                continue
            values = list(collected.get(id_key, set()))[:max_per_key]
            for val in values:
                if id_key == "ror" and _ror_has_wikidata(phase1_results, val):
                    continue
                for target in rule.get("resolve_on_sources") or []:
                    if target not in active_ids:
                        continue
                    source = registry.get(target)
                    if source is None:
                        continue
                    if id_key not in source.supported_lookup_keys():
                        continue
                    if (target, id_key, val) in satisfied:
                        continue
                    job = ExpansionJob(
                        target_source=target,
                        id_key=id_key,
                        id_value=val,
                    )
                    if job not in jobs:
                        jobs.append(job)
                    if len(jobs) >= max_lookups:
                        return jobs
        return jobs


def _satisfied_lookups(results: list[PartnerResult]) -> set[tuple[str, str, str]]:
    """(target_source, id_key, normalized_value) already present in results."""
    out: set[tuple[str, str, str]] = set()
    for r in results:
        src = r.source.value
        for key, value in (r.external_ids or {}).items():
            out.add((src, key, _normalize_value(key, value)))
        out.add((src, src, r.id.lower()))
    return out


def _ror_has_wikidata(results: list[PartnerResult], ror_val: str) -> bool:
    norm_ror = _normalize_value("ror", ror_val)
    for r in results:
        ext = r.external_ids or {}
        ror_ext = ext.get("ror")
        if not ror_ext:
            continue
        if _normalize_value("ror", ror_ext) == norm_ror and ext.get("wikidata"):
            return True
    return False


def _normalize_value(key: str, value: str) -> str:
    if key == "ror":
        v = value.replace(ROR_PREFIX, "").strip("/")
        return v.lower()
    if key == "wikidata":
        return value.upper().replace("HTTPS://WWW.WIKIDATA.ORG/WIKI/", "")
    if key == "openalex":
        return value.upper().lstrip("I")
    return value.strip().lower()


def _load_expansion_config() -> dict:
    path = CONFIG_DIR / "id_expansion.yaml"
    if not path.exists():
        return {"enabled": True, "max_lookups_per_request": 24, "rules": []}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("expansion") or data
