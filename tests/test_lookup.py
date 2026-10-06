import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.lookup import LookupQuery
from app.models.partner import PartnerResult, PartnerSourceId
from app.services.orchestrator import PartnerNotFoundError, SearchOrchestrator
from app.services.result_merger import ResultMerger
from app.sources.labri import LabriSource
from app.sources.protocol import SourceConfig
from app.sources.registry import SourceRegistry


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_lookup_query_expand_false_by_default():
    q = LookupQuery(source="ror", partner_id="05tj8pb04")
    assert q.expand is False
    assert q.merge is False


def test_lookup_query_accepts_dynamic_labri_source():
    q = LookupQuery(source="labri-tours", partner_id="123")
    assert q.source == "labri-tours"
    assert q.partner_id == "123"


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
async def test_lookup_invalid_source_returns_400(client):
    resp = await client.get("/v1/partners/invalid/abc123")
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        assert "valid_sources" in detail
    else:
        assert "Unknown source" in str(detail)


@pytest.mark.asyncio
async def test_lookup_accepts_registered_labri_tours():
    registry = SourceRegistry()
    registry._sources = {
        "labri-tours": LabriSource(
            id="labri-tours",
            display_name="LaBRRI Tours",
            base_url="https://tours.example/api",
            api_key="test-key",
        )
    }
    registry._config = {
        "labri-tours": SourceConfig(
            enabled=True,
            adapter="labri",
            display_name="LaBRRI Tours",
            base_url_env="LABRI_TOURS_API_URL",
            api_key_env="LABRI_TOURS_API_KEY",
            requires_env=[],
        )
    }

    async def fake_source_lookup(ctx, key, value):
        assert key == "labri-tours"
        assert value == "123"
        return PartnerResult(
            source="labri-tours",
            id="123",
            labels={"und": "Université de Tours"},
            external_ids={"labri-tours": "123"},
        )

    registry._sources["labri-tours"].lookup = fake_source_lookup  # type: ignore[method-assign]
    orch = SearchOrchestrator(registry=registry)
    resp = await orch.lookup_by_id(
        LookupQuery(source="labri-tours", partner_id="123")
    )
    assert len(resp.results) == 1
    assert resp.results[0].source == "labri-tours"
    assert resp.results[0].id == "123"


@pytest.mark.asyncio
async def test_lookup_rejects_unknown_source_id():
    registry = SourceRegistry()
    registry._sources = {}
    registry._config = {}
    orch = SearchOrchestrator(registry=registry)
    with pytest.raises(ValueError, match="Unknown source"):
        await orch.lookup_by_id(
            LookupQuery(source="labri-unknown", partner_id="123")
        )


@pytest.mark.asyncio
async def test_lookup_not_found_returns_404(client, monkeypatch):
    async def fake_lookup(_self, _query):
        raise PartnerNotFoundError("No partner found for ror:missing")

    monkeypatch.setattr(SearchOrchestrator, "lookup_by_id", fake_lookup)
    resp = await client.get("/v1/partners/ror/missing")
    assert resp.status_code == 404
