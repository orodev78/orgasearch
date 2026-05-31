from __future__ import annotations

import re

from app.models.partner import (
    Coordinates,
    CountryInfo,
    PartnerResult,
    PartnerSourceId,
)
from app.core.config import get_settings
from app.services.relevance import rank_to_source_score
from app.sources.protocol import SearchContext
from app.sources.type_mapping import normalize_openalex_type

OPENALEX_API = "https://api.openalex.org/institutions"
OA_ID_RE = re.compile(r"^I?(\d+)$", re.I)


class OpenAlexSource:
    id = "openalex"
    display_name = "OpenAlex"

    def supported_lookup_keys(self) -> frozenset[str]:
        return frozenset({"openalex", "ror"})

    def enabled(self) -> bool:
        return bool(get_settings().openalex_api_key.strip())

    async def search(self, ctx: SearchContext) -> list[PartnerResult]:
        client = ctx.client
        if client is None or not ctx.openalex_api_key:
            return []
        params: dict[str, str | int] = {
            "search": ctx.query,
            "per_page": min(ctx.per_source, 25),
            "api_key": ctx.openalex_api_key,
        }
        if ctx.country:
            params["filter"] = f"country_code:{ctx.country}"
        resp = await client.get(
            OPENALEX_API,
            params=params,
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        return [
            self._map_item(r, rank=idx) for idx, r in enumerate(results)
        ]

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None:
        client = ctx.client
        if client is None or not ctx.openalex_api_key:
            return None
        if key == "openalex":
            oa_id = _normalize_oa_id(value)
            if not oa_id:
                return None
            url = f"{OPENALEX_API}/I{oa_id}"
            params = {"api_key": ctx.openalex_api_key}
            resp = await client.get(url, params=params, timeout=ctx.timeout_seconds)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return self._map_item(resp.json(), rank=0)
        if key == "ror":
            ror_url = value if value.startswith("http") else f"https://ror.org/{value}"
            url = f"{OPENALEX_API}/{ror_url}"
            params = {"api_key": ctx.openalex_api_key}
            resp = await client.get(url, params=params, timeout=ctx.timeout_seconds)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return self._map_item(resp.json(), rank=0)
        return None

    def _map_item(self, item: dict, rank: int = 0) -> PartnerResult:
        raw_id = item.get("id", "")
        oa_id = raw_id.rsplit("/", 1)[-1].replace("I", "") if raw_id else ""
        oa_id = _normalize_oa_id(oa_id) or oa_id

        display = item.get("display_name") or ""
        labels = {"en": display} if display else {}

        ids_block = item.get("ids") or {}
        ext: dict[str, str] = {}
        if oa_id:
            ext["openalex"] = f"I{oa_id}"
        ror = ids_block.get("ror")
        if ror:
            ext["ror"] = ror
        wd = ids_block.get("wikidata")
        if wd:
            ext["wikidata"] = wd.replace("https://www.wikidata.org/wiki/", "")

        geo = item.get("geo") or {}
        city = geo.get("city")
        cc = geo.get("country_code")
        country = CountryInfo(code=cc.upper(), name=None) if cc else None
        coords = None
        lat, lon = geo.get("latitude"), geo.get("longitude")
        if lat is not None and lon is not None:
            coords = Coordinates(lat=float(lat), lon=float(lon))

        raw_type = item.get("type")
        ptype = normalize_openalex_type(raw_type)

        return PartnerResult(
            source=PartnerSourceId.OPENALEX,
            id=oa_id or raw_id,
            external_ids=ext,
            labels=labels,
            type=ptype,
            type_source=raw_type,
            website=item.get("homepage_url"),
            city=city,
            country=country,
            coordinates=coords,
            score=rank_to_source_score(rank),
            source_url=f"https://openalex.org/I{oa_id}" if oa_id else raw_id,
        )


def _normalize_oa_id(value: str) -> str | None:
    value = value.strip()
    if value.startswith("https://openalex.org/"):
        value = value.rsplit("/", 1)[-1]
    m = OA_ID_RE.match(value.replace("I", ""))
    return m.group(1) if m else None


def get_source() -> OpenAlexSource:
    return OpenAlexSource()
