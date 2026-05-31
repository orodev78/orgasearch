from app.models.partner import CountryInfo, PartnerResult, PartnerSourceId
from app.services.relevance import apply_relevance_scores, rank_to_source_score
from app.services.result_merger import ResultMerger


def test_rank_score_decay():
    assert rank_to_source_score(0) > rank_to_source_score(5)
    assert rank_to_source_score(0) == 1.0


def test_abdou_moumouni_ranks_uam_above_nagasaki():
    uam = PartnerResult(
        source=PartnerSourceId.ROR,
        id="05tj8pb04",
        labels={
            "en": "Abdou Moumouni University",
            "fr": "Université Abdou Moumouni de Niamey",
        },
        country=CountryInfo(code="NE", name="Niger"),
        score=rank_to_source_score(0),
        source_url="https://ror.org/05tj8pb04",
    )
    nagasaki = PartnerResult(
        source=PartnerSourceId.ROR,
        id="03ppx1p25",
        labels={"en": "University of Nagasaki", "ja": "長崎県立大学"},
        country=CountryInfo(code="JP", name="Japan"),
        score=rank_to_source_score(3),
        source_url="https://ror.org/03ppx1p25",
    )
    query = "Abdou Moumouni University of Niamey"
    apply_relevance_scores([uam, nagasaki], query)
    assert (uam.score or 0) > (nagasaki.score or 0)


def test_finalize_distinct_sorts_by_relevance():
    merger = ResultMerger()
    uam = PartnerResult(
        source=PartnerSourceId.ROR,
        id="05tj8pb04",
        labels={"en": "Abdou Moumouni University"},
        score=1.0,
        source_url="https://ror.org/05tj8pb04",
    )
    noise = PartnerResult(
        source=PartnerSourceId.ROR,
        id="03ppx1p25",
        labels={"en": "University of Nagasaki"},
        score=0.95,
        source_url="https://ror.org/03ppx1p25",
    )
    out = merger.finalize_distinct(
        [noise, uam], ["en"], limit=10, query="Abdou Moumouni University of Niamey"
    )
    assert out[0].id == "05tj8pb04"
