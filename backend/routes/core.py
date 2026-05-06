from datetime import datetime

from flask import Blueprint, jsonify, render_template, session

from .auth import login_required

from ..extensions import db
from ..models.core import Item
from ..models.sales import SalesBill


core_bp = Blueprint("core", __name__)


@core_bp.route("/")
@login_required
def dashboard():
    current_user = {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "name": session.get("name"),
        "role": session.get("role")
    }
    return render_template("dashboard.html", current_user=current_user)


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
