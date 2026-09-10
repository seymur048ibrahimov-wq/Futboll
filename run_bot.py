"""Entry point: load .env, then start the FootballAI V3 Telegram bot."""

from dotenv import load_dotenv

load_dotenv()

from bot.telegram_bot import main

if __name__ == "__main__":
    main()
