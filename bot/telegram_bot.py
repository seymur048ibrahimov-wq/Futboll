"""FootballAI V3 Telegram bot.

Env vars required (put them in .env, never in source code or chat):
    TELEGRAM_BOT_TOKEN   - from @BotFather
    TELEGRAM_CHAT_ID     - channel/group id the daily scan is posted to
                            (e.g. -1001234567890 for a channel, or a group id)
    API_FOOTBALL_KEY     - your API-Football key
    DAILY_SCAN_HOUR_UTC  - optional, default 8 (24h, UTC)

Run:
    python run_bot.py
"""

import logging
import os
import sys
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.scanner import run_daily_scan
from data.team_lookup import find_team, directory_status
from data.stats_provider import build_team_report, build_match_features
from data.api_adapter import fetch_scheduled_matches
from models.predictor import predict
from analysis.ranking import format_team_report, format_match

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,  # keep INFO/DEBUG logs out of stderr so Railway doesn't tag them as errors
)
logger = logging.getLogger("footballai.bot")

TELEGRAM_MSG_LIMIT = 4000  # leave headroom under Telegram's 4096 char limit


def _batch_cards(cards: list[str], limit: int = TELEGRAM_MSG_LIMIT) -> list[str]:
    """Pack formatted match cards into as few messages as possible."""
    batches, current = [], ""
    separator = "\n" + ("=" * 30) + "\n"
    for card in cards:
        candidate = (current + separator + card) if current else card
        if len(candidate) > limit and current:
            batches.append(current)
            current = card
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches


