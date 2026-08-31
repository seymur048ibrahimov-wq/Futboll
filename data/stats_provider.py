"""Builds predictor-ready match feature dicts from live API-Football data.

xG STRATEGY (3 tiers, checked in order per team):
  1. REAL xG   — if API-Football exposes an "expected_goals" statistic for a
                 team's recent fixtures (only available for some leagues/
                 seasons), we use the average of those real values.
  2. ESTIMATED — if no real xG is exposed but shot statistics are (shots on
                 goal, shots inside/outside the box), we compute a simple
                 shot-based xG estimate from those.
  3. FALLBACK  — if neither is available (stats endpoint empty/unsupported),
                 we fall back to the team's season average goals-for/against.

Whichever tier is used is recorded in match["xg_source"] as one of
"api" / "estimated" / "fallback_goals_avg". analysis/uncertainty.py reads
this and lowers the data-quality score accordingly — real xG costs nothing,
an estimate costs one quality point, and the goals-average fallback costs
two, since it carries the least information about actual chance quality.

Elo is not provided by the API either — see elo_store.py, which maintains
our own Elo table updated from finished fixtures.
"""

from typing import Dict, List, Optional

from data.api_adapter import _get
from data import elo_store

FORM_LOOKBACK = 6            # matches used for recency form / trend
RESULT_HISTORY_FOR_ELO = 15  # finished matches per team scanned to backfill Elo
FIXTURES_FOR_XG = 5          # finished matches sampled per team for xG (API-call heavy)

# Quality tier ranking, worst wins when combining two teams' sources.
_XG_TIER_RANK = {"api": 0, "estimated": 1, "fallback_goals_avg": 2}


def _result_points(goals_for: int, goals_against: int) -> int:
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


def _team_last_fixtures(api_key: str, team_id: int, count: int, status: str = "FT") -> list:
    data = _get(api_key, "/fixtures", {"team": team_id, "last": count})
    out = []
    for item in data.get("response", []):
        fx = item.get("fixture", {})
        if status and fx.get("status", {}).get("short") != status:
            continue
        out.append(item)
    return sorted(out, key=lambda x: x["fixture"]["timestamp"])


def _form_and_backfill_elo(fixtures: list, team_name: str) -> list:
    """Feed finished results into the shared Elo store and return last-N
    result points (oldest→newest) for recency-form / trend."""
    for item in fixtures:
        fx = item["fixture"]
        teams = item["teams"]
        goals = item.get("goals", {})
        gh, ga = goals.get("home"), goals.get("away")
        if gh is None or ga is None:
            continue
        elo_store.apply_result(fx["id"], teams["home"]["name"], teams["away"]["name"], gh, ga)

    recent = fixtures[-FORM_LOOKBACK:]
    points = []
    for item in recent:
        teams = item["teams"]
        goals = item.get("goals", {})
        is_home = teams["home"]["name"] == team_name
        gf = goals.get("home") if is_home else goals.get("away")
        ga = goals.get("away") if is_home else goals.get("home")
        if gf is None or ga is None:
            continue
        points.append(_result_points(gf, ga))
    return points


def _fixture_team_stats(api_key: str, fixture_id: int, team_id: int) -> Dict[str, float]:
    """Raw per-match stat values for one team in one fixture, keyed by our
    own short names. Missing values are simply absent from the dict."""
    try:
        data = _get(api_key, "/fixtures/statistics", {"fixture": fixture_id, "team": team_id})
    except Exception:
        return {}
    response = data.get("response", [])
    if not response:
        return {}
    raw = {(s.get("type") or "").strip().lower(): s.get("value") for s in response[0].get("statistics", [])}

    def num(*keys):
        for k in keys:
            v = raw.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return None

    return {
        "expected_goals": num("expected_goals", "expected goals", "xg"),
        "shots_on_goal": num("shots on goal", "shots on target"),
        "total_shots": num("total shots"),
        "shots_inside_box": num("shots insidebox", "shots inside box"),
        "shots_outside_box": num("shots outsidebox", "shots outside box"),
    }


def _shot_based_xg_estimate(stats: Dict[str, float]) -> Optional[float]:
    """Simple, transparent shot-location-weighted xG estimate. Not a
    substitute for a real shot-quality model — just better than a flat
    goals average when real xG isn't exposed by the API."""
    inside = stats.get("shots_inside_box")
    outside = stats.get("shots_outside_box")
    if inside is not None or outside is not None:
        return round(0.11 * (inside or 0) + 0.035 * (outside or 0), 3)

    on_goal = stats.get("shots_on_goal")
    total = stats.get("total_shots")
    if on_goal is not None and total is not None:
        off_target = max(total - on_goal, 0)
        return round(0.10 * on_goal + 0.02 * off_target, 3)

    return None


def _season_goal_average(api_key: str, team_id: int, league_id: int, season: int) -> Dict[str, float]:
    data = _get(api_key, "/teams/statistics", {"team": team_id, "league": league_id, "season": season})
    goals = data.get("response", {}).get("goals", {})
    gf = goals.get("for", {}).get("average", {}).get("total")
    ga = goals.get("against", {}).get("average", {}).get("total")
    try:
        gf = float(gf) if gf is not None else 1.2
    except (TypeError, ValueError):
        gf = 1.2
    try:
        ga = float(ga) if ga is not None else 1.2
    except (TypeError, ValueError):
        ga = 1.2
    return {"for": gf, "against": ga}


