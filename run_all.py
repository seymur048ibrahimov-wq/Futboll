"""Single Railway-friendly entry point: runs the Telegram bot (background
thread, polling) and the dashboard web server (main thread, binds $PORT)
in the same process.

Run: python run_all.py
"""

import os
import threading

from dotenv import load_dotenv

load_dotenv()


def _start_telegram_bot():
    from bot.telegram_bot import build_app
    app = build_app()
    # stop_signals must be empty here: signal handlers only work on the
    # main thread, and this runs on a background thread.
    app.run_polling(stop_signals=[])


def main():
    threading.Thread(target=_start_telegram_bot, daemon=True).start()

    from database.api_server import create_app
    flask_app = create_app()
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
