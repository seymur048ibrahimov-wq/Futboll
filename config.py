# FootballAI V3 configuration
# Independent model: bookmaker odds are NOT used anywhere.

# 8 əsas ölkə. Bot bu ölkələrin daxilindəki kişi/senior yerli yarışları da görə bilər.
CORE_COUNTRIES = {
    "England": {
        "flag": "🇬🇧",
        "primary": ["Premier League"],
        "major": ["Championship", "League One", "League Two", "National League", "FA Cup", "League Cup", "Community Shield", "EFL Trophy", "FA Trophy"],
    },
    "Spain": {
        "flag": "🇪🇸",
        "primary": ["La Liga"],
        "major": ["Segunda División", "Primera División RFEF - Group 1", "Primera División RFEF - Group 2", "Primera División RFEF - Group 3", "Primera División RFEF - Group 4", "Primera División RFEF - Group 5", "Copa del Rey", "Super Cup", "Copa Federacion"],
    },
    "Italy": {
        "flag": "🇮🇹",
        "primary": ["Serie A"],
        "major": ["Serie B", "Serie C - Girone A", "Serie C - Girone B", "Serie C - Girone C", "Serie C - Promotion - Play-offs", "Coppa Italia", "Coppa Italia Serie C", "Supercoppa Lega Finals"],
    },
    "Germany": {
        "flag": "🇩🇪",
        "primary": ["Bundesliga"],
        "major": ["2. Bundesliga", "3. Liga", "DFB Pokal", "Super Cup", "Regionalliga - Bayern", "Regionalliga - Nord", "Regionalliga - Nordost", "Regionalliga - SudWest", "Regionalliga - West", "Regionalliga - Promotion Play-offs", "Regionalliga - Relegation Round"],
    },
    "France": {
        "flag": "🇫🇷",
        "primary": ["Ligue 1"],
        "major": ["Ligue 2", "Ligue 3", "Coupe de France", "Coupe de la Ligue", "Trophée des Champions", "National 2 - Group A", "National 2 - Group B", "National 2 - Group C", "National 2 - Group D"],
    },
    "Netherlands": {
        "flag": "🇳🇱",
        "primary": ["Eredivisie"],
        "major": ["Eerste Divisie", "KNVB Beker", "Super Cup", "Tweede Divisie", "Derde Divisie - A", "Derde Divisie - B"],
    },
    "Portugal": {
        "flag": "🇵🇹",
        "primary": ["Primeira Liga"],
        "major": ["Segunda Liga", "Liga 3", "Taça de Portugal", "Taça da Liga", "Super Cup", "Campeonato de Portugal Prio - Group A", "Campeonato de Portugal Prio - Group B", "Campeonato de Portugal Prio - Group C", "Campeonato de Portugal Prio - Group D", "Campeonato de Portugal Prio - Group E", "Campeonato de Portugal Prio - Group F", "Campeonato de Portugal Prio - Group G", "Campeonato de Portugal Prio - Group H", "Campeonato de Portugal Prio - Promotion Round"],
    },
    "Turkey": {
        "flag": "🇹🇷",
        "primary": ["Süper Lig"],
        "major": ["1. Lig", "2. Lig", "3. Lig - Group 1", "3. Lig - Group 2", "3. Lig - Group 3", "3. Lig - Group 4", "3. Lig - Play-offs", "Türkiye Kupası", "Super Cup"],
    },
}

# Backwards-compatible primary league IDs used by the original V3 demo/config.
# These are NOT used to introduce bookmaker data.
LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Süper Lig": 203,
}

ALT_OVER_LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
MIN_CONFIDENCE = 65
MIN_MATCH_SCORE = 62

# Competition selection policy.
# "primary" = highest priority; "major" = included and ranked below primary.
# The live adapter can also discover additional senior domestic competitions
# from API-Football and add them after filtering out women/youth/reserve events.
INCLUDE_ADDITIONAL_SENIOR_DOMESTIC = True
EXCLUDE_NAME_TOKENS = (
    "Women", "Women's", "Women’s", "Feminine", "Feminin", "Women -",
    "U18", "U19", "U20", "U21", "U23", "Youth", "Junior", "Reserve",
    "Premier League 2", "Professional Development League",
)

# Lower divisions/cups are allowed into the scanner, but the model should
# require stronger data-quality checks before emitting a signal.
MIN_DATA_QUALITY_FOR_NON_PRIMARY = 70
