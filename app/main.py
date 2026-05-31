from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.search import router as search_router
from app.api.v1.sources import router as sources_router
from app.core.rate_limit import limiter, read_rate_limit
from app.core.config import get_settings
from app.core.http import close_http_client, get_http_client
from app.models.partner import HealthResponse
from app.sources.registry import get_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_registry().load()
    await get_http_client()
    yield
    await close_http_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Metasearch API for institutional partners across ROR, Wikidata, "
            "HAL, and OpenAlex."
        ),
        lifespan=lifespan,
        docs_url="/api/doc",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    @limiter.limit(read_rate_limit)
    async def health(request: Request) -> HealthResponse:
        registry = get_registry()
        return HealthResponse(
            status="ok",
            app=settings.app_name,
            version=settings.app_version,
            sources_loaded=len(registry.valid_ids()),
        )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/api/doc")

    app.include_router(search_router)
    app.include_router(sources_router)
    return app


app = create_app()
