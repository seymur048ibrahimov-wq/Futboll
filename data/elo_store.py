"""Self-maintained Elo ratings.

API-Football does not expose Elo ratings, so V3 keeps its own Elo table in
SQLite and updates it from finished fixtures. New teams start at BASE_ELO.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "footballai_v3.db"
BASE_ELO = 1500
K_FACTOR = 24
HOME_ADVANTAGE = 55  # Elo points added to the home side before expectation


def compute_delta(r_home: float, r_away: float, home_goals: int, away_goals: int) -> float:
    """Pure Elo update math, shared with the backtest so both use identical
    formulas. Returns the point delta applied to the home side (away gets -delta)."""
    expected_home = 1 / (1 + 10 ** (-((r_home + HOME_ADVANTAGE) - r_away) / 400))
    if home_goals > away_goals:
        score_home = 1.0
    elif home_goals == away_goals:
        score_home = 0.5
    else:
        score_home = 0.0
    goal_diff = abs(home_goals - away_goals)
    mov_mult = 1.0 if goal_diff <= 1 else (1.5 if goal_diff == 2 else 1.75)
    return K_FACTOR * mov_mult * (score_home - expected_home)


def init_elo_table():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS elo_ratings(
        team TEXT PRIMARY KEY,
        rating REAL NOT NULL,
        matches_played INTEGER NOT NULL DEFAULT 0
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS elo_processed_fixtures(
        fixture_id TEXT PRIMARY KEY
    )""")
    con.commit()
    con.close()


def get_rating(team: str) -> float:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT rating FROM elo_ratings WHERE team=?", (team,)).fetchone()
    con.close()
    return row[0] if row else BASE_ELO


def _set_rating(con, team: str, rating: float, played_delta: int = 1):
    con.execute("""
        INSERT INTO elo_ratings(team, rating, matches_played) VALUES(?,?,?)
        ON CONFLICT(team) DO UPDATE SET
            rating=excluded.rating,
            matches_played=elo_ratings.matches_played+?
    """, (team, rating, played_delta, played_delta))


def apply_result(fixture_id: str, home: str, away: str, home_goals: int, away_goals: int):
    """Update Elo for both teams from one finished match. Idempotent per fixture_id."""
    init_elo_table()
    con = sqlite3.connect(DB_PATH)
    already = con.execute(
        "SELECT 1 FROM elo_processed_fixtures WHERE fixture_id=?", (str(fixture_id),)
    ).fetchone()
    if already:
        con.close()
        return

    home_row = con.execute("SELECT rating FROM elo_ratings WHERE team=?", (home,)).fetchone()
    away_row = con.execute("SELECT rating FROM elo_ratings WHERE team=?", (away,)).fetchone()
    r_home = home_row[0] if home_row else BASE_ELO
    r_away = away_row[0] if away_row else BASE_ELO

    delta = compute_delta(r_home, r_away, home_goals, away_goals)
    _set_rating(con, home, r_home + delta)
    _set_rating(con, away, r_away - delta)
    con.execute("INSERT INTO elo_processed_fixtures(fixture_id) VALUES(?)", (str(fixture_id),))
    con.commit()
    con.close()
