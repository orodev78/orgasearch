import re

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.models.search import LANG_CODE_RE

VALID_LOOKUP_SOURCES = frozenset({"ror", "wikidata", "hal", "openalex"})


def parse_langs(v: str | list[str]) -> list[str]:
    if isinstance(v, str):
        parsed = [lang.strip().lower() for lang in v.split(",") if lang.strip()]
    else:
        parsed = [lang.lower() for lang in v]
    max_langs = get_settings().search_max_langs
    if len(parsed) > max_langs:
        raise ValueError(f"At most {max_langs} languages allowed in langs")
    for lang in parsed:
        if not LANG_CODE_RE.match(lang):
            raise ValueError(f"Invalid language code: {lang!r}")
    return parsed


class LookupQuery(BaseModel):
    source: str
    partner_id: str = Field(..., min_length=1, max_length=200)
    langs: list[str] = Field(default_factory=lambda: ["fr", "en"])
    expand: bool = False
    merge: bool = False
    max_expansions: int = Field(default=12, ge=0, le=50)
    limit: int = Field(default=30, ge=1, le=50)

    @field_validator("source")
    @classmethod
    def normalize_source(cls, v: str) -> str:
        sid = v.strip().lower()
        if sid not in VALID_LOOKUP_SOURCES:
            raise ValueError(
                f"Unknown source: {sid!r}. Valid: {', '.join(sorted(VALID_LOOKUP_SOURCES))}"
            )
        return sid

    @field_validator("partner_id")
    @classmethod
    def strip_partner_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("langs", mode="before")
    @classmethod
    def validate_langs(cls, v: str | list[str]) -> list[str]:
        return parse_langs(v)


def native_lookup_key(source_id: str) -> str:
    """External-id key used for direct lookup on a source adapter."""
    return source_id
