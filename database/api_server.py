import sqlite3
from flask import Flask, jsonify

DB = "footballai_v3.db"


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/predictions")
    def predictions():
        try:
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT 50"
            )
            rows = [dict(r) for r in cur.fetchall()]
            con.close()
            return jsonify(rows)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app
