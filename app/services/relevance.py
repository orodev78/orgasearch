"""Local relevance scoring for ranking merged search results."""

from __future__ import annotations

import re
import unicodedata

from app.models.partner import PartnerResult

STOPWORDS = frozenset(
    {
        "of",
        "the",
        "and",
        "de",
        "la",
        "le",
        "les",
        "du",
        "des",
        "et",
        "in",
        "at",
        "for",
        "a",
        "an",
    }
)
MIN_TOKEN_LEN = 3


def rank_to_source_score(rank: int) -> float:
    """Decay score from source API result position (0 = best)."""
    return max(0.15, 1.0 - rank * 0.06)


def apply_relevance_scores(
    results: list[PartnerResult],
    query: str,
    country: str | None = None,
) -> None:
    """Mutates results in place, setting combined relevance on `score`."""
    tokens = _query_tokens(query)
    norm_query = _normalize(query)
    country_upper = country.upper() if country else None

    for result in results:
        text = _text_relevance(result, tokens, norm_query)
        base = result.score or 0.0
        country_bonus = 0.0
        if country_upper and result.country and result.country.code == country_upper:
            country_bonus = 0.2
        combined = min(1.0, 0.35 * base + 0.55 * text + country_bonus)
        result.score = round(combined, 4)


def _query_tokens(query: str) -> list[str]:
    normalized = _normalize(query)
    tokens = [
        t
        for t in re.findall(r"\w+", normalized, flags=re.UNICODE)
        if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS
    ]
    if not tokens:
        tokens = [t for t in re.findall(r"\w+", normalized, flags=re.UNICODE) if t]
    return tokens


def _text_relevance(
    result: PartnerResult, tokens: list[str], norm_query: str
) -> float:
    if not tokens:
        return 0.0
    blob = _result_text_blob(result)
    if not blob:
        return 0.0
    if norm_query and norm_query in blob:
        return 1.0
    matched = sum(1 for t in tokens if t in blob)
    ratio = matched / len(tokens)
    if matched >= 2 and ratio >= 0.5:
        return min(1.0, 0.5 + ratio * 0.5)
    return ratio * 0.7


def _result_text_blob(result: PartnerResult) -> str:
    parts: list[str] = []
    for label in (result.labels or {}).values():
        parts.append(label)
    if result.label_country_locale:
        parts.append(result.label_country_locale)
    if result.city:
        parts.append(result.city)
    return _normalize(" ".join(parts))


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()
