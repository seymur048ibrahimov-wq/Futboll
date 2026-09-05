"""Team search across the 7 core competitions.

football-data.org's free tier has no name-search endpoint, so we build our
own small directory by listing each competition's teams once (7 calls) and
caching it in memory for a while — repeated lookups don't re-spend quota.
"""

import difflib
import logging
import re
import time
from typing import List, Optional, Tuple

from config import FOOTBALL_DATA_COMPETITIONS
from data.api_adapter import _get

logger = logging.getLogger("footballai.team_lookup")

_CACHE_TTL_SECONDS = 6 * 3600  # refresh the team list every 6 hours
_FUZZY_CUTOFF = 0.6
_cache = {"teams": [], "built_at": 0.0, "last_errors": []}


_CLUB_SUFFIXES = {"fc", "afc", "cf", "sc", "cfc", "sv", "tsg", "vfl", "vfb", "fk", "sk", "ac"}


def _normalize(s: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", s.lower()).strip()
    words = [w for w in cleaned.split() if w not in _CLUB_SUFFIXES]
    return " ".join(words)


def _fetch_competition_teams(api_key: str, code: str) -> List[dict]:
    data = _get(api_key, f"/competitions/{code}/teams", {})
    return [
        {"id": t.get("id"), "name": t.get("name"), "short_name": t.get("shortName")}
        for t in data.get("teams", [])
    ]


def _build_directory(api_key: str) -> Tuple[List[dict], List[str]]:
    teams = []
    errors = []
    for country, code in FOOTBALL_DATA_COMPETITIONS.items():
        try:
            comp_teams = _fetch_competition_teams(api_key, code)
        except Exception as exc:
            logger.warning("Team list fetch failed for %s (%s): %s", country, code, exc)
            errors.append(f"{country} ({code}): {exc}")
            continue
        for t in comp_teams:
            t["country"] = country
        teams.extend(comp_teams)
    return teams, errors


def _directory(api_key: str) -> List[dict]:
    stale = (time.time() - _cache["built_at"]) > _CACHE_TTL_SECONDS
    if not _cache["teams"] or stale:
        fresh, errors = _build_directory(api_key)
        _cache["last_errors"] = errors
        if fresh:  # don't wipe a good cache with an empty result from a bad call
            _cache["teams"] = fresh
            _cache["built_at"] = time.time()
    return _cache["teams"]


def directory_status() -> dict:
    """For diagnostics: how many teams are cached and what went wrong last
    time the directory was (re)built, if anything."""
    return {
        "team_count": len(_cache["teams"]),
        "last_errors": _cache["last_errors"],
    }


def find_team(api_key: str, query: str) -> Optional[dict]:
    """Exact match, then substring match, then fuzzy match (for typos like
    'Hoffenhaym' -> 'Hoffenheim' or 'B.dotrmund' -> 'Borussia Dortmund')."""
    raw = query.strip().lower()
    if not raw:
        return None

    teams = _directory(api_key)

    # 1) exact name/short-name match
    for t in teams:
        if t["name"].lower() == raw or (t.get("short_name") or "").lower() == raw:
            return t

    # 2) substring match — shortest matching name wins (closest to what was typed)
    candidates = [
        t for t in teams
        if raw in t["name"].lower() or raw in (t.get("short_name") or "").lower()
    ]
    if candidates:
        candidates.sort(key=lambda t: len(t["name"]))
        return candidates[0]

    # 3) fuzzy match — tolerates typos/misspellings, matched against both full
    # names and individual words within them (so "Hoffenhaym" still finds
    # "TSG 1899 Hoffenheim", and "B.dotrmund" still finds "Borussia Dortmund")
    query_n = _normalize(query)
    searchable = {}
    for t in teams:
        for full in filter(None, [t["name"], t.get("short_name")]):
            norm_full = _normalize(full)
            searchable.setdefault(norm_full, t)
            for token in norm_full.split():
                if len(token) >= 4:
                    searchable.setdefault(token, t)

    close = difflib.get_close_matches(query_n, list(searchable.keys()), n=1, cutoff=_FUZZY_CUTOFF)
    if close:
        return searchable[close[0]]

    return None
