from config import CORE_COUNTRIES, EXCLUDE_NAME_TOKENS, MIN_DATA_QUALITY_FOR_NON_PRIMARY


def is_excluded_competition(name: str) -> bool:
    """Reject women's/youth/reserve competitions from the senior-football bot."""
    value = (name or "").strip().lower()
    return any(token.lower() in value for token in EXCLUDE_NAME_TOKENS)


def competition_priority(country: str, competition: str) -> int:
    """Return 100 primary, 80 major, 50 discovered senior competition."""
    cfg = CORE_COUNTRIES.get(country, {})
    if competition in cfg.get("primary", []):
        return 100
    if competition in cfg.get("major", []):
        return 80
    return 50


def accept_competition(country: str, competition: str, data_quality: float = 100) -> bool:
    if country not in CORE_COUNTRIES:
        return False
    if is_excluded_competition(competition):
        return False
    priority = competition_priority(country, competition)
    if priority < 100 and data_quality < MIN_DATA_QUALITY_FOR_NON_PRIMARY:
        return False
    return True
