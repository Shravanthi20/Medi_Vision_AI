import json
from typing import Any

import sqlite3
from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, normalize_bill_row, required_fields, table_columns


bills_bp = Blueprint("bills", __name__)


@bills_bp.route("/api/bills", methods=["GET"])
def get_bills():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM bills ORDER BY ts DESC").fetchall()
    return jsonify([normalize_bill_row(row) for row in rows])


@bills_bp.route("/api/bills", methods=["POST"])
def save_bill():
    data = request.get_json(silent=True) or {}
    required = ["id", "ts", "date", "cust", "phone", "pay", "sub", "disc", "tax", "total", "items"]
    missing = required_fields(data, required)
    if missing:
        return json_error("Missing required bill fields", 400, missing)
    if not isinstance(data["items"], list) or len(data["items"]) == 0:
        return json_error("Bill must include at least one item", 400)

    try:
        with get_conn() as conn:
            bill_cols = table_columns(conn, "bills")
            insert_cols = [
                "id",
                "ts",
                "date",
                "cust",
                "phone",
                "pay",
                "sub",
                "disc",
                "tax",
                "total",
                "items",
                "doctor",
            ]
            insert_values: list[Any] = [
                data["id"],
                data["ts"],
                data["date"],
                data["cust"],
                data["phone"],
                data["pay"],
                data["sub"],
                data["disc"],
                data["tax"],
                data["total"],
                json.dumps(data["items"]),
                data.get("doctor", "Self"),
            ]
            if "rx" in bill_cols:
                insert_cols.append("rx")
                insert_values.append(data.get("rx", ""))
            if "prescription" in bill_cols:
                insert_cols.append("prescription")
                insert_values.append(data.get("prescription", ""))

            placeholders = ",".join(["?"] * len(insert_cols))
            conn.execute(
                f"INSERT INTO bills ({','.join(insert_cols)}) VALUES ({placeholders})",
                tuple(insert_values),
            )

            customer_name = str(data["cust"]).strip()
            customer_phone = str(data["phone"]).strip()
            face_vector = data.get("face_vector", "")
            total_value = float(data["total"])
            customer = conn.execute(
                "SELECT * FROM customers WHERE LOWER(name)=LOWER(?)",
                (customer_name,),
            ).fetchone()
            if customer:
                update_parts = ["visits = visits + 1", "total = total + ?"]
                update_values: list[Any] = [total_value]
                if face_vector and not customer["face_vector"]:
                    update_parts.append("face_vector = ?")
                    update_values.append(face_vector)
                update_values.append(customer["id"])
                conn.execute(
                    f"UPDATE customers SET {', '.join(update_parts)} WHERE id = ?",
                    tuple(update_values),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO customers (name, phone, visits, total, address, email, face_vector)
                    VALUES (?, ?, 1, ?, '', '', ?)
                    """,
                    (customer_name, customer_phone, total_value, face_vector),
                )

            doctor_name = str(data.get("doctor", "Self")).strip()
            if doctor_name and doctor_name.lower() != "self":
                doctor = conn.execute(
                    "SELECT id FROM doctors WHERE LOWER(name)=LOWER(?)",
                    (doctor_name,),
                ).fetchone()
                if not doctor:
                    conn.execute(
                        """
                        INSERT INTO doctors (name, specialty, hospital, phone, email)
                        VALUES (?, '', '', '', '')
                        """,
                        (doctor_name,),
                    )

            for item in data["items"]:
                med_id = str(item.get("id", "")).strip()
                qty = int(item.get("qty", 0) or 0)
                if not med_id or qty <= 0:
                    continue
                med = conn.execute("SELECT s FROM medicines WHERE id = ?", (med_id,)).fetchone()
                if not med:
                    continue
                current_stock = int(med["s"] or 0)
                next_stock = max(0, current_stock - qty)
                conn.execute("UPDATE medicines SET s = ? WHERE id = ?", (next_stock, med_id))

        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return json_error("Bill ID already exists", 409, {"id": data.get("id")})
    except (ValueError, TypeError) as err:
        return json_error("Invalid bill data", 400, str(err))
    except Exception as err:
        return json_error("Failed to save bill", 500, str(err))
