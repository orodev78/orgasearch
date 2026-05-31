import re

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

MAX_QUERY_LENGTH = 500
LANG_CODE_RE = re.compile(r"^[a-z]{2,3}$")


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=2, max_length=MAX_QUERY_LENGTH)
    langs: list[str] = Field(default_factory=lambda: ["fr", "en"])
    sources: list[str] | None = None
    limit: int = Field(default=20, ge=1, le=50)
    per_source: int = Field(default=10, ge=1, le=30)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    type: str | None = None
    expand: bool = True
    max_expansions: int = Field(default=12, ge=0, le=50)
    merge: bool = Field(
        default=False,
        description="If true, fuse records sharing cross-source IDs; if false, one row per source",
    )

    @field_validator("q")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()

    @field_validator("langs", mode="before")
    @classmethod
    def parse_langs(cls, v: str | list[str]) -> list[str]:
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

    @field_validator("sources", mode="before")
    @classmethod
    def parse_sources(cls, v: str | list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, str):
            return [s.strip().lower() for s in v.split(",") if s.strip()]
        return [s.lower() for s in v]

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else None
