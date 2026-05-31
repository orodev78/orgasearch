import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.search import MAX_QUERY_LENGTH, SearchQuery


def test_query_max_length():
    with pytest.raises(ValidationError):
        SearchQuery(q="x" * (MAX_QUERY_LENGTH + 1))


def test_langs_max_count():
    max_langs = get_settings().search_max_langs
    langs = ",".join(["aa"] * (max_langs + 1))
    with pytest.raises(ValidationError):
        SearchQuery(q="test", langs=langs)


def test_invalid_lang_code():
    with pytest.raises(ValidationError):
        SearchQuery(q="test", langs="fr,english")


def test_default_max_expansions():
    q = SearchQuery(q="cnrs")
    assert q.max_expansions == 12
