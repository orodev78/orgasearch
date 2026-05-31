import pytest

from app.core.sparql import (
    build_property_lookup_query,
    escape_literal,
    validate_ror_lookup_value,
)


def test_escape_literal_quotes():
    assert escape_literal('say "hello"') == 'say \\"hello\\"'


def test_build_query_safe():
    q = build_property_lookup_query("P6782", "https://ror.org/051kpcy16")
    assert "051kpcy16" in q
    assert "}" not in q.split("WHERE")[1].split('"')[1]


def test_ror_url_validation():
    assert validate_ror_lookup_value("051kpcy16") == "https://ror.org/051kpcy16"


def test_ror_injection_rejected():
    with pytest.raises(ValueError):
        validate_ror_lookup_value('https://ror.org/evil" . } UNION { ?item wdt:P31 "')


def test_literal_brace_rejected():
    with pytest.raises(ValueError):
        escape_literal("value } malicious")
