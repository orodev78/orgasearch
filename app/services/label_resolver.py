from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import CONFIG_DIR
from app.models.partner import PartnerResult


@lru_cache
def _country_languages() -> dict[str, str]:
    path = CONFIG_DIR / "country_languages.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {k.upper(): v for k, v in json.load(f).items()}


class LabelResolver:
    """Resolve label_country_locale from country and requested langs."""

    def apply(self, result: PartnerResult, langs: list[str]) -> PartnerResult:
        country_code = None
        if result.country and result.country.code:
            country_code = result.country.code.upper()

        locale = _country_languages().get(country_code, "en") if country_code else "en"
        result.country_locale = locale

        label = _pick_label(result.labels, locale)
        if not label:
            for lang in langs:
                label = _pick_label(result.labels, lang)
                if label:
                    break
        if not label:
            for fallback in (locale, "en", "fr", "de"):
                label = _pick_label(result.labels, fallback)
                if label:
                    break
        if not label and result.labels:
            label = next(iter(result.labels.values()))

        result.label_country_locale = label
        return result

    def apply_all(
        self, results: list[PartnerResult], langs: list[str]
    ) -> list[PartnerResult]:
        return [self.apply(r, langs) for r in results]


def _pick_label(labels: dict[str, str], lang: str) -> str | None:
    value = labels.get(lang)
    if value and value.strip():
        return value
    return None
