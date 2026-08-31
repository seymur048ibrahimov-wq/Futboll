import sqlite3
from datetime import datetime,timezone

DB="footballai_v3.db"

def init_db():
    con=sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT, home TEXT, away TEXT, league TEXT,
        predicted_at TEXT, home_win REAL, draw_prob REAL, away_win REAL,
        over05 REAL, over15 REAL, over25 REAL, over35 REAL,
        over45 REAL, over55 REAL, over65 REAL, btts REAL,
        match_score REAL, confidence REAL, model_agreement REAL,
        signal TEXT, flags TEXT, xg_source TEXT, actual_result TEXT)""")
    cols = [r[1] for r in con.execute("PRAGMA table_info(predictions)").fetchall()]
    if "xg_source" not in cols:
        con.execute("ALTER TABLE predictions ADD COLUMN xg_source TEXT")
    con.commit(); con.close()

def save(match,p):
    o=p["alt_under"]
    con=sqlite3.connect(DB)
    con.execute("""INSERT INTO predictions
    (match_id,home,away,league,predicted_at,home_win,draw_prob,away_win,
     over05,over15,over25,over35,over45,over55,over65,btts,
     match_score,confidence,model_agreement,signal,flags,xg_source)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (str(match["id"]),match["home"],match["away"],match["league"],
     datetime.now(timezone.utc).isoformat(),p["home_win"],p["draw"],p["away_win"],
     o["0.5"]["over"],o["1.5"]["over"],o["2.5"]["over"],o["3.5"]["over"],
     o["4.5"]["over"],o["5.5"]["over"],o["6.5"]["over"],p["btts"],
     p["match_score"],p["confidence"],p["model_agreement"],p["signal"],
     ",".join(p["uncertainty_flags"]),match.get("xg_source","api")))
    con.commit(); con.close()

def fetch_recent(limit=100):
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    rows=con.execute(
        "SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]
