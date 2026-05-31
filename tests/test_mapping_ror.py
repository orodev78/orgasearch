from app.sources.ror import RorSource


def test_ror_maps_fixture(load_fixture):
    data = load_fixture("ror_sample.json")
    source = RorSource()
    result = source._map_item(data["items"][0])

    assert result.id == "03yrm5c26"
    assert result.labels["fr"] == "Université de Caen Normandie"
    assert result.external_ids["ror"] == "https://ror.org/03yrm5c26"
    assert result.external_ids["wikidata"] == "Q123456"
    assert result.country is not None
    assert result.country.code == "FR"
    assert result.coordinates is not None
    assert result.type.value == "education"
