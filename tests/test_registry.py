from app.sources.registry import SourceRegistry


def test_registry_loads_builtin_sources():
    registry = SourceRegistry()
    registry.load()
    ids = registry.valid_ids()
    assert "ror" in ids
    assert "wikidata" in ids
    assert "hal" in ids
    assert "openalex" in ids


def test_registry_unknown_source_raises():
    registry = SourceRegistry()
    registry.load()
    try:
        registry.active(["unknown_source"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unknown_source" in str(exc).lower() or "Unknown" in str(exc)
