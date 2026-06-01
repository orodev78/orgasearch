import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app, create_app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["sources_loaded"] >= 4


@pytest.mark.asyncio
async def test_sources_list(client):
    resp = await client.get("/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    ids = {s["id"] for s in data["sources"]}
    assert "ror" in ids


@pytest.mark.asyncio
async def test_search_requires_min_length(client):
    resp = await client.get("/v1/partners/search", params={"q": "a"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cors_disabled_when_origins_empty(client):
    resp = await client.options(
        "/v1/partners/search",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_cors_when_origins_configured(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    get_settings.cache_clear()
    cors_app = create_app()
    transport = ASGITransport(app=cors_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.options(
            "/v1/partners/search",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    get_settings.cache_clear()
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
