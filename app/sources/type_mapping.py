from app.models.partner import PartnerType

ROR_TYPES: dict[str, PartnerType] = {
    "education": PartnerType.EDUCATION,
    "company": PartnerType.COMPANY,
    "nonprofit": PartnerType.NONPROFIT,
    "government": PartnerType.GOVERNMENT,
    "healthcare": PartnerType.HEALTHCARE,
    "facility": PartnerType.RESEARCH,
    "other": PartnerType.OTHER,
}

OPENALEX_TYPES: dict[str, PartnerType] = {
    "education": PartnerType.EDUCATION,
    "company": PartnerType.COMPANY,
    "nonprofit": PartnerType.NONPROFIT,
    "government": PartnerType.GOVERNMENT,
    "healthcare": PartnerType.HEALTHCARE,
    "facility": PartnerType.RESEARCH,
    "other": PartnerType.OTHER,
}

HAL_TYPES: dict[str, PartnerType] = {
    "institution": PartnerType.EDUCATION,
    "laboratory": PartnerType.RESEARCH,
    "research": PartnerType.RESEARCH,
    "university": PartnerType.EDUCATION,
    "company": PartnerType.COMPANY,
}

WIKIDATA_P31: dict[str, PartnerType] = {
    "Q3918": PartnerType.EDUCATION,
    "Q875538": PartnerType.EDUCATION,
    "Q31855": PartnerType.EDUCATION,
    "Q4830453": PartnerType.COMPANY,
    "Q43229": PartnerType.NONPROFIT,
    "Q327333": PartnerType.GOVERNMENT,
    "Q16917": PartnerType.HEALTHCARE,
    "Q31855": PartnerType.RESEARCH,
}


def normalize_ror_type(raw: str | None) -> PartnerType:
    if not raw:
        return PartnerType.OTHER
    return ROR_TYPES.get(raw.lower(), PartnerType.OTHER)


def normalize_openalex_type(raw: str | None) -> PartnerType:
    if not raw:
        return PartnerType.OTHER
    return OPENALEX_TYPES.get(raw.lower(), PartnerType.OTHER)


def normalize_hal_type(raw: str | None) -> PartnerType:
    if not raw:
        return PartnerType.OTHER
    key = raw.lower().split("/")[-1] if "/" in raw else raw.lower()
    return HAL_TYPES.get(key, PartnerType.OTHER)


def normalize_wikidata_p31(qid: str | None) -> PartnerType:
    if not qid:
        return PartnerType.OTHER
    return WIKIDATA_P31.get(qid.upper(), PartnerType.OTHER)
