"""Builds predictor-ready match feature dicts from football-data.org data.

football-data.org's free tier does not expose shot statistics, real xG, or
injuries. So unlike the old API-Football version, there is no 3-tier xG
strategy here — xg/xga is always computed from each team's own recent
goals-for/against (the same tier the old code called
"fallback_goals_avg"). analysis/uncertainty.py already treats that as the
lowest-confidence xG tier, so signal quality naturally reflects this.

Elo is not provided by the API either — see elo_store.py, which maintains
our own Elo table updated from finished fixtures.

Injuries and confirmed-lineup data aren't available on the free plan, so
those fields are conservative defaults (0 injuries known, lineup not
confirmed) rather than a guess.
"""

from typing import List, Tuple

from data.api_adapter import fetch_team_recent_matches
from data import elo_store

FORM_LOOKBACK = 6            # matches used for recency form / trend
RESULT_HISTORY = 8           # finished matches fetched per team


def _result_points(goals_for: int, goals_against: int) -> int:
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


def _team_recent_results(matches: List[dict], team_id: int, team_name: str) -> Tuple[list, list, list]:
    """Feeds finished results into the shared Elo store and returns
    (form_points, goals_for_list, goals_against_list) for the team's last
    FORM_LOOKBACK matches, oldest first."""
    parsed = []
    for m in matches:
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        score = m.get("score", {}).get("fullTime", {})
        gh, ga = score.get("home"), score.get("away")
        if gh is None or ga is None:
            continue
        parsed.append((m.get("utcDate", ""), home.get("id"), home.get("name"),
                        away.get("name"), gh, ga))

    parsed.sort(key=lambda x: x[0])

    for _, hid, hname, aname, gh, ga in parsed:
        elo_store.apply_result(hname + aname, hname, aname, gh, ga)

    points, gf_list, ga_list = [], [], []
    for _, hid, hname, aname, gh, ga in parsed[-FORM_LOOKBACK:]:
        is_home = hid == team_id
        gf = gh if is_home else ga
        gagainst = ga if is_home else gh
        points.append(_result_points(gf, gagainst))
        gf_list.append(gf)
        ga_list.append(gagainst)

    return points, gf_list, ga_list


def _goal_averages(gf_list: list, ga_list: list) -> Tuple[float, float]:
    if not gf_list:
        return 1.2, 1.2  # league-average-ish default when no history exists yet
    return (
        round(sum(gf_list) / len(gf_list), 3),
        round(sum(ga_list) / len(ga_list), 3),
    )


_FORM_SYMBOLS = {3: "Q", 1: "B", 0: "M"}  # Qalib / Bərabər / Məğlub


def build_team_report(api_key: str, team: dict) -> dict:
    """Standalone team analysis for the /komanda Telegram command — form,
    Elo, goal averages, and a readable list of recent results."""
    matches = fetch_team_recent_matches(api_key, team["id"], RESULT_HISTORY)
    form, gf_list, ga_list = _team_recent_results(matches, team["id"], team["name"])
    gf_avg, ga_avg = _goal_averages(gf_list, ga_list)
    elo = elo_store.get_rating(team["name"])

    form_str = "".join(_FORM_SYMBOLS[p] for p in form) if form else "—"

    finished = [
        m for m in matches
        if m.get("score", {}).get("fullTime", {}).get("home") is not None
    ]
    finished.sort(key=lambda m: m.get("utcDate", ""))

    recent_lines = []
    for m in finished[-RESULT_HISTORY:]:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        gh = m["score"]["fullTime"]["home"]
        ga = m["score"]["fullTime"]["away"]
        recent_lines.append(f"{home} {gh}-{ga} {away}")

    return {
        "name": team["name"],
        "country": team.get("country", ""),
        "elo": round(elo, 1),
        "form": form_str,
        "goals_for_avg": gf_avg,
        "goals_against_avg": ga_avg,
        "recent_matches": recent_lines,
    }


def build_match_features(api_key: str, fixture: dict) -> dict:
    """Turn one fixture (as returned by api_adapter.fetch_scheduled_matches)
    into the full feature dict predictor.predict() expects."""
    home_id = fixture["home_id"]
    away_id = fixture["away_id"]
    home_name = fixture["home"]
    away_name = fixture["away"]

    home_matches = fetch_team_recent_matches(api_key, home_id, RESULT_HISTORY)
    away_matches = fetch_team_recent_matches(api_key, away_id, RESULT_HISTORY)

    home_form, home_gf, home_ga = _team_recent_results(home_matches, home_id, home_name)
    away_form, away_gf, away_ga = _team_recent_results(away_matches, away_id, away_name)

    home_xg, home_xga = _goal_averages(home_gf, home_ga)
    away_xg, away_xga = _goal_averages(away_gf, away_ga)

    home_elo = elo_store.get_rating(home_name)
    away_elo = elo_store.get_rating(away_name)

    return {
        "id": fixture["fixture_id"],
        "league": fixture["league"],
        "home": home_name,
        "away": away_name,
        "home_form": home_form,
        "away_form": away_form,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "home_xga": home_xga,
        "away_xga": away_xga,
        "xg_source": "fallback_goals_avg",
        "home_elo": home_elo,
        "away_elo": away_elo,
        "home_injuries": 0,
        "away_injuries": 0,
        "lineup_confirmed": False,
        "home_attack_adj": 0,
        "away_attack_adj": 0,
        "home_dynamic_rating_adj": 0,
        "away_dynamic_rating_adj": 0,
    }
