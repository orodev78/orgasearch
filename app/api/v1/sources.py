from fastapi import APIRouter, Request

from app.core.rate_limit import limiter, read_rate_limit
from app.models.partner import SourceInfo, SourcesListResponse
from app.sources.registry import get_registry

router = APIRouter(prefix="/v1", tags=["sources"])


@router.get("/sources", response_model=SourcesListResponse)
@limiter.limit(read_rate_limit)
async def list_sources(request: Request) -> SourcesListResponse:
    registry = get_registry()
    items = [
        SourceInfo(**item)
        for item in registry.list_sources()
    ]
    return SourcesListResponse(sources=items)
