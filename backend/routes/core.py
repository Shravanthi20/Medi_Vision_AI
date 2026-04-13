from datetime import datetime

from flask import Blueprint, jsonify, render_template, send_file

from ..config import DB_PATH
from ..db import get_conn


core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@core_bp.route("/api/health", methods=["GET"])
def api_health():
    with get_conn() as conn:
        med_count = conn.execute("SELECT COUNT(*) AS c FROM medicines").fetchone()["c"]
        bill_count = conn.execute("SELECT COUNT(*) AS c FROM bills").fetchone()["c"]
        now = datetime.utcnow().isoformat() + "Z"
    return jsonify(
        {
            "status": "ok",
            "database_path": DB_PATH,
            "medicines": med_count,
            "bills": bill_count,
            "time_utc": now,
        }
    )


@core_bp.route("/api/backup")
def backup_db():
    return send_file(DB_PATH, as_attachment=True)
