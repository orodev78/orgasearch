from __future__ import annotations

import re
from copy import deepcopy

import yaml

from app.core.config import CONFIG_DIR, get_settings
from app.models.partner import PartnerResult
from app.services.label_resolver import LabelResolver
from app.services.relevance import apply_relevance_scores

ROR_RE = re.compile(r"(?:https?://ror\.org/)?([a-z0-9]{5,12})", re.I)


class ResultMerger:
    def __init__(self) -> None:
        self._priority_keys = self._load_priority_keys()
        self._label_resolver = LabelResolver()

    def finalize_distinct(
        self,
        results: list[PartnerResult],
        langs: list[str],
        limit: int,
        query: str,
        country: str | None = None,
        apply_min_score: bool = True,
    ) -> list[PartnerResult]:
        """Keep one row per (source, id); labels stay source-specific."""
        resolved = self._label_resolver.apply_all(results, langs)
        distinct = self._dedupe_source_id(resolved)
        apply_relevance_scores(distinct, query, country)
        distinct.sort(key=lambda x: x.score or 0.0, reverse=True)
        return self._apply_score_floor(distinct, limit, apply_min_score=apply_min_score)

    def _dedupe_source_id(self, results: list[PartnerResult]) -> list[PartnerResult]:
        seen: set[tuple[str, str]] = set()
        out: list[PartnerResult] = []
        for r in results:
            key = (r.source.value, r.id)
            if key in seen:
                continue
            seen.add(key)
            r.sources = [r.source.value]
            out.append(r)
        return out

    def merge(
        self,
        results: list[PartnerResult],
        langs: list[str],
        limit: int,
        query: str,
        country: str | None = None,
        apply_min_score: bool = True,
    ) -> list[PartnerResult]:
        groups: dict[str, list[PartnerResult]] = {}
        for r in results:
            key = self._dedup_key(r)
            groups.setdefault(key, []).append(r)

        merged: list[PartnerResult] = []
        for group in groups.values():
            merged.append(self._merge_group(group))

        merged = self._label_resolver.apply_all(merged, langs)
        apply_relevance_scores(merged, query, country)
        merged.sort(key=lambda x: x.score or 0.0, reverse=True)
        return self._apply_score_floor(merged, limit, apply_min_score=apply_min_score)

    def _apply_score_floor(
        self,
        results: list[PartnerResult],
        limit: int,
        *,
        apply_min_score: bool = True,
    ) -> list[PartnerResult]:
        if apply_min_score:
            min_score = get_settings().search_min_score
            filtered = [r for r in results if (r.score or 0.0) >= min_score]
        else:
            filtered = results
        return filtered[:limit]

    def _dedup_key(self, r: PartnerResult) -> str:
        ext = r.external_ids or {}
        for key in self._priority_keys:
            val = ext.get(key)
            if val:
                norm = self._normalize_id(key, val)
                if norm:
                    return f"{key}:{norm}"
        return f"{r.source.value}:{r.id}"

    def _normalize_id(self, key: str, value: str) -> str:
        if key == "ror":
            m = ROR_RE.search(value)
            return m.group(1).lower() if m else value.lower()
        if key == "wikidata":
            return value.upper().replace("HTTPS://WWW.WIKIDATA.ORG/WIKI/", "")
        if key == "openalex":
            return value.upper().lstrip("I")
        return value.lower()

    def _merge_group(self, group: list[PartnerResult]) -> PartnerResult:
        base = deepcopy(group[0])
        source_ids = {g.source.value for g in group}
        base.sources = sorted(source_ids)

        all_ext: dict[str, str] = {}
        all_labels: dict[str, str] = {}
        best_score = base.score or 0.0

        for g in group:
            all_ext.update(g.external_ids or {})
            all_labels.update(g.labels or {})
            if g.score and (g.score or 0) > best_score:
                best_score = g.score
            for field in (
                "website",
                "city",
                "country",
                "coordinates",
                "type",
                "type_source",
            ):
                if getattr(g, field) and not getattr(base, field):
                    setattr(base, field, getattr(g, field))

        base.external_ids = all_ext
        base.labels = all_labels
        base.score = best_score if best_score else base.score
        return base

    def _load_priority_keys(self) -> list[str]:
        path = CONFIG_DIR / "dedup_rules.yaml"
        if not path.exists():
            return ["ror", "wikidata", "openalex", "hal", "isni"]
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return list(data.get("priority_keys") or [])
