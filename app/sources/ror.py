from __future__ import annotations

import re

import httpx

from app.models.partner import (
    Coordinates,
    CountryInfo,
    PartnerResult,
    PartnerSourceId,
)
from app.services.relevance import rank_to_source_score
from app.sources.protocol import SearchContext
from app.sources.type_mapping import normalize_ror_type

ROR_API = "https://api.ror.org/v2/organizations"
ROR_ID_RE = re.compile(r"(?:https?://ror\.org/)?([a-z0-9]{5,12})", re.I)


class RorSource:
    id = "ror"
    display_name = "ROR"

    def supported_lookup_keys(self) -> frozenset[str]:
        return frozenset({"ror"})

    def enabled(self) -> bool:
        return True

    async def search(self, ctx: SearchContext) -> list[PartnerResult]:
        client = ctx.client
        if client is None:
            return []
        params: dict[str, str | int] = {
            "query": ctx.query,
            "page": 1,
        }
        if ctx.country:
            params["filter"] = f"country.country_code:{ctx.country}"
        resp = await client.get(
            ROR_API,
            params=params,
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") or []
        return [
            self._map_item(item, rank=idx)
            for idx, item in enumerate(items[: ctx.per_source])
        ]

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None:
        if key != "ror":
            return None
        ror_id = _normalize_ror_id(value)
        if not ror_id:
            return None
        client = ctx.client
        if client is None:
            return None
        url = f"https://api.ror.org/v2/organizations/{ror_id}"
        resp = await client.get(url, timeout=ctx.timeout_seconds)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._map_item(resp.json(), rank=0)

    def _map_item(self, item: dict, rank: int = 0) -> PartnerResult:
        ror_id = _normalize_ror_id(item.get("id", "")) or item.get("id", "")
        labels: dict[str, str] = {}
        for name in item.get("names") or []:
            lang = (name.get("lang") or "und").lower()
            value = name.get("value")
            if value and lang not in labels:
                labels[lang] = value
        if not labels and item.get("name"):
            labels["en"] = item["name"]

        ext: dict[str, str] = {}
        for ext_id in item.get("external_ids") or []:
            if not isinstance(ext_id, dict):
                continue
            key = (ext_id.get("type") or "").lower()
            if not key:
                continue
            value = ext_id.get("preferred")
            if not value:
                all_vals = ext_id.get("all") or []
                value = all_vals[0] if all_vals else None
            if value:
                if key == "wikidata" and not str(value).upper().startswith("Q"):
                    value = f"Q{value}" if str(value).isdigit() else value
                ext[key] = str(value)
        ext["ror"] = f"https://ror.org/{ror_id}"

        types = item.get("types") or []
        raw_type = types[0] if types else None
        ptype = normalize_ror_type(raw_type)

        website = None
        for link in item.get("links") or []:
            if link.get("type") == "website":
                website = link.get("value")
                break

        city = None
        country = None
        coords = None
        locations = item.get("locations") or []
        if locations:
            loc = locations[0]
            geo = loc.get("geonames_details") or {}
            city = geo.get("name") or loc.get("name")
            cc = geo.get("country_code") or geo.get("country_iso")
            cname = geo.get("country_name")
            if cc:
                country = CountryInfo(code=cc.upper(), name=cname)
            geo = loc.get("geonames_details") or {}
            lat = loc.get("lat") or geo.get("lat")
            lon = loc.get("lon") or loc.get("lng") or geo.get("lon") or geo.get("lng")
            if lat is not None and lon is not None:
                coords = Coordinates(lat=float(lat), lon=float(lon))

        return PartnerResult(
            source=PartnerSourceId.ROR,
            id=ror_id,
            external_ids=ext,
            labels=labels,
            type=ptype,
            type_source=raw_type,
            website=website,
            city=city,
            country=country,
            coordinates=coords,
            score=rank_to_source_score(rank),
            source_url=f"https://ror.org/{ror_id}",
        )


def _normalize_ror_id(value: str) -> str | None:
    m = ROR_ID_RE.search(value.strip())
    return m.group(1).lower() if m else None


def get_source() -> RorSource:
    return RorSource()
