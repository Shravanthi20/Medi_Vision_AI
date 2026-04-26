from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, required_fields
from .auth import role_required


purchases_bp = Blueprint("purchases", __name__)


@purchases_bp.route("/api/purchases", methods=["GET"])
@role_required("admin", "manager", "user")
def get_purchases():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM purchases").fetchall()
    return jsonify(
        [
            {
                "id": row["id"],
                "supplier": row["supplier"],
                "items": row["items"],
                "amount": row["amount"],
                "date": row["date"],
                "status": row["status"],
                "batch": row["batch"],
                "expiry": row["expiry"],
                "photo": row["photo"],
            }
            for row in rows
        ]
    )


@purchases_bp.route("/api/purchases", methods=["POST"])
@role_required("admin", "manager", "user")
def add_purchase():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["id", "supplier", "items", "amount", "date", "status"])
    if missing:
        return json_error("Missing required purchase fields", 400, missing)

    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO purchases
                (id, supplier, items, amount, date, status, batch, expiry, photo)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["id"],
                    data["supplier"],
                    data["items"],
                    float(data["amount"]),
                    data["date"],
                    data["status"],
                    data.get("batch", ""),
                    data.get("expiry", ""),
                    data.get("photo", ""),
                ),
            )

            supplier_name = str(data.get("supplier", "")).strip()
            if supplier_name:
                existing = conn.execute(
                    "SELECT id FROM suppliers WHERE LOWER(name)=LOWER(?)",
                    (supplier_name,),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE suppliers SET last_order = ? WHERE id = ?",
                        (data["date"], existing["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO suppliers (name, phone, gst, last_order, status)
                        VALUES (?, '', '', ?, 'Active')
                        """,
                        (supplier_name, data["date"]),
                    )

        return jsonify({"status": "success"})
    except (ValueError, TypeError) as err:
        return json_error("Invalid purchase payload", 400, str(err))
    except Exception as err:
        return json_error("Failed to save purchase", 500, str(err))
