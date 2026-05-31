from __future__ import annotations

import re

from app.core.sparql import (
    build_property_lookup_query,
    validate_isni_value,
    validate_ror_lookup_value,
)
from app.models.partner import (
    Coordinates,
    CountryInfo,
    PartnerResult,
    PartnerSourceId,
)
from app.services.relevance import rank_to_source_score
from app.sources.protocol import SearchContext
from app.sources.type_mapping import normalize_wikidata_p31

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
QID_RE = re.compile(r"^Q\d+$", re.I)


class WikidataSource:
    id = "wikidata"
    display_name = "Wikidata"

    def supported_lookup_keys(self) -> frozenset[str]:
        return frozenset({"wikidata", "isni", "ror"})

    def enabled(self) -> bool:
        return True

    async def search(self, ctx: SearchContext) -> list[PartnerResult]:
        client = ctx.client
        if client is None:
            return []
        headers = {"User-Agent": ctx.wikidata_user_agent}
        qids: list[str] = []
        seen: set[str] = set()
        langs = ctx.langs if ctx.langs else ["en"]
        limit = min(ctx.per_source, 10)
        for lang in langs[:3]:
            params = {
                "action": "wbsearchentities",
                "search": ctx.query,
                "language": lang,
                "type": "item",
                "limit": limit,
                "format": "json",
            }
            resp = await client.get(
                WIKIDATA_API,
                params=params,
                headers=headers,
                timeout=ctx.timeout_seconds,
            )
            resp.raise_for_status()
            for item in resp.json().get("search") or []:
                qid = item.get("id")
                if qid and qid not in seen:
                    seen.add(qid)
                    qids.append(qid)
                if len(qids) >= limit:
                    break
            if len(qids) >= limit:
                break
        if not qids:
            return []
        return await self._enrich_entities(ctx, qids[:limit], start_rank=0)

    async def lookup(
        self, ctx: SearchContext, key: str, value: str
    ) -> PartnerResult | None:
        client = ctx.client
        if client is None:
            return None
        if key == "wikidata":
            qid = value.upper() if value.upper().startswith("Q") else None
            if not qid or not QID_RE.match(qid):
                return None
            results = await self._enrich_entities(ctx, [qid], start_rank=0)
            return results[0] if results else None
        if key == "isni":
            try:
                normalized = validate_isni_value(value)
            except ValueError:
                return None
            found = await self._lookup_by_property(ctx, "P213", normalized)
            if found:
                return found
            return await self._lookup_by_property(
                ctx, "P213", normalized.replace(" ", "")
            )
        if key == "ror":
            try:
                ror_url = validate_ror_lookup_value(value)
            except ValueError:
                return None
            return await self._lookup_by_property(ctx, "P6782", ror_url)
        return None

    async def _lookup_by_property(
        self, ctx: SearchContext, prop: str, value: str
    ) -> PartnerResult | None:
        client = ctx.client
        if client is None:
            return None
        try:
            query = build_property_lookup_query(prop, value)
        except ValueError:
            return None
        params = {
            "query": query,
            "format": "json",
        }
        headers = {
            "User-Agent": ctx.wikidata_user_agent,
            "Accept": "application/sparql-results+json",
        }
        resp = await client.get(
            "https://query.wikidata.org/sparql",
            params=params,
            headers=headers,
            timeout=ctx.timeout_seconds,
        )
        if resp.status_code != 200:
            return None
        bindings = (
            resp.json().get("results", {}).get("bindings") or []
        )
        if not bindings:
            return None
        uri = bindings[0].get("item", {}).get("value", "")
        qid = uri.rsplit("/", 1)[-1] if uri else ""
        if not qid:
            return None
        results = await self._enrich_entities(ctx, [qid], start_rank=0)
        return results[0] if results else None

    async def _enrich_entities(
        self, ctx: SearchContext, qids: list[str], start_rank: int = 0
    ) -> list[PartnerResult]:
        client = ctx.client
        if client is None or not qids:
            return []
        params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels|claims|sitelinks",
            "languages": "|".join(ctx.langs[:5]) if ctx.langs else "en",
            "format": "json",
        }
        headers = {"User-Agent": ctx.wikidata_user_agent}
        resp = await client.get(
            WIKIDATA_API,
            params=params,
            headers=headers,
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        entities = resp.json().get("entities") or {}
        related = _related_qids_to_fetch(entities, qids)
        if related:
            entities.update(await self._fetch_entities(ctx, related))
        langs = ctx.langs if ctx.langs else ["en"]
        results = []
        for offset, qid in enumerate(qids):
            ent = entities.get(qid)
            if not ent or ent.get("missing"):
                continue
            mapped = self._map_entity(
                qid,
                ent,
                rank=start_rank + offset,
                entities=entities,
                langs=langs,
            )
            if mapped:
                results.append(mapped)
        return results

    async def _fetch_entities(
        self, ctx: SearchContext, ids: list[str]
    ) -> dict[str, dict]:
        client = ctx.client
        if client is None or not ids:
            return {}
        params = {
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "labels|claims",
            "languages": "|".join(ctx.langs[:5]) if ctx.langs else "en",
            "format": "json",
        }
        headers = {"User-Agent": ctx.wikidata_user_agent}
        resp = await client.get(
            WIKIDATA_API,
            params=params,
            headers=headers,
            timeout=ctx.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json().get("entities") or {}

    def _map_entity(
        self,
        qid: str,
        ent: dict,
        rank: int = 0,
        entities: dict[str, dict] | None = None,
        langs: list[str] | None = None,
    ) -> PartnerResult | None:
        labels: dict[str, str] = {}
        for lang, obj in (ent.get("labels") or {}).items():
            labels[lang] = obj.get("value", "")

        claims = ent.get("claims") or {}
        ext: dict[str, str] = {"wikidata": qid}
        website = _claim_url(claims, "P856")
        coords = _claim_coords(claims, "P625")
        country_q = _claim_entity(claims, "P17")
        located_q = _claim_entity(claims, "P131")
        isni = _claim_string(claims, "P213")
        ror = _claim_string(claims, "P6782")
        if isni:
            ext["isni"] = isni
        if ror:
            ext["ror"] = ror if ror.startswith("http") else f"https://ror.org/{ror}"

        p31 = _claim_entity(claims, "P31")
        ptype = normalize_wikidata_p31(p31)

        country = _resolve_country(country_q, entities or {})
        city = _resolve_place_label(
            located_q, entities or {}, langs or ["en"]
        )

        return PartnerResult(
            source=PartnerSourceId.WIKIDATA,
            id=qid,
            external_ids=ext,
            labels=labels,
            type=ptype,
            type_source=p31,
            website=website,
            city=city,
            country=country,
            coordinates=coords,
            score=rank_to_source_score(rank),
            source_url=f"https://www.wikidata.org/wiki/{qid}",
        )


def _related_qids_to_fetch(entities: dict[str, dict], qids: list[str]) -> list[str]:
    """Q-ids for P17 (country) and P131 (located in) not yet in entities."""
    needed: list[str] = []
    seen = set(entities.keys())
    for qid in qids:
        claims = (entities.get(qid) or {}).get("claims") or {}
        for prop in ("P17", "P131"):
            ref = _claim_entity(claims, prop)
            if ref and ref.startswith("Q") and ref not in seen:
                seen.add(ref)
                needed.append(ref)
    return needed


def _resolve_place_label(
    place_q: str | None,
    entities: dict[str, dict],
    langs: list[str],
) -> str | None:
    if not place_q:
        return None
    if not (place_q.startswith("Q") and QID_RE.match(place_q)):
        return place_q.strip() or None
    labels = (entities.get(place_q) or {}).get("labels") or {}
    for lang in langs:
        obj = labels.get(lang)
        if obj and obj.get("value"):
            return obj["value"]
    for fallback in ("en", "fr", "de"):
        obj = labels.get(fallback)
        if obj and obj.get("value"):
            return obj["value"]
    if labels:
        first = next(iter(labels.values()))
        if isinstance(first, dict):
            return first.get("value")
    return None


def _resolve_country(
    country_q: str | None, entities: dict[str, dict]
) -> CountryInfo | None:
    if not country_q:
        return None
    if len(country_q) == 2 and country_q.isalpha():
        return CountryInfo(code=country_q.upper())
    if country_q.startswith("Q") and QID_RE.match(country_q):
        cent = entities.get(country_q) or {}
        code = _claim_string(cent.get("claims") or {}, "P297")
        if code and len(code) == 2:
            name = (cent.get("labels") or {}).get("en", {}).get("value")
            return CountryInfo(code=code.upper(), name=name)
    return None


def _claim_string(claims: dict, prop: str) -> str | None:
    for snak in claims.get(prop) or []:
        dv = snak.get("mainsnak", {}).get("datavalue", {})
        if dv and dv.get("type") == "string":
            return dv.get("value")
    return None


def _claim_url(claims: dict, prop: str) -> str | None:
    return _claim_string(claims, prop)


def _claim_entity(claims: dict, prop: str) -> str | None:
    for snak in claims.get(prop) or []:
        dv = snak.get("mainsnak", {}).get("datavalue", {})
        if dv and dv.get("type") == "wikibase-entityid":
            return dv.get("value", {}).get("id")
    return None


def _claim_coords(claims: dict, prop: str):
    for snak in claims.get(prop) or []:
        dv = snak.get("mainsnak", {}).get("datavalue", {})
        if dv and dv.get("type") == "globecoordinate":
            v = dv.get("value", {})
            lat, lon = v.get("latitude"), v.get("longitude")
            if lat is not None and lon is not None:
                return Coordinates(lat=float(lat), lon=float(lon))
    return None


def get_source() -> WikidataSource:
    return WikidataSource()
