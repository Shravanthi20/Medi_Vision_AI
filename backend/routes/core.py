from datetime import datetime

from flask import Blueprint, jsonify, render_template

from ..extensions import db
from ..models.core import Item
from ..models.sales import SalesBill


core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@core_bp.route("/api/health", methods=["GET"])
def api_health():
    med_count = db.session.query(Item).count()
    bill_count = db.session.query(SalesBill).count()
    now = datetime.utcnow().isoformat() + "Z"
    return jsonify(
        {
            "status": "ok",
            "database": "postgres",
            "medicines": med_count,
            "bills": bill_count,
            "time_utc": now,
        }
    )


@core_bp.route("/api/backup")
def backup_db():
    return (
        jsonify(
            {
                "status": "error",
                "message": "File backup is not available in Postgres mode. Use pg_dump based backups.",
            }
        ),
        410,
    )
