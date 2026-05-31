from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter, search_rate_limit
from app.models.lookup import LookupQuery
from app.models.partner import ErrorDetail, SearchResponse
from app.models.search import MAX_QUERY_LENGTH, SearchQuery
from app.services.orchestrator import PartnerNotFoundError, SearchOrchestrator
from app.sources.registry import get_registry

router = APIRouter(prefix="/v1/partners", tags=["partners"])


def get_orchestrator() -> SearchOrchestrator:
    return SearchOrchestrator()


@router.get("/search", response_model=SearchResponse)
@limiter.limit(search_rate_limit)
async def partners_search(
    request: Request,
    q: str = Query(
        ...,
        min_length=2,
        max_length=MAX_QUERY_LENGTH,
        description="Search text",
    ),
    langs: str = Query("fr,en", description="Comma-separated ISO 639-1 codes"),
    sources: str | None = Query(None, description="Comma-separated source ids"),
    limit: int | None = Query(None, ge=1, le=50),
    per_source: int | None = Query(None, ge=1, le=30),
    country: str | None = Query(None, min_length=2, max_length=2),
    type: str | None = Query(None, alias="type"),
    expand: bool = Query(True),
    merge: bool = Query(
        False,
        description="Fuse duplicate organizations across sources (default: separate row per source)",
    ),
    max_expansions: int | None = Query(None, ge=0, le=50),
    orchestrator: SearchOrchestrator = Depends(get_orchestrator),
) -> SearchResponse:
    settings = get_settings()
    try:
        query = SearchQuery(
            q=q,
            langs=langs,
            sources=sources,
            limit=limit or settings.search_default_limit,
            per_source=per_source or settings.search_per_source_limit,
            country=country,
            type=type,
            expand=expand,
            merge=merge,
            max_expansions=max_expansions
            or settings.search_max_expansions_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return await orchestrator.search(query)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/{source}/{partner_id}",
    response_model=SearchResponse,
    responses={404: {"model": ErrorDetail}},
)
@limiter.limit(search_rate_limit)
async def partners_lookup(
    request: Request,
    source: str,
    partner_id: str,
    langs: str = Query("fr,en", description="Comma-separated ISO 639-1 codes"),
    expand: bool = Query(
        False,
        description="Resolve related records via external_ids on other sources",
    ),
    merge: bool = Query(
        False,
        description="Fuse duplicate organizations across sources",
    ),
    limit: int | None = Query(None, ge=1, le=50),
    max_expansions: int | None = Query(None, ge=0, le=50),
    orchestrator: SearchOrchestrator = Depends(get_orchestrator),
) -> SearchResponse:
    settings = get_settings()
    try:
        query = LookupQuery(
            source=source,
            partner_id=partner_id,
            langs=langs,
            expand=expand,
            merge=merge,
            limit=limit or settings.search_default_limit,
            max_expansions=max_expansions
            or settings.search_max_expansions_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return await orchestrator.lookup_by_id(query)
    except PartnerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "Unknown source" in detail:
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": detail,
                    "valid_sources": get_registry().valid_ids(),
                },
            ) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
