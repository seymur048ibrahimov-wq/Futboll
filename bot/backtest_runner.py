"""Leak-free walk-forward backtest against real API-Football history.

CRITICAL DESIGN RULE: every feature used to predict match N must come only
from matches that finished BEFORE match N. Concretely:

  - Elo: starts every team at BASE_ELO, updated match-by-match in fixture
    order; a team's rating going into match N reflects only matches 1..N-1.
  - Form: rolling last-6 result points, from matches before N only.
  - xG/xGA: rolling last-5 samples (real API xG if present, else a
    shot-based estimate, else a static 1.2/1.2 default for early-season
    matches with no history yet) from matches before N only.

This costs two API calls per fixture (fixtures list once, then one
/fixtures/statistics call per match) rather than the live pipeline's
per-scan lookups, so a full league season (~380 matches) is a few hundred
requests — mind your plan's rate limits.

Usage:
    python -m bot.backtest_runner --league "Premier League" --season 2024
"""

import argparse
import os
from collections import defaultdict, deque

from dotenv import load_dotenv

from config import LEAGUES
from data.api_adapter import _get, api_key_from_env
from data.elo_store import BASE_ELO, compute_delta
from analysis.backtest import walk_forward

DEFAULT_XG = 1.2
FORM_LOOKBACK = 6
XG_LOOKBACK = 5


def _fetch_season_fixtures(api_key: str, league_id: int, season: int) -> list:
    data = _get(api_key, "/fixtures", {"league": league_id, "season": season})
    finished = [
        item for item in data.get("response", [])
        if item["fixture"]["status"]["short"] == "FT"
    ]
    return sorted(finished, key=lambda x: x["fixture"]["timestamp"])


def _fetch_fixture_stats(api_key: str, fixture_id: int) -> dict:
    """Both teams' stats from one call. Keyed by team_id."""
    try:
        data = _get(api_key, "/fixtures/statistics", {"fixture": fixture_id})
    except Exception:
        return {}
    out = {}
    for entry in data.get("response", []):
        team_id = entry.get("team", {}).get("id")
        raw = {(s.get("type") or "").strip().lower(): s.get("value") for s in entry.get("statistics", [])}

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

        out[team_id] = {
            "expected_goals": num("expected_goals", "expected goals", "xg"),
            "shots_on_goal": num("shots on goal", "shots on target"),
            "total_shots": num("total shots"),
            "shots_inside_box": num("shots insidebox", "shots inside box"),
            "shots_outside_box": num("shots outsidebox", "shots outside box"),
        }
    return out


def _shot_based_xg_estimate(stats: dict):
    inside = stats.get("shots_inside_box")
    outside = stats.get("shots_outside_box")
    if inside is not None or outside is not None:
        return round(0.11 * (inside or 0) + 0.035 * (outside or 0), 3)
    on_goal = stats.get("shots_on_goal")
    total = stats.get("total_shots")
    if on_goal is not None and total is not None:
        return round(0.10 * on_goal + 0.02 * max(total - on_goal, 0), 3)
    return None


def _rolling_xg_source(samples: list) -> str:
    if not samples:
        return "fallback_goals_avg"
    if all(s["real"] for s in samples):
        return "api"
    return "estimated"


