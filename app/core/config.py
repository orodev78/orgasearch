from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Orgasearch"
    app_version: str = "1.0.0"
    openalex_api_key: str = ""
    wikidata_user_agent: str = "Orgasearch/1.0 (contact@example.org)"
    cache_url: str = ""
    search_default_limit: int = 30
    search_per_source_limit: int = 15
    search_timeout_seconds: float = 8.0
    search_max_query_length: int = 500
    search_max_langs: int = 10
    search_max_expansions_default: int = 12
    search_min_score: float = 0.45
    rate_limit_global: str = "120/minute"
    rate_limit_search: str = "30/minute"
    rate_limit_read: str = "60/minute"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
