"""Daily scan pipeline: live fixtures -> full features -> predictions.

Kept separate from telegram_bot.py so it can also be run/tested headless.
"""

import logging
from datetime import datetime, timezone

from config import CORE_COUNTRIES
from data.api_adapter import discover_competitions, fetch_upcoming_matches
from data.stats_provider import build_match_features
from models.predictor import predict
from analysis.ranking import format_match
from database.db import init_db, save

logger = logging.getLogger("footballai.scanner")

# Only these signal tiers get posted to the channel — NO SIGNAL is dropped.
POSTABLE_SIGNALS = {"STRONG", "GOOD", "WATCH"}

# Safety cap so one scan can't burn the whole API quota if a country has
# many secondary competitions discovered.
MAX_COMPETITIONS_PER_COUNTRY = 4
MAX_FIXTURES_PER_COMPETITION = 5

# When nothing clears the normal signal bar, send at most this many
# best-effort candidates instead of staying silent for the day.
FALLBACK_MAX = 3


def current_season() -> int:
    now = datetime.now(timezone.utc)
    # European club seasons: season "year" is the year it starts (Aug–May).
    return now.year if now.month >= 7 else now.year - 1


def run_daily_scan(api_key: str) -> tuple[list[str], dict]:
    """Returns (cards, diagnostics).

    diagnostics keeps real error text (not just counts) so the caller can
    show the person exactly why nothing was found, without needing to open
    Railway's logs separately.
    """
    init_db()
    season = current_season()
    evaluated = []  # every (match, prediction) pair, regardless of signal
    diag = {
        "countries_checked": 0,
        "countries_failed": 0,
        "competitions_checked": 0,
        "fixtures_found": 0,
        "predict_errors": 0,
        "errors": [],  # up to a handful of real "<where>: <exception text>" strings
    }

    def _log_error(where: str, exc: Exception):
        msg = f"{where}: {exc}"
        logger.warning(msg)
        if len(diag["errors"]) < 5:
            diag["errors"].append(msg)

    for country in CORE_COUNTRIES:
        diag["countries_checked"] += 1
        try:
            competitions = discover_competitions(api_key, country, season)
        except Exception as exc:
            diag["countries_failed"] += 1
            _log_error(f"Competition discovery failed for {country}", exc)
            continue

        for comp in competitions[:MAX_COMPETITIONS_PER_COUNTRY]:
            diag["competitions_checked"] += 1
            try:
                fixtures = fetch_upcoming_matches(
                    api_key, comp["id"], season, next_games=MAX_FIXTURES_PER_COMPETITION
                )
            except Exception as exc:
                _log_error(f"Fixture fetch failed for {comp['name']} ({country})", exc)
                continue

            diag["fixtures_found"] += len(fixtures)

            for fx in fixtures:
                if not fx.get("home_id") or not fx.get("away_id"):
                    continue
                try:
                    match = build_match_features(api_key, fx, comp["id"], season)
                    prediction = predict(match)
                except Exception as exc:
                    diag["predict_errors"] += 1
                    _log_error(f"Feature build/predict failed for {fx.get('home')} vs {fx.get('away')}", exc)
                    continue

                evaluated.append((match, prediction))
                if prediction["signal"] in POSTABLE_SIGNALS:
                    save(match, prediction)

    diag["evaluated"] = len(evaluated)
    postable = [mp for mp in evaluated if mp[1]["signal"] in POSTABLE_SIGNALS]

    if postable:
        postable.sort(key=lambda mp: (
            {"STRONG": 0, "GOOD": 1, "WATCH": 2}[mp[1]["signal"]],
            -mp[1]["confidence"],
            -mp[1]["match_score"],
        ))
        return [format_match(m, p, i + 1) for i, (m, p) in enumerate(postable)], diag

    if not evaluated:
        # Genuinely nothing to say — no fixtures today / everything failed.
        return [], diag

    # Nothing cleared the normal quality bar. Rather than sending silence,
    # surface the best 1-3 candidates but mark them clearly as low-confidence
    # so they're never confused with a real STRONG/GOOD/WATCH pick.
    evaluated.sort(key=lambda mp: (-mp[1]["confidence"], -mp[1]["match_score"]))
    fallback = evaluated[:FALLBACK_MAX]
    for _, p in fallback:
        p["fallback"] = True
    return [format_match(m, p, i + 1) for i, (m, p) in enumerate(fallback)], diag
