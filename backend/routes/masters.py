from datetime import datetime
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..db import get_conn, json_error, required_fields
from .auth import role_required


masters_bp = Blueprint("masters", __name__)


@masters_bp.route("/api/suppliers", methods=["GET"])
@role_required("admin", "manager", "user", "junior")
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
@role_required("admin", "manager", "user")
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
@role_required("admin", "manager", "user", "junior")
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
                "balance": row["balance"] if "balance" in row.keys() else 0.0,
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/customers", methods=["POST"])
@role_required("admin", "manager", "user", "junior")
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
@role_required("admin", "manager", "user", "junior")
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
@role_required("admin", "manager", "user", "junior")
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
@role_required("admin", "manager", "user")
def delete_supplier(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@masters_bp.route("/api/customers/<id>", methods=["DELETE"])
@role_required("admin", "manager", "user")
def delete_customer(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@masters_bp.route("/api/customers/<id>/ledger", methods=["GET"])
@role_required("admin", "manager", "user", "junior")
def get_customer_ledger(id):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM ledger_entries WHERE customer_id = ? ORDER BY id ASC", (id,)).fetchall()
    return jsonify([dict(row) for row in rows])


@masters_bp.route("/api/customers/<id>/payment", methods=["POST"])
@role_required("admin", "manager", "user")
def record_customer_payment(id):
    data = request.get_json(silent=True) or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return json_error("Amount must be greater than zero", 400)
    
    try:
        with get_conn() as conn:
            customer = conn.execute("SELECT balance FROM customers WHERE id = ?", (id,)).fetchone()
            if not customer:
                return json_error("Customer not found", 404)
            
            # Since a payment reduces the outstanding balance:
            current_balance = float(customer["balance"] or 0)
            new_balance = current_balance - amount
            
            # Record ledger
            conn.execute(
                """
                INSERT INTO ledger_entries (customer_id, date, ref_type, ref_id, description, debit, credit, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (id, datetime.utcnow().isoformat() + "Z", "Payment", f"PAY-{int(datetime.utcnow().timestamp())}", data.get("description", "Manual Payment"), 0.0, amount, new_balance)
            )
            
            # Update customer
            conn.execute("UPDATE customers SET balance = ? WHERE id = ?", (new_balance, id))
            
        return jsonify({"status": "success", "new_balance": new_balance})
    except Exception as err:
        return json_error("Failed to record payment", 500, str(err))


@masters_bp.route("/api/doctors/<id>", methods=["DELETE"])
@role_required("admin", "manager", "user")
def delete_doctor(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@masters_bp.route("/api/users", methods=["GET"])
@role_required("admin")
def get_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, name, role, code, phone, is_active FROM users").fetchall()
    return jsonify([dict(row) for row in rows])


@masters_bp.route("/api/users", methods=["POST"])
@role_required("admin")
def add_user():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["username", "name", "role", "password"])
    if missing:
        return json_error("Missing required user fields", 400, missing)
    
    password_hash = generate_password_hash(data["password"])
    try:
        with get_conn() as conn:
            if data.get("id"):
                conn.execute(
                    """
                    UPDATE users SET username=?, password_hash=?, name=?, role=?, code=?, phone=?, is_active=?
                    WHERE id=?
                    """,
                    (data["username"], password_hash, data["name"], data["role"], data.get("code", ""), data.get("phone", ""), data.get("is_active", 1), data["id"])
                )
            else:
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, name, role, code, phone, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (data["username"], password_hash, data["name"], data["role"], data.get("code", ""), data.get("phone", ""), data.get("is_active", 1))
                )
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to save user (username might not be unique)", 500, str(err))


@masters_bp.route("/api/users/<id>", methods=["DELETE"])
@role_required("admin")
def delete_user(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (id,))
    return jsonify({"status": "success"})
