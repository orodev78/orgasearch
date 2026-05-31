import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
