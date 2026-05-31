from __future__ import annotations

import re
import unicodedata

from app.core.country_names import country_name_from_iso_code
from app.models.partner import CountryInfo, PartnerResult, PartnerSourceId
from app.services.relevance import rank_to_source_score
from app.sources.protocol import SearchContext
from app.sources.type_mapping import normalize_hal_type

HAL_API = "https://api.archives-ouvertes.fr/ref/structure/"


class HalSource:
    id = "hal"
    display_name = "HAL Structures"

    def supported_lookup_keys(self) -> frozenset[str]:
        return frozenset({"hal"})

    def enabled(self) -> bool:
        return True

    async def search(self, ctx: SearchContext) -> list[PartnerResult]:
        client = ctx.client
        if client is None:
            return []
        params = {
            "q": _build_hal_query(ctx.query),
            "rows": min(ctx.per_source, 30),
            "fl": "docid,label_s,name_s,acronym_s,type_s,country_s,address_s,url_s,code_s",
            "wt": "json",
        }
        resp = await client.get(
            HAL_API,
            params=params,
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("response", {}).get("docs") or []
        return [
            self._map_doc(doc, rank=idx) for idx, doc in enumerate(docs)
        ]

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None:
        if key != "hal":
            return None
        client = ctx.client
        if client is None:
            return None
        params = {
            "q": f"docid:{value}",
            "rows": 1,
            "fl": "docid,label_s,name_s,acronym_s,type_s,country_s,address_s,url_s,code_s",
            "wt": "json",
        }
        resp = await client.get(HAL_API, params=params, timeout=ctx.timeout_seconds)
        if resp.status_code != 200:
            return None
        docs = resp.json().get("response", {}).get("docs") or []
        if not docs:
            return None
        return self._map_doc(docs[0], rank=0)

    def _map_doc(self, doc: dict, rank: int = 0) -> PartnerResult:
        docid = str(doc.get("docid", ""))
        name = _first(doc.get("name_s")) or _first(doc.get("label_s")) or ""
        label = _first(doc.get("label_s")) or name
        type_raw = _first(doc.get("type_s"))
        country_s = _first(doc.get("country_s"))
        address = _first(doc.get("address_s"))
        url = _first(doc.get("url_s"))

        labels: dict[str, str] = {}
        if label:
            labels["fr"] = label
        if name and name != label:
            labels.setdefault("fr", name)

        city = _parse_city(address)
        country = _map_hal_country(country_s) if country_s else None

        ext = {"hal": docid}
        code_s = _first(doc.get("code_s"))
        if code_s:
            ext["hal_code"] = code_s

        return PartnerResult(
            source=PartnerSourceId.HAL,
            id=docid,
            external_ids=ext,
            labels=labels,
            type=normalize_hal_type(type_raw),
            type_source=type_raw,
            website=url,
            city=city,
            country=country,
            score=rank_to_source_score(rank),
            source_url=f"https://aurehal.archives-ouvertes.fr/structure/{docid}",
        )


def _map_hal_country(country_s: str) -> CountryInfo:
    raw = country_s.strip()
    if len(raw) == 2 and raw.isalpha():
        code = raw.upper()
        return CountryInfo(code=code, name=country_name_from_iso_code(code))
    code = raw.upper()[:2]
    return CountryInfo(code=code, name=raw)


def _build_hal_query(query: str) -> str:
    """HAL Solr: phrase match with accents often returns 0; token AND works better."""
    normalized = unicodedata.normalize("NFD", query)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    terms = [t for t in re.findall(r"\w+", stripped, flags=re.UNICODE) if len(t) >= 2]
    if len(terms) >= 2:
        return " AND ".join(terms)
    if terms:
        return terms[0]
    return stripped.strip() or query


def _first(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        return str(val[0]) if val else None
    return str(val)


def _parse_city(address: str | None) -> str | None:
    if not address:
        return None
    parts = re.split(r"[,;]", address)
    if len(parts) >= 2:
        return parts[-2].strip() or None
    return None


def get_source() -> HalSource:
    return HalSource()
