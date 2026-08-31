"""Quick manual sanity check for the live API-Football adapter.

Run: python api_test.py
Requires API_FOOTBALL_KEY in your environment/.env.
"""

from dotenv import load_dotenv
load_dotenv()

from data.api_adapter import api_key_from_env, discover_competitions
from bot.scanner import current_season
from config import CORE_COUNTRIES

if __name__ == "__main__":
    key = api_key_from_env()
    season = current_season()
    for country in CORE_COUNTRIES:
        print("\n", country)
        comps = discover_competitions(key, country, season)
        for c in comps:
            print(c["id"], "-", c["name"], f"(priority {c['priority']})")
