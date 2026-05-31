from app.models.partner import PartnerResult, PartnerSourceId
from app.services.expansion_planner import ExpansionPlanner
from app.sources.registry import SourceRegistry


def test_expansion_plans_ror_lookups():
    registry = SourceRegistry()
    registry.load()
    planner = ExpansionPlanner()
    phase1 = [
        PartnerResult(
            source=PartnerSourceId.ROR,
            id="03yrm5c26",
            external_ids={"ror": "https://ror.org/03yrm5c26"},
            labels={"en": "Test University"},
            source_url="https://ror.org/03yrm5c26",
        )
    ]
    jobs = planner.plan(
        phase1,
        registry,
        requested_sources=None,
        max_expansions=24,
        expand_enabled=True,
    )
    assert len(jobs) >= 1
    assert all(j.id_key == "ror" for j in jobs)
    targets = {j.target_source for j in jobs}
    assert "wikidata" in targets
