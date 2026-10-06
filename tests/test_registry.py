import os

from app.core.config import load_env_file
from app.sources.labri import build_labri_sources
from app.sources.protocol import SourceConfig
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


def _clear_labri_env(monkeypatch):
    for key in (
        "LABRI_TOURS_API_URL",
        "LABRI_TOURS_API_KEY",
        "LABRI_ORLEANS_API_URL",
        "LABRI_ORLEANS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_registry_labri_zero_available_without_env(monkeypatch):
    _clear_labri_env(monkeypatch)
    registry = SourceRegistry()
    registry.load()
    assert "labri-tours" in registry.valid_ids()
    assert registry.is_available("labri-tours") is False
    active_labri = [s.id for s in registry.active() if s.id.startswith("labri-")]
    assert active_labri == []


def test_registry_labri_available_when_env_pair_set(monkeypatch):
    _clear_labri_env(monkeypatch)
    monkeypatch.setenv("LABRI_TOURS_API_URL", "https://tours.example/api")
    monkeypatch.setenv("LABRI_TOURS_API_KEY", "tours-key")
    registry = SourceRegistry()
    registry.load()
    assert registry.is_available("labri-tours") is True
    active_labri = [s.id for s in registry.active() if s.id.startswith("labri-")]
    assert active_labri == ["labri-tours"]


def test_load_env_file_exposes_dynamic_labri_keys(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LABRI_TOURS_API_URL=https://from-dotenv.example/api\n"
        "LABRI_TOURS_API_KEY=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.core.config.ENV_FILE", env_path)
    _clear_labri_env(monkeypatch)
    assert load_env_file(override=True) is True
    assert os.environ.get("LABRI_TOURS_API_URL") == "https://from-dotenv.example/api"
    assert os.environ.get("LABRI_TOURS_API_KEY") == "from-dotenv"


def test_build_labri_sources_multiple_instances(monkeypatch):
    _clear_labri_env(monkeypatch)
    monkeypatch.setenv("LABRI_TOURS_API_URL", "https://tours.example/api")
    monkeypatch.setenv("LABRI_TOURS_API_KEY", "tours-key")
    monkeypatch.setenv("LABRI_ORLEANS_API_URL", "https://orleans.example/api")
    monkeypatch.setenv("LABRI_ORLEANS_API_KEY", "orleans-key")
    configs = {
        "labri-tours": SourceConfig(
            enabled=True,
            adapter="labri",
            display_name="LaBRRI Tours",
            base_url_env="LABRI_TOURS_API_URL",
            api_key_env="LABRI_TOURS_API_KEY",
        ),
        "labri-orleans": SourceConfig(
            enabled=True,
            adapter="labri",
            display_name="LaBRRI Orléans",
            base_url_env="LABRI_ORLEANS_API_URL",
            api_key_env="LABRI_ORLEANS_API_KEY",
        ),
    }
    sources = build_labri_sources(configs)
    assert {s.id for s in sources} == {"labri-tours", "labri-orleans"}
    assert all(s.enabled() for s in sources)
