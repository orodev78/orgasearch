from app.sources.wikidata import WikidataSource


def test_wikidata_maps_entity(load_fixture):
    data = load_fixture("wikidata_entities.json")
    source = WikidataSource()
    result = source._map_entity("Q123456", data["entities"]["Q123456"])

    assert result is not None
    assert result.id == "Q123456"
    assert "fr" in result.labels
    assert result.external_ids["wikidata"] == "Q123456"
    assert "ror" in result.external_ids
    assert result.website == "https://www.unicaen.fr"
    assert result.coordinates is not None


def test_resolve_country_from_p297():
    from app.sources.wikidata import _resolve_country

    entities = {
        "Q1032": {
            "labels": {"en": {"value": "Niger"}},
            "claims": {
                "P297": [
                    {
                        "mainsnak": {
                            "datavalue": {"type": "string", "value": "NE"}
                        }
                    }
                ]
            },
        }
    }
    country = _resolve_country("Q1032", entities)
    assert country is not None
    assert country.code == "NE"
    assert country.name == "Niger"


def test_resolve_country_iso_two_letter():
    from app.sources.wikidata import _resolve_country

    country = _resolve_country("ne", {})
    assert country is not None
    assert country.code == "NE"


def test_resolve_country_unknown_qid_returns_none():
    from app.sources.wikidata import _resolve_country

    assert _resolve_country("Q999999", {}) is None


def test_resolve_place_label_from_qid():
    from app.sources.wikidata import _resolve_place_label

    entities = {
        "Q3672": {
            "labels": {
                "en": {"value": "Niamey"},
                "fr": {"value": "Niamey"},
            }
        }
    }
    assert _resolve_place_label("Q3672", entities, ["fr", "en"]) == "Niamey"


def test_resolve_place_label_prefers_requested_lang():
    from app.sources.wikidata import _resolve_place_label

    entities = {
        "Q90": {
            "labels": {
                "en": {"value": "Paris"},
                "fr": {"value": "Paris"},
            }
        }
    }
    assert _resolve_place_label("Q90", entities, ["fr"]) == "Paris"


def test_map_entity_resolves_city_when_entities_provided():
    from app.sources.wikidata import WikidataSource

    source = WikidataSource()
    ent = {
        "labels": {"en": {"value": "Test University"}},
        "claims": {
            "P131": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "type": "wikibase-entityid",
                            "value": {"id": "Q3672"},
                        }
                    }
                }
            ],
        },
    }
    entities = {
        "Q3672": {"labels": {"en": {"value": "Niamey"}, "fr": {"value": "Niamey"}}},
    }
    result = source._map_entity(
        "Q1", ent, entities=entities, langs=["fr", "en"]
    )
    assert result is not None
    assert result.city == "Niamey"
    assert result.city != "Q3672"