def build_backtest_dataset(api_key: str, league_id: int, season: int) -> list:
    fixtures = _fetch_season_fixtures(api_key, league_id, season)

    elo = defaultdict(lambda: BASE_ELO)
    form_history = defaultdict(lambda: deque(maxlen=FORM_LOOKBACK))
    xg_for_history = defaultdict(lambda: deque(maxlen=XG_LOOKBACK))
    xg_against_history = defaultdict(lambda: deque(maxlen=XG_LOOKBACK))

    dataset = []

    for item in fixtures:
        fx = item["fixture"]
        teams = item["teams"]
        goals = item.get("goals", {})
        home_id, away_id = teams["home"]["id"], teams["away"]["id"]
        home_name, away_name = teams["home"]["name"], teams["away"]["name"]
        gh, ga = goals.get("home"), goals.get("away")
        if gh is None or ga is None:
            continue

        # --- Build features from PRE-match state only ---
        def avg_or_default(dq):
            return round(sum(x["value"] for x in dq) / len(dq), 3) if dq else DEFAULT_XG

        match_features = {
            "id": fx["id"],
            "league": item.get("league", {}).get("name"),
            "home": home_name,
            "away": away_name,
            "home_form": list(form_history[home_id]),
            "away_form": list(form_history[away_id]),
            "home_xg": avg_or_default(xg_for_history[home_id]),
            "away_xg": avg_or_default(xg_for_history[away_id]),
            "home_xga": avg_or_default(xg_against_history[home_id]),
            "away_xga": avg_or_default(xg_against_history[away_id]),
            "xg_source": _rolling_xg_source(
                list(xg_for_history[home_id]) + list(xg_for_history[away_id])
            ),
            "home_elo": elo[home_id],
            "away_elo": elo[away_id],
            "home_injuries": 0,   # historical injury data isn't reconstructable via this API
            "away_injuries": 0,
            "lineup_confirmed": True,
            "home_attack_adj": 0,
            "away_attack_adj": 0,
            "home_dynamic_rating_adj": 0,
            "away_dynamic_rating_adj": 0,
            "result": "H" if gh > ga else ("A" if gh < ga else "D"),
        }
        dataset.append(match_features)

        # --- Update rolling state AFTER using it for this match ---
        form_history[home_id].append(3 if gh > ga else (1 if gh == ga else 0))
        form_history[away_id].append(3 if ga > gh else (1 if gh == ga else 0))

        stats = _fetch_fixture_stats(api_key, fx["id"])
        home_stats = stats.get(home_id, {})
        away_stats = stats.get(away_id, {})

        def xg_sample(team_stats):
            if team_stats.get("expected_goals") is not None:
                return {"value": team_stats["expected_goals"], "real": True}
            est = _shot_based_xg_estimate(team_stats)
            if est is not None:
                return {"value": est, "real": False}
            return None

        h_for = xg_sample(home_stats)
        a_for = xg_sample(away_stats)
        if h_for:
            xg_for_history[home_id].append(h_for)
            xg_against_history[away_id].append(h_for)  # what home generated = away conceded
        if a_for:
            xg_for_history[away_id].append(a_for)
            xg_against_history[home_id].append(a_for)

        delta = compute_delta(elo[home_id], elo[away_id], gh, ga)
        elo[home_id] += delta
        elo[away_id] -= delta

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Leak-free FootballAI V3 backtest")
    parser.add_argument("--league", help="League name from config.LEAGUES, e.g. 'Premier League'")
    parser.add_argument("--league-id", type=int, help="Raw API-Football league id (overrides --league)")
    parser.add_argument("--season", type=int, required=True, help="Season start year, e.g. 2024")
    args = parser.parse_args()

    load_dotenv()
    api_key = api_key_from_env()

    if args.league_id:
        league_id = args.league_id
        league_label = str(league_id)
    elif args.league:
        if args.league not in LEAGUES:
            raise SystemExit(f"Unknown league '{args.league}'. Options: {list(LEAGUES)}")
        league_id = LEAGUES[args.league]
        league_label = args.league
    else:
        raise SystemExit("Provide --league or --league-id")

    print(f"Fetching {league_label} season {args.season} history...")
    dataset = build_backtest_dataset(api_key, league_id, args.season)
    print(f"Built {len(dataset)} leak-free match samples.\n")

    result = walk_forward(dataset)
    print("=== Walk-forward backtest ===")
    for k, v in result.items():
        print(f"{k}: {v}")

    by_source = defaultdict(list)
    for m in dataset:
        by_source[m["xg_source"]].append(m)
    print("\n=== xG source breakdown ===")
    for src, matches in by_source.items():
        print(f"{src}: {len(matches)} matches")


if __name__ == "__main__":
    main()
