from app.models.partner import PartnerResult, PartnerSourceId
from app.services.result_merger import ResultMerger


def test_merger_dedup_by_ror():
    merger = ResultMerger()
    ror = PartnerResult(
        source=PartnerSourceId.ROR,
        id="03yrm5c26",
        external_ids={"ror": "https://ror.org/03yrm5c26"},
        labels={"en": "University A"},
        city="Caen",
        source_url="https://ror.org/03yrm5c26",
    )
    oa = PartnerResult(
        source=PartnerSourceId.OPENALEX,
        id="123",
        external_ids={
            "ror": "https://ror.org/03yrm5c26",
            "openalex": "I123",
        },
        labels={"en": "University A OpenAlex"},
        website="https://example.org",
        source_url="https://openalex.org/I123",
    )
    merged = merger.merge(
        [ror, oa], ["en", "fr"], limit=10, query="University A"
    )
    assert len(merged) == 1
    assert merged[0].sources is not None
    assert "ror" in merged[0].sources
    assert "openalex" in merged[0].sources
    assert merged[0].website == "https://example.org"


def test_merger_drops_results_below_min_score():
    merger = ResultMerger()
    strong = PartnerResult(
        source=PartnerSourceId.ROR,
        id="good",
        labels={"en": "Abdou Moumouni University"},
        score=0.9,
        source_url="https://ror.org/good",
    )
    weak = PartnerResult(
        source=PartnerSourceId.ROR,
        id="noise",
        labels={"en": "University of Nagasaki"},
        score=0.2,
        source_url="https://ror.org/noise",
    )
    out = merger.finalize_distinct(
        [weak, strong], ["en"], limit=10, query="Abdou Moumouni University"
    )
    assert len(out) == 1
    assert out[0].id == "good"