async def _send_scan(bot, chat_id: str, api_key: str):
    cards, diag = run_daily_scan(api_key)
    if not cards:
        if diag.get("fetch_error"):
            reason = f"⚠️ Matçlar çəkilə bilmədi.\n\nXəta: {diag['fetch_error']}"
        else:
            reason = (
                f"📭 Bu gün siqnal veriləcək uyğun matç tapılmadı.\n\n"
                f"🔍 Diaqnostika:\n"
                f"• Yoxlanılan fikstür: {diag['fixtures_seen']} "
                f"(feature/predict xətası: {diag['fixtures_failed']})\n"
                f"• Qiymətləndirilən matç: {diag['predictions_built']}\n"
                f"• WATCH həddini keçməyən: {diag['predictions_below_watch']}"
            )
        await bot.send_message(chat_id=chat_id, text=reason)
        return
    header = f"⚽ *FootballAI V3 — Günlük Proqnozlar* ({len(cards)} matç)\n🚫 Bukmeyker MODELƏ DAXİL DEYİL"
    await bot.send_message(chat_id=chat_id, text=header, parse_mode="Markdown")
    for batch in _batch_cards(cards):
        await bot.send_message(chat_id=chat_id, text=batch)


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY") or os.environ["API_FOOTBALL_KEY"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    try:
        await _send_scan(context.bot, chat_id, api_key)
    except Exception as exc:
        logger.exception("Daily scan failed")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Scan xətası: {exc}")


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger: /scan — lets you test without waiting for the schedule."""
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY") or os.environ["API_FOOTBALL_KEY"]
    await update.message.reply_text("🔎 Skan başladı, bir neçə dəqiqə çəkə bilər...")
    await _send_scan(context.bot, update.effective_chat.id, api_key)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FootballAI V3 botu aktivdir.\n"
        "/scan — indi əl ilə skan et\n"
        "/komanda <ad> — bir komandanı analiz et (məs: /komanda Arsenal)\n"
        "Gündəlik skan avtomatik planlaşdırılıb."
    )


async def _lookup_and_report_team(update: Update, api_key: str, name: str) -> Optional[dict]:
    """Finds one team and sends its report. Returns the team dict on success,
    or None (after already messaging the user) on failure."""
    try:
        team = find_team(api_key, name)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Axtarış zamanı xəta ('{name}'): {exc}")
        return None

    if not team:
        status = directory_status()
        msg = (
            f"'{name}' adlı komanda tapılmadı.\n"
            "Yalnız bu liqalardakı komandalar axtarıla bilər: İngiltərə, İspaniya, "
            "İtaliya, Almaniya, Fransa, Hollandiya, Portuqaliya."
        )
        if status["team_count"] == 0:
            msg += "\n\n⚠️ Komanda bazası boşdur (0 komanda yükləndi)."
            if status["last_errors"]:
                msg += "\n\nXətalar:\n" + "\n".join(f"• {e}" for e in status["last_errors"][:5])
        await update.message.reply_text(msg)
        return None

    return team


async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/komanda <ad> — analyze one team.
    /komanda TeamA-TeamB — if they have a scheduled match, show the full
    prediction card (regardless of WATCH threshold); otherwise send both
    teams' individual reports."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "İstifadə:\n"
            "/komanda <komandanın adı> — Məsələn: /komanda Arsenal\n"
            "/komanda TeamA-TeamB — Məsələn: /komanda Fiorentina-Torino"
        )
        return

    api_key = os.environ.get("FOOTBALL_DATA_API_KEY") or os.environ["API_FOOTBALL_KEY"]

    if "-" in query:
        left, _, right = query.partition("-")
        left, right = left.strip(), right.strip()
        if left and right:
            await update.message.reply_text(f"🔍 '{left}' və '{right}' arasında yoxlanılır...")
            return await _handle_head_to_head(update, api_key, left, right)

    await update.message.reply_text(f"🔍 '{query}' axtarılır...")
    team = await _lookup_and_report_team(update, api_key, query)
    if not team:
        return

    try:
        report = build_team_report(api_key, team)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Analiz zamanı xəta: {exc}")
        return

    await update.message.reply_text(format_team_report(report))


async def _handle_head_to_head(update: Update, api_key: str, left: str, right: str):
    try:
        team_a = find_team(api_key, left)
        team_b = find_team(api_key, right)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Axtarış zamanı xəta: {exc}")
        return

    missing = [n for n, t in [(left, team_a), (right, team_b)] if not t]
    if missing:
        status = directory_status()
        msg = (
            f"Tapılmadı: {', '.join(missing)}.\n"
            "Yalnız bu liqalardakı komandalar axtarıla bilər: İngiltərə, İspaniya, "
            "İtaliya, Almaniya, Fransa, Hollandiya, Portuqaliya."
        )
        if status["team_count"] == 0:
            msg += "\n\n⚠️ Komanda bazası boşdur (0 komanda yükləndi)."
            if status["last_errors"]:
                msg += "\n\nXətalar:\n" + "\n".join(f"• {e}" for e in status["last_errors"][:5])
        await update.message.reply_text(msg)
        return

    try:
        fixtures = fetch_scheduled_matches(api_key)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Fikstürlər çəkilə bilmədi: {exc}")
        return

    ids = {team_a["id"], team_b["id"]}
    match_fx = next(
        (fx for fx in fixtures if {fx["home_id"], fx["away_id"]} == ids),
        None,
    )

    if match_fx:
        try:
            match = build_match_features(api_key, match_fx)
            prediction = predict(match)
        except Exception as exc:
            await update.message.reply_text(f"⚠️ Analiz zamanı xəta: {exc}")
            return
        await update.message.reply_text(
            "🧪 Əl ilə yoxlama (WATCH həddindən asılı olmayaraq göstərilir):\n"
        )
        await update.message.reply_text(format_match(match, prediction, 1))
        return

    await update.message.reply_text(
        f"'{left}' və '{right}' arasında planlaşdırılan matç tapılmadı "
        "(cədvəldə yoxdur, ya da çox uzaq tarixdədir). Ayrı-ayrı hesabatlar göndərilir:"
    )
    for team in (team_a, team_b):
        try:
            report = build_team_report(api_key, team)
            await update.message.reply_text(format_team_report(report))
        except Exception as exc:
            await update.message.reply_text(f"⚠️ '{team['name']}' analiz edilərkən xəta: {exc}")


def _utc_time(hour: int):
    from datetime import time, timezone
    return time(hour=hour, minute=0, tzinfo=timezone.utc)


def build_app() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("komanda", team_command))

    # Default 07:00 UTC = 11:00 Baku time (UTC+4) — inside the requested
    # 10:00-12:00 daily notification window. Override with
    # DAILY_SCAN_HOUR_UTC in .env if you want a different UTC hour.
    hour = int(os.getenv("DAILY_SCAN_HOUR_UTC", "7"))
    if app.job_queue is None:
        raise RuntimeError(
            "JobQueue not available — install with: pip install \"python-telegram-bot[job-queue]\""
        )
    app.job_queue.run_daily(daily_job, time=_utc_time(hour))
    return app


def main():
    app = build_app()
    logger.info("FootballAI V3 bot starting (polling mode)...")
    app.run_polling()


if __name__ == "__main__":
    main()
