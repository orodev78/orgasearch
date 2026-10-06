from __future__ import annotations

import os

from app.models.partner import (
    Coordinates,
    CountryInfo,
    PartnerResult,
    PartnerType,
)
from app.services.relevance import rank_to_source_score
from app.sources.protocol import SearchContext, SourceConfig


class LabriSource:
    """Reusable adapter for one LaBRRI API instance."""

    def __init__(
        self,
        id: str,
        display_name: str,
        base_url: str,
        api_key: str,
    ) -> None:
        self.id = id
        self.display_name = display_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def supported_lookup_keys(self) -> frozenset[str]:
        return frozenset({self.id})

    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def search(self, ctx: SearchContext) -> list[PartnerResult]:
        client = ctx.client
        if client is None or not self.enabled():
            return []
        params: dict[str, str | int] = {
            "q": ctx.query,
            "limit": min(ctx.per_source, 30),
        }
        if ctx.country:
            params["country"] = ctx.country
        resp = await client.get(
            f"{self.base_url}/partners/search",
            params=params,
            headers=self._headers(),
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        results = payload.get("results") or []
        return [
            self._map_item(item, rank=idx) for idx, item in enumerate(results)
        ]

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None:
        if key != self.id:
            return None
        client = ctx.client
        if client is None or not self.enabled():
            return None
        partner_id = value.strip()
        if not partner_id:
            return None
        resp = await client.get(
            f"{self.base_url}/partners/{partner_id}",
            headers=self._headers(),
            timeout=ctx.timeout_seconds,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._map_item(resp.json() or {}, rank=0)

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key}

    def _map_item(self, item: dict, rank: int = 0) -> PartnerResult:
        partner_id = str(item.get("id") or "")
        ext = {
            str(k): str(v)
            for k, v in (item.get("external_ids") or {}).items()
            if v is not None and str(v).strip()
        }
        if partner_id:
            ext[self.id] = partner_id

        labels = {
            str(k): str(v)
            for k, v in (item.get("labels") or {}).items()
            if v is not None and str(v).strip()
        }

        raw_type = item.get("type")
        ptype: PartnerType | None = None
        if isinstance(raw_type, str) and raw_type.strip():
            try:
                ptype = PartnerType(raw_type.strip().lower())
            except ValueError:
                ptype = PartnerType.OTHER

        country = None
        country_raw = item.get("country")
        if isinstance(country_raw, dict) and country_raw.get("code"):
            country = CountryInfo(
                code=str(country_raw["code"]).upper(),
                name=country_raw.get("name"),
            )

        coords = None
        coords_raw = item.get("coordinates")
        if isinstance(coords_raw, dict):
            lat, lon = coords_raw.get("lat"), coords_raw.get("lon")
            if lat is not None and lon is not None:
                coords = Coordinates(lat=float(lat), lon=float(lon))

        return PartnerResult(
            source=self.id,
            id=partner_id,
            external_ids=ext,
            labels=labels,
            type=ptype,
            type_source=item.get("type_source"),
            website=item.get("website"),
            city=item.get("city"),
            country=country,
            coordinates=coords,
            score=rank_to_source_score(rank),
            source_url=item.get("source_url"),
        )


def build_labri_sources(configs: dict[str, SourceConfig]) -> list[LabriSource]:
    """Instantiate one LabriSource per YAML entry with adapter: labri."""
    sources: list[LabriSource] = []
    for source_id, cfg in configs.items():
        if cfg.adapter != "labri":
            continue
        base_url = ""
        api_key = ""
        if cfg.base_url_env:
            base_url = os.environ.get(cfg.base_url_env, "").strip()
        if cfg.api_key_env:
            api_key = os.environ.get(cfg.api_key_env, "").strip()
        sources.append(
            LabriSource(
                id=source_id,
                display_name=cfg.display_name or source_id,
                base_url=base_url,
                api_key=api_key,
            )
        )
    return sources
