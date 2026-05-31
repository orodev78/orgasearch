from app.models.partner import CountryInfo, PartnerResult, PartnerSourceId
from app.services.label_resolver import LabelResolver


def test_country_locale_label_not_overridden_by_langs():
    resolver = LabelResolver()
    result = PartnerResult(
        source=PartnerSourceId.ROR,
        id="03avx4w11",
        labels={"fr": "CAEN société", "it": "CAEN", "en": "CAEN company"},
        country=CountryInfo(code="IT", name="Italy"),
        source_url="https://ror.org/03avx4w11",
    )
    resolved = resolver.apply(result, langs=["fr", "en"])
    assert resolved.country_locale == "it"
    assert resolved.label_country_locale == "CAEN"


def test_france_uses_french_label_with_fr_langs():
    resolver = LabelResolver()
    result = PartnerResult(
        source=PartnerSourceId.ROR,
        id="051kpcy16",
        labels={
            "fr": "université de Caen-Normandie",
            "en": "University of Caen Normandy",
            "it": "Università di Caen",
        },
        country=CountryInfo(code="FR", name="France"),
        source_url="https://ror.org/051kpcy16",
    )
    resolved = resolver.apply(result, langs=["fr", "en"])
    assert resolved.country_locale == "fr"
    assert resolved.label_country_locale == "université de Caen-Normandie"
