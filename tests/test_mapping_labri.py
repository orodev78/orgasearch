from app.sources.labri import LabriSource


def test_labri_maps_fixture(load_fixture):
    data = load_fixture("labri_sample.json")
    source = LabriSource(
        id="labri-tours",
        display_name="LaBRRI Tours",
        base_url="https://tours.example/api",
        api_key="test-key",
    )
    result = source._map_item(data["results"][0])

    assert result.source == "labri-tours"
    assert result.id == "123"
    assert result.labels["und"] == "Université de Tours"
    assert result.external_ids["ror"] == "https://ror.org/03yrm5c26"
    assert result.external_ids["hal"] == "300009"
    assert result.external_ids["labri-tours"] == "123"
    assert result.type is not None
    assert result.type.value == "education"
    assert result.type_source == "Université/Institution"
    assert result.city == "Tours"
    assert result.country is not None
    assert result.country.code == "FR"
    assert result.coordinates is not None
    assert result.coordinates.lat == 47.39
    assert result.website == "https://www.univ-tours.fr"


def test_labri_enabled_requires_url_and_key():
    assert LabriSource("labri-tours", "Tours", "", "").enabled() is False
    assert LabriSource("labri-tours", "Tours", "https://x/api", "").enabled() is False
    assert LabriSource("labri-tours", "Tours", "", "key").enabled() is False
    assert (
        LabriSource("labri-tours", "Tours", "https://x/api", "key").enabled() is True
    )
