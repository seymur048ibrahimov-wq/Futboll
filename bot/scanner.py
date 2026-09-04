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


def current_season() -> int:
    now = datetime.now(timezone.utc)
    # European club seasons: season "year" is the year it starts (Aug–May).
    return now.year if now.month >= 7 else now.year - 1


def run_daily_scan(api_key: str):
    """Returns (cards, diagnostics). cards is the formatted match card list
    (0 or 1 items). diagnostics explains what happened during the scan so
    a 'no signal' result can be told apart from a broken pipeline."""
    init_db()
    season = current_season()
    all_predictions = []

    diag = {
        "countries_checked": 0,
        "countries_failed": 0,
        "competitions_checked": 0,
        "fixtures_seen": 0,
        "fixtures_failed": 0,
        "predictions_built": 0,
        "predictions_below_watch": 0,
    }

    for country in CORE_COUNTRIES:
        diag["countries_checked"] += 1
        try:
            competitions = discover_competitions(api_key, country, season)
        except Exception as exc:
            diag["countries_failed"] += 1
            logger.warning("Competition discovery failed for %s: %s", country, exc)
            continue

        for comp in competitions[:MAX_COMPETITIONS_PER_COUNTRY]:
            diag["competitions_checked"] += 1
            try:
                fixtures = fetch_upcoming_matches(
                    api_key, comp["id"], season, next_games=MAX_FIXTURES_PER_COMPETITION
                )
            except Exception as exc:
                logger.warning("Fixture fetch failed for %s (%s): %s", comp["name"], country, exc)
                continue

            for fx in fixtures:
                if not fx.get("home_id") or not fx.get("away_id"):
                    continue
                diag["fixtures_seen"] += 1
                try:
                    match = build_match_features(api_key, fx, comp["id"], season)
                    prediction = predict(match)
                except Exception as exc:
                    diag["fixtures_failed"] += 1
                    logger.warning(
                        "Feature build/predict failed for %s vs %s: %s",
                        fx.get("home"), fx.get("away"), exc,
                    )
                    continue

                diag["predictions_built"] += 1

                if prediction["signal"] not in POSTABLE_SIGNALS:
                    diag["predictions_below_watch"] += 1
                    continue

                save(match, prediction)
                all_predictions.append((match, prediction))

    all_predictions.sort(key=lambda mp: (
        {"STRONG": 0, "GOOD": 1, "WATCH": 2}[mp[1]["signal"]],
        -mp[1]["confidence"],
        -mp[1]["match_score"],
    ))

    if not all_predictions:
        return [], diag

    # Only send the single best-vetted match of the day. If nothing meets
    # the quality bar (all_predictions is empty), no message goes out that day.
    best_match, best_prediction = all_predictions[0]
    return [format_match(best_match, best_prediction, 1)], diag
