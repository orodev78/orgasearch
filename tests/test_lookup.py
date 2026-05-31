import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.lookup import LookupQuery
from app.models.partner import PartnerResult, PartnerSourceId
from app.services.orchestrator import PartnerNotFoundError, SearchOrchestrator
from app.services.result_merger import ResultMerger


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_lookup_query_expand_false_by_default():
    q = LookupQuery(source="ror", partner_id="05tj8pb04")
    assert q.expand is False
    assert q.merge is False


def test_merger_skips_min_score_when_disabled():
    merger = ResultMerger()
    weak = PartnerResult(
        source=PartnerSourceId.ROR,
        id="noise",
        labels={"en": "University of Nagasaki"},
        score=0.1,
        source_url="https://ror.org/noise",
    )
    out = merger.finalize_distinct(
        [weak], ["en"], limit=10, query="irrelevant", apply_min_score=False
    )
    assert len(out) == 1
    assert out[0].id == "noise"


@pytest.mark.asyncio
async def test_lookup_invalid_source_returns_422(client):
    resp = await client.get("/v1/partners/invalid/abc123")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_not_found_returns_404(client, monkeypatch):
    async def fake_lookup(_self, _query):
        raise PartnerNotFoundError("No partner found for ror:missing")

    monkeypatch.setattr(SearchOrchestrator, "lookup_by_id", fake_lookup)
    resp = await client.get("/v1/partners/ror/missing")
    assert resp.status_code == 404
