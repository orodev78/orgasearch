from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import get_settings
from app.core.http import get_http_client
from app.models.partner import (
    ChildQuery,
    PartialError,
    PartnerResult,
    SearchMeta,
    SearchResponse,
)
from app.models.lookup import LookupQuery, native_lookup_key
from app.models.search import SearchQuery
from app.services.expansion_planner import ExpansionJob, ExpansionPlanner
from app.services.result_merger import ResultMerger
from app.services.search_cache import (
    build_cache_key,
    build_lookup_cache_key,
    get_cached_search,
    set_cached_search,
)
from app.sources.protocol import PartnerSource, SearchContext
from app.sources.registry import SourceRegistry, get_registry

merger = ResultMerger()
planner = ExpansionPlanner()


class PartnerNotFoundError(ValueError):
    """No record for the given source and native id."""


class SearchOrchestrator:
    def __init__(self, registry: SourceRegistry | None = None) -> None:
        self.registry = registry or get_registry()

    async def search(self, query: SearchQuery) -> SearchResponse:
        settings = get_settings()
        cache_key = build_cache_key(
            query.q,
            query.langs,
            query.sources,
            query.country,
            query.type,
            query.expand,
            query.merge,
            query.limit,
            query.per_source,
        )
        cached = await get_cached_search(cache_key)
        if cached:
            resp = SearchResponse.model_validate(cached)
            resp.meta.cache_hit = True
            return resp

        started = time.perf_counter()
        client = await get_http_client()
        active = self.registry.active(query.sources)
        child_queries: list[ChildQuery] = []
        partial_errors: list[PartialError] = []
        phase1_results: list[PartnerResult] = []

        ctx_base = SearchContext(
            query=query.q,
            langs=query.langs,
            per_source=query.per_source or settings.search_per_source_limit,
            country=query.country,
            partner_type=query.type,
            client=client,
            openalex_api_key=settings.openalex_api_key,
            wikidata_user_agent=settings.wikidata_user_agent,
        )

        phase1_results, cq1, pe1 = await self._run_search_phase(active, ctx_base)
        child_queries.extend(cq1)
        partial_errors.extend(pe1)

        phase2_results: list[PartnerResult] = []
        if query.expand:
            jobs = planner.plan(
                phase1_results,
                self.registry,
                query.sources,
                query.max_expansions,
                True,
            )
            phase2_results, cq2, pe2 = await self._run_lookup_phase(jobs, ctx_base)
            child_queries.extend(cq2)
            partial_errors.extend(pe2)

        all_results = phase1_results + phase2_results
        if query.merge:
            final_results = merger.merge(
                all_results,
                query.langs,
                query.limit,
                query.q,
                query.country,
            )
        else:
            final_results = merger.finalize_distinct(
                all_results,
                query.langs,
                query.limit,
                query.q,
                query.country,
            )

        counts: dict[str, int] = {}
        for r in final_results:
            src = r.source.value
            counts[src] = counts.get(src, 0) + 1

        duration_ms = int((time.perf_counter() - started) * 1000)
        meta = SearchMeta(
            query=query.q,
            langs=query.langs,
            sources_queried=[s.id for s in active],
            counts_by_source=counts,
            duration_ms=duration_ms,
            child_queries=child_queries,
            partial_errors=partial_errors,
            expand=query.expand,
            merge=query.merge,
            cache_hit=False,
        )
        response = SearchResponse(results=final_results, meta=meta)
        await set_cached_search(cache_key, response.model_dump(mode="json"))
        return response

    async def lookup_by_id(self, query: LookupQuery) -> SearchResponse:
        settings = get_settings()
        source_id = query.source
        if source_id not in self.registry.valid_ids():
            raise ValueError(
                f"Unknown source: {source_id}. "
                f"Valid: {', '.join(self.registry.valid_ids())}"
            )
        if not self.registry.is_available(source_id):
            raise ValueError(f"Source not available: {source_id}")
        source = self.registry.get(source_id)
        if source is None:
            raise ValueError(f"Source not loaded: {source_id}")

        lookup_key = native_lookup_key(source_id)
        if lookup_key not in source.supported_lookup_keys():
            raise ValueError(
                f"Source {source_id!r} does not support native id lookup"
            )

        cache_key = build_lookup_cache_key(
            source_id,
            query.partner_id,
            query.langs,
            query.expand,
            query.merge,
            query.limit,
            query.max_expansions,
        )
        cached = await get_cached_search(cache_key)
        if cached:
            resp = SearchResponse.model_validate(cached)
            resp.meta.cache_hit = True
            return resp

        started = time.perf_counter()
        client = await get_http_client()
        cfg = self.registry.config(source_id)
        meta_query = f"{source_id}:{query.partner_id}"
        ctx = SearchContext(
            query=meta_query,
            langs=query.langs,
            per_source=1,
            client=client,
            timeout_seconds=cfg.timeout_seconds,
            openalex_api_key=settings.openalex_api_key,
            wikidata_user_agent=settings.wikidata_user_agent,
        )

        child_queries: list[ChildQuery] = []
        partial_errors: list[PartialError] = []
        phase1_results: list[PartnerResult] = []

        t0 = time.perf_counter()
        try:
            primary = await source.lookup(ctx, lookup_key, query.partner_id)
        except Exception as exc:
            partial_errors.append(
                PartialError(source=source_id, phase="lookup", message=str(exc))
            )
            child_queries.append(
                ChildQuery(
                    source=source_id,
                    phase="lookup",
                    status="error",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    trigger={"key": lookup_key, "value": query.partner_id},
                    error=str(exc),
                )
            )
            primary = None
        else:
            status = "ok" if primary else "not_found"
            child_queries.append(
                ChildQuery(
                    source=source_id,
                    phase="lookup",
                    status=status,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    trigger={"key": lookup_key, "value": query.partner_id},
                )
            )

        if primary is None:
            raise PartnerNotFoundError(
                f"No partner found for {source_id}:{query.partner_id}"
            )

        phase1_results = [primary]
        phase2_results: list[PartnerResult] = []
        if query.expand:
            jobs = planner.plan(
                phase1_results,
                self.registry,
                None,
                query.max_expansions,
                True,
            )
            phase2_results, cq2, pe2 = await self._run_lookup_phase(jobs, ctx)
            child_queries.extend(cq2)
            partial_errors.extend(pe2)

        all_results = phase1_results + phase2_results
        relevance_query = _relevance_query_from_results(phase1_results)
        if query.merge:
            final_results = merger.merge(
                all_results,
                query.langs,
                query.limit,
                relevance_query,
                apply_min_score=False,
            )
        else:
            final_results = merger.finalize_distinct(
                all_results,
                query.langs,
                query.limit,
                relevance_query,
                apply_min_score=False,
            )

        counts: dict[str, int] = {}
        for r in final_results:
            src = r.source.value
            counts[src] = counts.get(src, 0) + 1

        sources_queried = sorted({source_id, *(r.source.value for r in final_results)})
        duration_ms = int((time.perf_counter() - started) * 1000)
        meta = SearchMeta(
            meta_query=False,
            query=meta_query,
            langs=query.langs,
            sources_queried=sources_queried,
            counts_by_source=counts,
            duration_ms=duration_ms,
            child_queries=child_queries,
            partial_errors=partial_errors,
            expand=query.expand,
            merge=query.merge,
            cache_hit=False,
        )
        response = SearchResponse(results=final_results, meta=meta)
        await set_cached_search(cache_key, response.model_dump(mode="json"))
        return response

    async def _run_search_phase(
        self,
        sources: list[PartnerSource],
        ctx: SearchContext,
    ) -> tuple[list[PartnerResult], list[ChildQuery], list[PartialError]]:
        tasks = []
        for source in sources:
            cfg = self.registry.config(source.id)
            source_ctx = SearchContext(
                query=ctx.query,
                langs=ctx.langs,
                per_source=ctx.per_source,
                country=ctx.country,
                partner_type=ctx.partner_type,
                client=ctx.client,
                timeout_seconds=cfg.timeout_seconds,
                openalex_api_key=ctx.openalex_api_key,
                wikidata_user_agent=ctx.wikidata_user_agent,
            )
            tasks.append(self._search_one(source, source_ctx))

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[PartnerResult] = []
        child_queries: list[ChildQuery] = []
        partial_errors: list[PartialError] = []

        for source, outcome in zip(sources, outcomes, strict=True):
            started = time.perf_counter()
            if isinstance(outcome, Exception):
                partial_errors.append(
                    PartialError(
                        source=source.id,
                        phase="search",
                        message=str(outcome),
                    )
                )
                child_queries.append(
                    ChildQuery(
                        source=source.id,
                        phase="search",
                        status="error",
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        error=str(outcome),
                    )
                )
            else:
                res, duration_ms = outcome
                results.extend(res)
                child_queries.append(
                    ChildQuery(
                        source=source.id,
                        phase="search",
                        status="ok",
                        duration_ms=duration_ms,
                    )
                )
        return results, child_queries, partial_errors

    async def _search_one(
        self, source: PartnerSource, ctx: SearchContext
    ) -> tuple[list[PartnerResult], int]:
        t0 = time.perf_counter()
        results = await source.search(ctx)
        return results, int((time.perf_counter() - t0) * 1000)

    async def _run_lookup_phase(
        self,
        jobs: list[ExpansionJob],
        ctx: SearchContext,
    ) -> tuple[list[PartnerResult], list[ChildQuery], list[PartialError]]:
        if not jobs:
            return [], [], []

        async def run_job(job: ExpansionJob):
            source = self.registry.get(job.target_source)
            if source is None:
                return job, None, Exception("source not found")
            cfg = self.registry.config(job.target_source)
            job_ctx = SearchContext(
                query=ctx.query,
                langs=ctx.langs,
                per_source=1,
                client=ctx.client,
                timeout_seconds=cfg.timeout_seconds,
                openalex_api_key=ctx.openalex_api_key,
                wikidata_user_agent=ctx.wikidata_user_agent,
            )
            t0 = time.perf_counter()
            try:
                result = await source.lookup(job_ctx, job.id_key, job.id_value)
                return job, result, None, int((time.perf_counter() - t0) * 1000)
            except Exception as exc:
                return job, None, exc, int((time.perf_counter() - t0) * 1000)

        outcomes = await asyncio.gather(
            *[run_job(j) for j in jobs], return_exceptions=True
        )
        results: list[PartnerResult] = []
        child_queries: list[ChildQuery] = []
        partial_errors: list[PartialError] = []

        for outcome in outcomes:
            if isinstance(outcome, Exception):
                continue
            job, result, exc, duration_ms = outcome
            trigger = {"key": job.id_key, "value": job.id_value}
            if exc:
                partial_errors.append(
                    PartialError(
                        source=job.target_source,
                        phase="lookup",
                        message=str(exc),
                    )
                )
                child_queries.append(
                    ChildQuery(
                        source=job.target_source,
                        phase="lookup",
                        status="error",
                        duration_ms=duration_ms,
                        trigger=trigger,
                        error=str(exc),
                    )
                )
            elif result:
                results.append(result)
                child_queries.append(
                    ChildQuery(
                        source=job.target_source,
                        phase="lookup",
                        status="ok",
                        duration_ms=duration_ms,
                        trigger=trigger,
                    )
                )
            else:
                child_queries.append(
                    ChildQuery(
                        source=job.target_source,
                        phase="lookup",
                        status="not_found",
                        duration_ms=duration_ms,
                        trigger=trigger,
                    )
                )
        return results, child_queries, partial_errors


def _relevance_query_from_results(results: list[PartnerResult]) -> str:
    if not results:
        return ""
    r = results[0]
    if r.label_country_locale:
        return r.label_country_locale
    if r.labels:
        return next(iter(r.labels.values()))
    return ""
