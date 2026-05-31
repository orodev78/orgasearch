"""SPARQL literal escaping and property validation for Wikidata lookups."""

from __future__ import annotations

import re

PROP_RE = re.compile(r"^P\d+$", re.I)
MAX_LITERAL_LEN = 256
ROR_URL_RE = re.compile(
    r"^https://ror\.org/[a-z0-9]{5,12}$",
    re.I,
)
ROR_ID_RE = re.compile(r"^[a-z0-9]{5,12}$", re.I)
ISNI_RE = re.compile(r"^[0-9Xx\s]{8,20}$")


def validate_property(prop: str) -> str:
    if not PROP_RE.match(prop):
        raise ValueError(f"Invalid Wikidata property: {prop!r}")
    return prop


def escape_literal(value: str) -> str:
    if len(value) > MAX_LITERAL_LEN:
        raise ValueError("SPARQL literal value too long")
    if any(c in value for c in ("\n", "\r", "\x00", "{", "}", "|")):
        raise ValueError("SPARQL literal contains invalid characters")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def validate_ror_lookup_value(value: str) -> str:
    value = value.strip()
    if value.startswith("http"):
        if not ROR_URL_RE.match(value):
            raise ValueError("Invalid ROR URL for SPARQL lookup")
        return value
    if ROR_ID_RE.match(value):
        return f"https://ror.org/{value.lower()}"
    raise ValueError("Invalid ROR id for SPARQL lookup")


def validate_isni_value(value: str) -> str:
    normalized = " ".join(value.split())
    if not ISNI_RE.match(normalized):
        raise ValueError("Invalid ISNI for SPARQL lookup")
    return normalized


def build_property_lookup_query(prop: str, value: str) -> str:
    prop_id = validate_property(prop)
    escaped = escape_literal(value)
    return f"SELECT ?item WHERE {{ ?item wdt:{prop_id} \"{escaped}\" . }} LIMIT 1"
