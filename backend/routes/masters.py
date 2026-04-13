from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, required_fields


masters_bp = Blueprint("masters", __name__)


@masters_bp.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM suppliers").fetchall()
    return jsonify(
        [
            {
                "id": row["id"],
                "name": row["name"],
                "phone": row["phone"],
                "gst": row["gst"],
                "last_order": row["last_order"],
                "status": row["status"],
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/suppliers", methods=["POST"])
def add_supplier():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "phone"])
    if missing:
        return json_error("Missing required supplier fields", 400, missing)
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO suppliers (id, name, phone, gst, last_order, status)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    data.get("id"),
                    data["name"],
                    data["phone"],
                    data.get("gst", ""),
                    data.get("last_order", "-"),
                    data.get("status", "Active"),
                ),
            )
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to save supplier", 500, str(err))


@masters_bp.route("/api/customers", methods=["GET"])
def get_customers():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM customers").fetchall()
    return jsonify(
        [
            {
                "id": row["id"],
                "name": row["name"],
                "phone": row["phone"],
                "visits": row["visits"],
                "total_spend": row["total"],
                "address": row["address"],
                "email": row["email"],
                "face_vector": row["face_vector"],
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/customers", methods=["POST"])
def add_customer():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "phone"])
    if missing:
        return json_error("Missing required customer fields", 400, missing)
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO customers
                (id, name, phone, visits, total, address, email, face_vector)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    data.get("id"),
                    data["name"],
                    data["phone"],
                    int(data.get("visits", 1) or 1),
                    float(data.get("total", 0) or 0),
                    data.get("address", ""),
                    data.get("email", ""),
                    data.get("face_vector", ""),
                ),
            )
        return jsonify({"status": "success"})
    except (ValueError, TypeError) as err:
        return json_error("Invalid customer payload", 400, str(err))
    except Exception as err:
        return json_error("Failed to save customer", 500, str(err))


@masters_bp.route("/api/doctors", methods=["GET"])
def get_doctors():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM doctors").fetchall()
    return jsonify(
        [
            {
                "id": row["id"],
                "name": row["name"],
                "specialty": row["specialty"],
                "hospital": row["hospital"],
                "phone": row["phone"],
                "email": row["email"],
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/doctors", methods=["POST"])
def add_doctor():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "specialty", "hospital", "phone"])
    if missing:
        return json_error("Missing required doctor fields", 400, missing)
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO doctors (id, name, specialty, hospital, phone, email)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    data.get("id"),
                    data["name"],
                    data["specialty"],
                    data["hospital"],
                    data["phone"],
                    data.get("email", ""),
                ),
            )
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to save doctor", 500, str(err))


@masters_bp.route("/api/suppliers/<id>", methods=["DELETE"])
def delete_supplier(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@masters_bp.route("/api/customers/<id>", methods=["DELETE"])
def delete_customer(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@masters_bp.route("/api/doctors/<id>", methods=["DELETE"])
def delete_doctor(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors WHERE id = ?", (id,))
    return jsonify({"status": "success"})
