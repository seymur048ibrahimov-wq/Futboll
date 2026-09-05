"""football-data.org (v4) adapter helpers.

Free tier: current season only (this is why we migrated off API-Football,
whose free plan only allows 2022-2024), ~10 requests/minute, no odds, no
shot stats/xG, no injuries data. The prediction engine remains independent:
bookmaker odds are never mapped into match objects.

There is no more "discover competitions" step: football-data.org's free
plan only covers a fixed, known set of competitions, so config.py's
FOOTBALL_DATA_COMPETITIONS mapping is the single source of truth for which
leagues the scanner looks at.
"""

import os
import time
from typing import Dict, List, Optional

import requests

from config import FOOTBALL_DATA_COMPETITIONS

BASE_URL = "https://api.football-data.org/v4"

# Simple global throttle so a single scan (many sequential calls) stays
# under the free plan's ~10 requests/minute limit.
_MIN_INTERVAL_SECONDS = 6.5
_last_call_ts = 0.0


def _headers(api_key: str) -> Dict[str, str]:
    return {"X-Auth-Token": api_key}


def _get(api_key: str, path: str, params: Optional[dict] = None) -> dict:
    global _last_call_ts
    wait = _MIN_INTERVAL_SECONDS - (time.time() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)

    response = requests.get(
        f"{BASE_URL}{path}", headers=_headers(api_key), params=params or {}, timeout=20
    )
    _last_call_ts = time.time()

    if response.status_code == 429:
        raise RuntimeError("football-data.org rate limit hit (429) — too many requests too fast.")
    if response.status_code == 403:
        raise RuntimeError("football-data.org: 403 Forbidden — check FOOTBALL_DATA_API_KEY.")
    response.raise_for_status()
    return response.json()


def fetch_scheduled_matches(api_key: str) -> List[dict]:
    """One call across every configured competition, scheduled matches only,
    soonest first."""
    codes = ",".join(FOOTBALL_DATA_COMPETITIONS.values())
    code_to_country = {v: k for k, v in FOOTBALL_DATA_COMPETITIONS.items()}

    data = _get(api_key, "/matches", {"competitions": codes, "status": "SCHEDULED"})

    matches = []
    for item in data.get("matches", []):
        comp = item.get("competition", {})
        home = item.get("homeTeam", {})
        away = item.get("awayTeam", {})
        if not home.get("id") or not away.get("id"):
            continue
        matches.append({
            "fixture_id": item.get("id"),
            "date": item.get("utcDate", ""),
            "league": comp.get("name"),
            "league_code": comp.get("code"),
            "country": code_to_country.get(comp.get("code"), ""),
            "home": home.get("name"),
            "away": away.get("name"),
            "home_id": home.get("id"),
            "away_id": away.get("id"),
        })

    matches.sort(key=lambda m: m["date"])
    return matches


def fetch_team_recent_matches(api_key: str, team_id: int, limit: int = 8) -> List[dict]:
    """Last N finished matches for a team, used for both form/Elo and the
    goals-average xG fallback (see stats_provider.py)."""
    data = _get(api_key, f"/teams/{team_id}/matches", {"status": "FINISHED", "limit": limit})
    return data.get("matches", [])


def api_key_from_env() -> str:
    key = os.getenv("FOOTBALL_DATA_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("Set FOOTBALL_DATA_API_KEY in .env/environment before live use.")
    return key
