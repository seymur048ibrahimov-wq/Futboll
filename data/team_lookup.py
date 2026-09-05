"""Team search across the 7 core competitions.

football-data.org's free tier has no name-search endpoint, so we build our
own small directory by listing each competition's teams once (7 calls) and
caching it in memory for a while — repeated lookups don't re-spend quota.
"""

import time
from typing import List, Optional

from config import FOOTBALL_DATA_COMPETITIONS
from data.api_adapter import _get

_CACHE_TTL_SECONDS = 6 * 3600  # refresh the team list every 6 hours
_cache = {"teams": [], "built_at": 0.0}


def _fetch_competition_teams(api_key: str, code: str) -> List[dict]:
    data = _get(api_key, f"/competitions/{code}/teams", {})
    return [
        {"id": t.get("id"), "name": t.get("name"), "short_name": t.get("shortName")}
        for t in data.get("teams", [])
    ]


def _build_directory(api_key: str) -> List[dict]:
    teams = []
    for country, code in FOOTBALL_DATA_COMPETITIONS.items():
        try:
            comp_teams = _fetch_competition_teams(api_key, code)
        except Exception:
            continue
        for t in comp_teams:
            t["country"] = country
        teams.extend(comp_teams)
    return teams


def _directory(api_key: str) -> List[dict]:
    stale = (time.time() - _cache["built_at"]) > _CACHE_TTL_SECONDS
    if not _cache["teams"] or stale:
        fresh = _build_directory(api_key)
        if fresh:  # don't wipe a good cache with an empty result from a bad call
            _cache["teams"] = fresh
            _cache["built_at"] = time.time()
    return _cache["teams"]


def find_team(api_key: str, query: str) -> Optional[dict]:
    """Case-insensitive exact/short-name match first, then substring match
    (shortest matching name wins, since that's usually the closest to what
    was actually typed)."""
    query_l = query.strip().lower()
    if not query_l:
        return None

    teams = _directory(api_key)

    for t in teams:
        if t["name"].lower() == query_l or (t.get("short_name") or "").lower() == query_l:
            return t

    candidates = [
        t for t in teams
        if query_l in t["name"].lower() or query_l in (t.get("short_name") or "").lower()
    ]
    if candidates:
        candidates.sort(key=lambda t: len(t["name"]))
        return candidates[0]

    return None
