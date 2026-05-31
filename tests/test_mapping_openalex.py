from app.sources.openalex import OpenAlexSource


def test_openalex_maps_fixture(load_fixture):
    data = load_fixture("openalex_sample.json")
    source = OpenAlexSource()
    result = source._map_item(data["results"][0])

    assert result.id == "1234567890"
    assert result.labels["en"] == "University of Caen Normandy"
    assert "ror" in result.external_ids
    assert result.external_ids["wikidata"] == "Q123456"
    assert result.country is not None
    assert result.country.code == "FR"
