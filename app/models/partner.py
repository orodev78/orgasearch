from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PartnerSourceId(StrEnum):
    ROR = "ror"
    WIKIDATA = "wikidata"
    HAL = "hal"
    OPENALEX = "openalex"


class PartnerType(StrEnum):
    EDUCATION = "education"
    COMPANY = "company"
    NONPROFIT = "nonprofit"
    GOVERNMENT = "government"
    HEALTHCARE = "healthcare"
    RESEARCH = "research"
    OTHER = "other"


class CountryInfo(BaseModel):
    code: str
    name: str | None = None


class Coordinates(BaseModel):
    lat: float
    lon: float


class PartnerResult(BaseModel):
    """Unified partner record (JSON contract v1)."""

    source: PartnerSourceId
    id: str
    external_ids: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str] = Field(default_factory=dict)
    label_country_locale: str | None = None
    country_locale: str | None = None
    type: PartnerType | None = None
    type_source: str | None = None
    website: str | None = None
    city: str | None = None
    country: CountryInfo | None = None
    coordinates: Coordinates | None = None
    score: float | None = None
    source_url: str | None = None
    sources: list[str] | None = None

    model_config = {"extra": "ignore"}


class ChildQuery(BaseModel):
    source: str
    phase: str
    status: str
    duration_ms: int
    trigger: dict[str, str] | None = None
    error: str | None = None


class PartialError(BaseModel):
    source: str
    phase: str
    message: str


class SearchMeta(BaseModel):
    meta_query: bool = True
    query: str
    langs: list[str]
    sources_queried: list[str]
    counts_by_source: dict[str, int]
    duration_ms: int
    child_queries: list[ChildQuery] = Field(default_factory=list)
    partial_errors: list[PartialError] = Field(default_factory=list)
    expand: bool = True
    merge: bool = False
    cache_hit: bool = False


class SearchResponse(BaseModel):
    results: list[PartnerResult]
    meta: SearchMeta


class SourceInfo(BaseModel):
    id: str
    display_name: str
    enabled: bool
    requires_config: list[str] = Field(default_factory=list)
    timeout_seconds: float | None = None
    default_per_source: int | None = None


class SourcesListResponse(BaseModel):
    sources: list[SourceInfo]


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    sources_loaded: int


class ErrorDetail(BaseModel):
    detail: str
    valid_sources: list[str] | None = None


def partner_result_json_schema() -> dict[str, Any]:
    return PartnerResult.model_json_schema()