def _team_xg_and_xga(
    api_key: str, team_id: int, league_id: int, season: int, fixtures: list
) -> Dict[str, object]:
    """Returns {"xg":..., "xga":..., "source": "api"|"estimated"|"fallback_goals_avg"}.

    For each of the team's last few finished fixtures we pull its own stats
    (for xG) and its opponent's stats in that same fixture (for xGA, i.e.
    what the opponent generated against this team's defense).
    """
    sample = fixtures[-FIXTURES_FOR_XG:]

    real_for, real_against = [], []
    est_for, est_against = [], []

    for item in sample:
        fx_id = item["fixture"]["id"]
        teams = item["teams"]
        is_home = teams["home"]["id"] == team_id
        own_id = team_id
        opp_id = teams["away"]["id"] if is_home else teams["home"]["id"]

        own_stats = _fixture_team_stats(api_key, fx_id, own_id)
        opp_stats = _fixture_team_stats(api_key, fx_id, opp_id)

        if own_stats.get("expected_goals") is not None:
            real_for.append(own_stats["expected_goals"])
        else:
            est = _shot_based_xg_estimate(own_stats)
            if est is not None:
                est_for.append(est)

        if opp_stats.get("expected_goals") is not None:
            real_against.append(opp_stats["expected_goals"])
        else:
            est = _shot_based_xg_estimate(opp_stats)
            if est is not None:
                est_against.append(est)

    if real_for and real_against:
        return {
            "xg": round(sum(real_for) / len(real_for), 3),
            "xga": round(sum(real_against) / len(real_against), 3),
            "source": "api",
        }

    if est_for or est_against:
        fallback_avg = _season_goal_average(api_key, team_id, league_id, season)
        xg = round(sum(est_for) / len(est_for), 3) if est_for else fallback_avg["for"]
        xga = round(sum(est_against) / len(est_against), 3) if est_against else fallback_avg["against"]
        return {"xg": xg, "xga": xga, "source": "estimated"}

    fallback_avg = _season_goal_average(api_key, team_id, league_id, season)
    return {"xg": fallback_avg["for"], "xga": fallback_avg["against"], "source": "fallback_goals_avg"}


def _team_injury_count(api_key: str, team_id: int) -> int:
    try:
        data = _get(api_key, "/injuries", {"team": team_id})
        return len(data.get("response", []))
    except Exception:
        # Injuries endpoint can be quota-limited on lower plans; degrade gracefully.
        return 0


def _lineup_confirmed(api_key: str, fixture_id: int) -> bool:
    try:
        data = _get(api_key, "/fixtures/lineups", {"fixture": fixture_id})
        return len(data.get("response", [])) > 0
    except Exception:
        return False


def build_match_features(api_key: str, fixture: dict, league_id: int, season: int) -> dict:
    """Turn one fixture (as returned by api_adapter.fetch_upcoming_matches) into
    the full feature dict predictor.predict() expects.
    """
    home_id = fixture["home_id"]
    away_id = fixture["away_id"]
    home_name = fixture["home"]
    away_name = fixture["away"]

    home_fixtures = _team_last_fixtures(api_key, home_id, RESULT_HISTORY_FOR_ELO)
    away_fixtures = _team_last_fixtures(api_key, away_id, RESULT_HISTORY_FOR_ELO)

    home_form = _form_and_backfill_elo(home_fixtures, home_name)
    away_form = _form_and_backfill_elo(away_fixtures, away_name)

    home_xg = _team_xg_and_xga(api_key, home_id, league_id, season, home_fixtures)
    away_xg = _team_xg_and_xga(api_key, away_id, league_id, season, away_fixtures)

    # Worst tier of the two teams determines the match-level xG data-quality flag.
    xg_source = max([home_xg["source"], away_xg["source"]], key=lambda s: _XG_TIER_RANK[s])

    home_injuries = _team_injury_count(api_key, home_id)
    away_injuries = _team_injury_count(api_key, away_id)

    home_elo = elo_store.get_rating(home_name)
    away_elo = elo_store.get_rating(away_name)

    # Mild heuristic: each missing key player shaves a little off attacking output.
    home_attack_adj = round(-0.02 * home_injuries, 3)
    away_attack_adj = round(-0.02 * away_injuries, 3)

    lineup_confirmed = _lineup_confirmed(api_key, fixture["fixture_id"])

    return {
        "id": fixture["fixture_id"],
        "league": fixture["league"],
        "home": home_name,
        "away": away_name,
        "home_form": home_form,
        "away_form": away_form,
        "home_xg": home_xg["xg"],
        "away_xg": away_xg["xg"],
        "home_xga": home_xg["xga"],
        "away_xga": away_xg["xga"],
        "xg_source": xg_source,
        "home_elo": home_elo,
        "away_elo": away_elo,
        "home_injuries": home_injuries,
        "away_injuries": away_injuries,
        "lineup_confirmed": lineup_confirmed,
        "home_attack_adj": home_attack_adj,
        "away_attack_adj": away_attack_adj,
        "home_dynamic_rating_adj": 0,
        "away_dynamic_rating_adj": 0,
    }
