from app.sources.hal import HalSource


def test_hal_maps_fixture(load_fixture):
    data = load_fixture("hal_sample.json")
    source = HalSource()
    result = source._map_doc(data["response"]["docs"][0])

    assert result.id == "129439"
    assert "fr" in result.labels
    assert result.external_ids["hal"] == "129439"
    assert result.country is not None
    assert result.country.code == "FR"
    assert result.country.name == "France"
    assert result.type.value == "research"


def test_hal_country_iso_code_resolves_name():
    source = HalSource()
    result = source._map_doc({"docid": "1", "country_s": ["ne"]})
    assert result.country is not None
    assert result.country.code == "NE"
    assert result.country.name == "Niger"
