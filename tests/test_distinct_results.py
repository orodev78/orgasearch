from app.models.partner import PartnerResult, PartnerSourceId
from app.services.result_merger import ResultMerger


def test_distinct_keeps_separate_source_rows():
    merger = ResultMerger()
    ror = PartnerResult(
        source=PartnerSourceId.ROR,
        id="051kpcy16",
        external_ids={"ror": "https://ror.org/051kpcy16", "wikidata": "Q568554"},
        labels={"fr": "université de Caen-Normandie", "en": "University of Caen Normandy"},
        source_url="https://ror.org/051kpcy16",
    )
    wd = PartnerResult(
        source=PartnerSourceId.WIKIDATA,
        id="Q568554",
        external_ids={"wikidata": "Q568554", "ror": "https://ror.org/051kpcy16"},
        labels={"fr": "Université de Caen Normandie", "it": "Università di Caen"},
        source_url="https://www.wikidata.org/wiki/Q568554",
    )
    out = merger.finalize_distinct(
        [ror, wd], ["fr", "en"], limit=10, query="université caen"
    )
    assert len(out) == 2
    assert out[0].labels != out[1].labels
    ror_row = next(r for r in out if r.source == PartnerSourceId.ROR)
    wd_row = next(r for r in out if r.source == PartnerSourceId.WIKIDATA)
    assert "it" not in ror_row.labels
    assert "it" in wd_row.labels
    assert ror_row.sources == ["ror"]
    assert wd_row.sources == ["wikidata"]
