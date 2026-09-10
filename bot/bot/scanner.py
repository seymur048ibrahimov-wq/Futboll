"""Daily scan pipeline: scheduled fixtures -> full features -> predictions.

Kept separate from telegram_bot.py so it can also be run/tested headless.
"""

import logging

from config import MAX_TOTAL_FIXTURES_PER_SCAN
from data.api_adapter import fetch_scheduled_matches
from data.stats_provider import build_match_features
from models.predictor import predict
from analysis.ranking import format_match
from database.db import init_db, save

logger = logging.getLogger("footballai.scanner")

# Only these signal tiers get posted to the channel — NO SIGNAL is dropped.
POSTABLE_SIGNALS = {"STRONG", "GOOD", "WATCH"}


def run_daily_scan(api_key: str):
    """Returns (cards, diagnostics). cards is the formatted match card list
    (0 or 1 items). diagnostics explains what happened during the scan so
    a 'no signal' result can be told apart from a broken pipeline."""
    init_db()

    diag = {
        "fixtures_seen": 0,
        "fixtures_failed": 0,
        "predictions_built": 0,
        "predictions_below_watch": 0,
        "fetch_error": None,
    }

    try:
        fixtures = fetch_scheduled_matches(api_key)
    except Exception as exc:
        logger.warning("Scheduled-matches fetch failed: %s", exc)
        diag["fetch_error"] = str(exc)
        return [], diag

    all_predictions = []

    for fx in fixtures[:MAX_TOTAL_FIXTURES_PER_SCAN]:
        diag["fixtures_seen"] += 1
        try:
            match = build_match_features(api_key, fx)
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
