# FootballAI V3 configuration
# Independent model: bookmaker odds are NOT used anywhere.

# 7 əsas ölkə (Türkiyə çıxarıldı — football-data.org pulsuz planında yoxdur).
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
}

# football-data.org (v4) competition codes for each core country's primary
# (top-flight) league. Free-tier plan covers current season for exactly
# these competitions — this is now the single source of truth for which
# leagues the scanner looks at; there is no more "discover competitions"
# step since the provider already gives us a fixed, known set.
FOOTBALL_DATA_COMPETITIONS = {
    "England": "PL",
    "Spain": "PD",
    "Italy": "SA",
    "Germany": "BL1",
    "France": "FL1",
    "Netherlands": "DED",
    "Portugal": "PPL",
}

# Caps how many total scheduled fixtures (across every competition combined)
# get full feature-building per scan. football-data.org's free plan is
# limited to ~10 requests/minute, and each fixture costs 2 requests (one
# per team), so this keeps a single scan's runtime and request count sane.
MAX_TOTAL_FIXTURES_PER_SCAN = 20

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

# If True, the scanner only looks at each country's top-flight league
# (CORE_COUNTRIES[...]["primary"]) — no lower divisions, no cups, no
# discovered extras. This keeps the bot's daily picks to the same marquee
# fixtures a bookmaker's "main games" list shows (real named matchups only,
# no round-aggregate markets), and it drastically cuts API-Football request
# usage since every non-primary competition is skipped before any
# fixtures/stats are fetched for it.
ONLY_PRIMARY_LEAGUES = True
EXCLUDE_NAME_TOKENS = (
    "Women", "Women's", "Women’s", "Feminine", "Feminin", "Women -",
    "U18", "U19", "U20", "U21", "U23", "Youth", "Junior", "Reserve",
    "Premier League 2", "Professional Development League",
)

# Lower divisions/cups are allowed into the scanner, but the model should
# require stronger data-quality checks before emitting a signal.
MIN_DATA_QUALITY_FOR_NON_PRIMARY = 70
