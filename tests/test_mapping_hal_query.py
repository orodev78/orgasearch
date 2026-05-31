from app.sources.hal import _build_hal_query


def test_hal_query_strips_accents_and_uses_and():
    q = _build_hal_query("université caen")
    assert "universite" in q.lower()
    assert "caen" in q.lower()
    assert "AND" in q
