"""API-Football adapter helpers.

The prediction engine remains independent: bookmaker odds are never mapped
into match objects. This module only prepares football data for the model.

The live API key is read from the caller/environment; never hard-code it.
"""

import os
from functools import lru_cache
from typing import Dict, List

import requests

from config import CORE_COUNTRIES, INCLUDE_ADDITIONAL_SENIOR_DOMESTIC, ONLY_PRIMARY_LEAGUES
from data.competition_filter import accept_competition

BASE_URL = "https://v3.football.api-sports.io"


def _headers(api_key: str) -> Dict[str, str]:
    return {"x-apisports-key": api_key}


def _get(api_key: str, path: str, params: dict) -> dict:
    response = requests.get(
        f"{BASE_URL}{path}", headers=_headers(api_key), params=params, timeout=20
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"API-Football error: {payload['errors']}")
    return payload


@lru_cache(maxsize=16)
def discover_competitions(api_key: str, country: str, season: int) -> List[dict]:
    """Discover senior competitions for one of the 8 core countries.

    The result is cached for the process lifetime so repeated scans do not
    repeatedly spend requests on the same league list.
    """
    if country not in CORE_COUNTRIES:
        raise ValueError(f"Country is not in the 8-core set: {country}")

    data = _get(api_key, "/leagues", {"country": country, "season": season})
    result = []
    for item in data.get("response", []):
        league = item.get("league", {})
        name = league.get("name", "")
        if not accept_competition(country, name):
            continue
        result.append({
            "id": league.get("id"),
            "name": name,
            "country": country,
            "type": league.get("type"),
            "priority": (
                100 if name in CORE_COUNTRIES[country]["primary"]
                else 80 if name in CORE_COUNTRIES[country]["major"]
                else 50
            ),
        })

    if ONLY_PRIMARY_LEAGUES:
        # Top-flight only: this is what actually shapes the daily list, so
        # it's checked first and short-circuits the wider "major" filter
        # below — no lower divisions, no cups, no discovered extras.
        primary = set(CORE_COUNTRIES[country]["primary"])
        result = [x for x in result if x["name"] in primary]
    elif not INCLUDE_ADDITIONAL_SENIOR_DOMESTIC:
        allowed = set(CORE_COUNTRIES[country]["primary"] + CORE_COUNTRIES[country]["major"])
        result = [x for x in result if x["name"] in allowed]

    return sorted(result, key=lambda x: (-x["priority"], x["name"]))


def fetch_upcoming_matches(api_key: str, league_id: int, season: int, next_games: int = 20) -> List[dict]:
    """Fetch upcoming fixtures for one competition.

    Only fixture/team/time data is returned here. Odds are intentionally
    ignored even if the provider exposes them elsewhere.
    """
    data = _get(
        api_key,
        "/fixtures",
        {"league": league_id, "season": season, "next": next_games},
    )
    matches = []
    for item in data.get("response", []):
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        matches.append({
            "fixture_id": fixture.get("id"),
            "date": fixture.get("date"),
            "timestamp": fixture.get("timestamp"),
            "league": item.get("league", {}).get("name"),
            "league_id": item.get("league", {}).get("id"),
            "country": item.get("league", {}).get("country"),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
            "home_id": teams.get("home", {}).get("id"),
            "away_id": teams.get("away", {}).get("id"),
        })
    return matches


def api_key_from_env() -> str:
    key = os.getenv("API_FOOTBALL_KEY") or os.getenv("APISPORTS_KEY")
    if not key:
        raise RuntimeError("Set API_FOOTBALL_KEY in .env/environment before live use.")
    return key
