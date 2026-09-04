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

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.scanner import run_daily_scan

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


def _diag_text(diag: dict) -> str:
    lines = [
        "🔍 Diaqnostika:",
        f"• Yoxlanılan ölkə: {diag['countries_checked']} (uğursuz: {diag['countries_failed']})",
        f"• Yoxlanılan liqa/yarış: {diag['competitions_checked']}",
        f"• Tapılan fikstür: {diag['fixtures_found']} (feature/predict xətası: {diag['predict_errors']})",
        f"• Qiymətləndirilən matç: {diag['evaluated']}",
    ]
    if diag["errors"]:
        lines.append("")
        lines.append("❗ Əsl xəta mətni (son 5-ə qədər):")
        for e in diag["errors"]:
            lines.append(f"  - {e}")
    return "\n".join(lines)


async def _send_scan(bot, chat_id: str, api_key: str):
    cards, diag = run_daily_scan(api_key)
    if not cards:
        await bot.send_message(
            chat_id=chat_id,
            text="📭 Bu gün siqnal veriləcək uyğun matç tapılmadı.\n\n" + _diag_text(diag),
        )
        return
    header = f"⚽ *FootballAI V3 — Günlük Proqnozlar* ({len(cards)} matç)\n🚫 Bukmeyker MODELƏ DAXİL DEYİL"
    await bot.send_message(chat_id=chat_id, text=header, parse_mode="Markdown")
    for batch in _batch_cards(cards):
        await bot.send_message(chat_id=chat_id, text=batch)
    if diag["countries_failed"] or diag["predict_errors"]:
        await bot.send_message(chat_id=chat_id, text=_diag_text(diag))


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    api_key = os.environ["API_FOOTBALL_KEY"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    try:
        await _send_scan(context.bot, chat_id, api_key)
    except Exception as exc:
        logger.exception("Daily scan failed")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Scan xətası: {exc}")


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger: /scan — lets you test without waiting for the schedule."""
    api_key = os.environ["API_FOOTBALL_KEY"]
    await update.message.reply_text("🔎 Skan başladı, bir neçə dəqiqə çəkə bilər...")
    await _send_scan(context.bot, update.effective_chat.id, api_key)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FootballAI V3 botu aktivdir.\n"
        "/scan — indi əl ilə skan et\n"
        "Gündəlik skan avtomatik planlaşdırılıb."
    )


def _utc_time(hour: int):
    from datetime import time, timezone
    return time(hour=hour, minute=0, tzinfo=timezone.utc)


def build_app() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("scan", scan_command))

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
