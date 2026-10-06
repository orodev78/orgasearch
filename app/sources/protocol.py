from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx

from app.models.partner import PartnerResult


@dataclass
class SearchContext:
    query: str
    langs: list[str]
    per_source: int
    country: str | None = None
    partner_type: str | None = None
    client: httpx.AsyncClient | None = None
    timeout_seconds: float = 5.0
    openalex_api_key: str = ""
    wikidata_user_agent: str = ""


@dataclass
class SourceConfig:
    enabled: bool = True
    timeout_seconds: float = 5.0
    default_per_source: int = 10
    requires_env: list[str] = field(default_factory=list)
    adapter: str | None = None
    display_name: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None


@runtime_checkable
class PartnerSource(Protocol):
    """Contract for every data source adapter."""

    id: str
    display_name: str

    def supported_lookup_keys(self) -> frozenset[str]: ...

    def enabled(self) -> bool: ...

    async def search(self, ctx: SearchContext) -> list[PartnerResult]: ...

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None: ...
