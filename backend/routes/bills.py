import json
from typing import Any

from datetime import datetime
import sqlite3
from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, normalize_bill_row, required_fields, safe_json_loads, table_columns
from ..services.whatsapp import send_whatsapp_receipt
from ..sms_service import create_bill_sms_payload, create_sms_message, resolve_customer_row


bills_bp = Blueprint("bills", __name__)


def _bill_items(raw: Any) -> list[dict[str, Any]]:
    items = safe_json_loads(raw, [])
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _get_bill_row(conn, bill_id: str):
    return conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()


def _normalize_name(value: Any) -> str:
    return str(value or "").strip()


def _customer_key(name: str) -> str:
    return _normalize_name(name).lower()


def _find_customer_by_name(conn, name: str):
    name = _normalize_name(name)
    if not name:
        return None
    return conn.execute(
        "SELECT * FROM customers WHERE LOWER(name)=LOWER(?)",
        (name,),
    ).fetchone()


def _adjust_customer_summary(
    conn,
    *,
    name: str,
    phone: str,
    total_delta: float,
    visit_delta: int,
    allow_insert: bool,
    face_vector: str = "",
    balance_delta: float = 0.0,
):
    customer_name = _normalize_name(name)
    customer_phone = _normalize_name(phone)
    if not customer_name:
        return

    customer = _find_customer_by_name(conn, customer_name)
    if customer:
        current_visits = int(customer["visits"] or 0)
        current_total = float(customer["total"] or 0)
        current_bal = float(customer["balance"] or 0) if "balance" in customer.keys() else 0.0
        next_visits = max(0, current_visits + int(visit_delta))
        next_total = max(0.0, current_total + float(total_delta))
        next_bal = current_bal + float(balance_delta)
        update_parts = ["visits = ?", "total = ?", "balance = ?"]
        update_values: list[Any] = [next_visits, next_total, next_bal]
        if customer_phone and not _normalize_name(customer["phone"]):
            update_parts.append("phone = ?")
            update_values.append(customer_phone)
        if face_vector and not _normalize_name(customer["face_vector"]):
            update_parts.append("face_vector = ?")
            update_values.append(face_vector)
        update_values.append(customer["id"])
        conn.execute(
            f"UPDATE customers SET {', '.join(update_parts)} WHERE id = ?",
            tuple(update_values),
        )
        return

    if not allow_insert:
        return

    insert_visits = max(1, int(visit_delta) if int(visit_delta) > 0 else 1)
    insert_total = max(0.0, float(total_delta))
    conn.execute(
        """
        INSERT INTO customers (name, phone, visits, total, address, email, face_vector, balance)
        VALUES (?, ?, ?, ?, '', '', ?, ?)
        """,
        (customer_name, customer_phone, insert_visits, insert_total, face_vector, balance_delta),
    )


def _apply_stock_delta(conn, items: list[dict[str, Any]], quantity_multiplier: int) -> None:
    if not items:
        return

    delta_by_med: dict[str, int] = {}
    for item in items:
        med_id = _normalize_name(item.get("id", ""))
        qty = int(item.get("qty", 0) or 0)
        if not med_id or qty <= 0:
            continue
        delta_by_med[med_id] = delta_by_med.get(med_id, 0) + (qty * quantity_multiplier)

    for med_id, delta in delta_by_med.items():
        med = conn.execute("SELECT s FROM medicines WHERE id = ?", (med_id,)).fetchone()
        if not med:
            continue
        current_stock = int(med["s"] or 0)
        next_stock = max(0, current_stock + delta)
        conn.execute("UPDATE medicines SET s = ? WHERE id = ?", (next_stock, med_id))


def _merge_bill_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        if key == "items" and (not isinstance(value, list) or len(value) == 0):
            continue
        if isinstance(value, str) and not value.strip() and key not in {"doctor", "rx", "prescription"}:
            continue
        merged[key] = value
    if "doctor" not in merged or merged["doctor"] is None:
        merged["doctor"] = "Self"
    if "items" not in merged:
        merged["items"] = existing.get("items", [])
    return merged


def _write_bill_row(conn, bill: dict[str, Any], replace: bool = False) -> None:
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
        "customer_type",
        "bill_type",
        "discount_type",
        "discount_value",
    ]
    insert_values: list[Any] = [
        bill["id"],
        bill["ts"],
        bill["date"],
        bill["cust"],
        bill["phone"],
        bill["pay"],
        bill["sub"],
        bill["disc"],
        bill["tax"],
        bill["total"],
        json.dumps(bill["items"]),
        bill.get("doctor", "Self"),
        bill.get("customer_type", "customer"),
        bill.get("bill_type", "retail"),
        bill.get("discount_type", "pct"),
        bill.get("discount_value", 0),
    ]
    if "rx" in bill_cols:
        insert_cols.append("rx")
        insert_values.append(bill.get("rx", ""))
    if "prescription" in bill_cols:
        insert_cols.append("prescription")
        insert_values.append(bill.get("prescription", ""))

    placeholders = ",".join(["?"] * len(insert_cols))
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    conn.execute(
        f"{verb} INTO bills ({','.join(insert_cols)}) VALUES ({placeholders})",
        tuple(insert_values),
    )


def _bill_customer_changed(existing: dict[str, Any], updated: dict[str, Any]) -> bool:
    return _customer_key(existing.get("cust", "")) != _customer_key(updated.get("cust", ""))


def _build_new_bill(existing_row, incoming: dict[str, Any]) -> dict[str, Any]:
    existing = normalize_bill_row(existing_row)
    merged = _merge_bill_payload(existing, incoming)
    merged["id"] = existing["id"]
    merged["ts"] = incoming.get("ts", existing_row["ts"])
    merged["date"] = incoming.get("date", existing_row["date"])
    merged["cust"] = incoming.get("cust", existing_row["cust"])
    merged["phone"] = incoming.get("phone", existing_row["phone"])
    merged["pay"] = incoming.get("pay", existing_row["pay"])
    merged["sub"] = incoming.get("sub", existing_row["sub"])
    merged["disc"] = incoming.get("disc", existing_row["disc"])
    merged["tax"] = incoming.get("tax", existing_row["tax"])
    merged["total"] = incoming.get("total", existing_row["total"])
    merged["items"] = _bill_items(merged.get("items", existing.get("items", [])))
    merged["doctor"] = incoming.get("doctor", existing_row["doctor"] or "Self")
    merged["customer_type"] = incoming.get("customer_type", existing_row["customer_type"] or "customer")
    merged["bill_type"] = incoming.get("bill_type", existing_row["bill_type"] or "retail")
    merged["discount_type"] = incoming.get("discount_type", existing_row["discount_type"] or "pct")
    merged["discount_value"] = incoming.get("discount_value", existing_row["discount_value"] or 0)
    merged["rx"] = incoming.get("rx", existing_row["rx"] if "rx" in existing_row.keys() else "")
    merged["prescription"] = incoming.get(
        "prescription",
        existing_row["prescription"] if "prescription" in existing_row.keys() else "",
    )
    return merged


@bills_bp.route("/api/bills", methods=["GET"])
def get_bills():
    start_ts = request.args.get("start_date")
    end_ts = request.args.get("end_date")
    customer = request.args.get("customer")
    doctor = request.args.get("doctor")
    medicine = request.args.get("medicine")

    query = "SELECT * FROM bills WHERE 1=1"
    params = []

    if start_ts:
        query += " AND ts >= ?"
        params.append(int(start_ts))
    if end_ts:
        query += " AND ts <= ?"
        params.append(int(end_ts))
    if customer:
        query += " AND LOWER(cust) LIKE ?"
        params.append(f"%{customer.lower()}%")
    if doctor:
        query += " AND LOWER(doctor) LIKE ?"
        params.append(f"%{doctor.lower()}%")
    if medicine:
        query += " AND LOWER(items) LIKE ?"
        params.append(f"%{medicine.lower()}%")

    query += " ORDER BY ts DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify([normalize_bill_row(row) for row in rows])

@bills_bp.route("/api/reports/gst", methods=["GET"])
def get_gst_report():
    start_ts = request.args.get("start_date")
    end_ts = request.args.get("end_date")
    
    query = "SELECT * FROM bills WHERE 1=1"
    params = []
    if start_ts:
        query += " AND ts >= ?"
        params.append(int(start_ts))
    if end_ts:
        query += " AND ts <= ?"
        params.append(int(end_ts))
        
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        
    total_sales = 0
    total_tax = 0
    taxable_amount = 0
    non_taxable_amount = 0
    
    for row in rows:
        b = normalize_bill_row(row)
        total_sales += float(b["total"])
        total_tax += float(b["tax"])
        if float(b["tax"]) > 0:
            taxable_amount += (float(b["sub"]) - float(b["disc"]))
        else:
            non_taxable_amount += (float(b["sub"]) - float(b["disc"]))
            
    return jsonify({
        "total_sales": total_sales,
        "total_tax": total_tax,
        "taxable_amount": taxable_amount,
        "non_taxable_amount": non_taxable_amount,
        "net_revenue": total_sales - total_tax
    })


@bills_bp.route("/api/bills/<bill_id>", methods=["GET"])
def get_bill(bill_id):
    with get_conn() as conn:
        row = _get_bill_row(conn, bill_id)
    if not row:
        return json_error("Bill not found", 404, {"id": bill_id})
    return jsonify(normalize_bill_row(row))


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
            _write_bill_row(conn, data, replace=False)
            is_credit = str(data.get("pay", "")).lower() == "credit"
            balance_delta = float(data["total"]) if is_credit else 0.0

            _adjust_customer_summary(
                conn,
                name=data["cust"],
                phone=data["phone"],
                total_delta=float(data["total"]),
                visit_delta=1,
                allow_insert=True,
                face_vector=data.get("face_vector", ""),
                balance_delta=balance_delta,
            )
            customer_name = str(data["cust"]).strip()
            customer_phone = str(data["phone"]).strip()

            customer_row = resolve_customer_row(conn, None, customer_phone, customer_name)

            if customer_row:
                new_balance = float(customer_row.get("balance", 0)) if customer_row and "balance" in customer_row.keys() else 0.0
                conn.execute(
                    """
                    INSERT INTO ledger_entries (customer_id, date, ref_type, ref_id, description, debit, credit, balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        customer_row["id"], 
                        datetime.utcnow().isoformat() + "Z", 
                        "Sale", 
                        data["id"], 
                        f"Bill #{data['id']} ({data.get('pay', 'cash')})", 
                        float(data["total"]), 
                        0.0 if is_credit else float(data["total"]),
                        new_balance
                    )
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

            _apply_stock_delta(conn, _bill_items(data["items"]), -1)

            try:
                sms_payload = create_bill_sms_payload(conn, data, customer_row)
                if sms_payload:
                    create_sms_message(conn, sms_payload, auto_send=True)
            except Exception:
                pass

            # Send WhatsApp message if phone is provided
            if customer_phone:
                items_str = ""
                for item in data.get("items", []):
                    name = item.get("n", "Item")
                    qty = int(item.get("qty", 1) or 1)
                    price = float(item.get("p", 0) or 0)
                    item_total = qty * price
                    items_str += f"- {name} (Qty: {qty}) : Rs. {item_total:.2f}\n"

                sub = float(data.get("sub", 0) or 0)
                disc = float(data.get("disc", 0) or 0)
                tax = float(data.get("tax", 0) or 0)
                total = float(data.get("total", 0) or 0)

                message_content = (
                    f"Hello {customer_name},\n\n"
                    f"Your bill for Rs. {total:.2f} is ready.\n\n"
                    f"*Purchases:*\n{items_str}\n"
                    f"Subtotal: Rs. {sub:.2f}\n"
                    f"Discount: Rs. {disc:.2f}\n"
                    f"GST: Rs. {tax:.2f}\n"
                    f"*Total: Rs. {total:.2f}*\n\n"
                    f"Thank you for visiting Selvam Medicals! 💊"
                )
                
                whatsapp_res = send_whatsapp_receipt(data["id"], customer_phone, message_content)
                
                conn.execute(
                    """
                    INSERT INTO communication_logs (bill_id, customer_phone, status, message, timestamp, provider_message_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (data["id"], customer_phone, whatsapp_res["status"], message_content, datetime.utcnow().isoformat() + "Z", whatsapp_res["provider_message_id"])
                )

        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return json_error("Bill ID already exists", 409, {"id": data.get("id")})
    except (ValueError, TypeError) as err:
        return json_error("Invalid bill data", 400, str(err))
    except Exception as err:
        return json_error("Failed to save bill", 500, str(err))


@bills_bp.route("/api/bills/<bill_id>", methods=["PATCH", "PUT"])
def update_bill(bill_id):
    data = request.get_json(silent=True) or {}
    try:
        with get_conn() as conn:
            existing_row = _get_bill_row(conn, bill_id)
            if not existing_row:
                return json_error("Bill not found", 404, {"id": bill_id})

            updated = _build_new_bill(existing_row, data)
            required = ["id", "ts", "date", "cust", "phone", "pay", "sub", "disc", "tax", "total", "items"]
            missing = required_fields(updated, required)
            if missing:
                return json_error("Missing required bill fields", 400, missing)
            if not isinstance(updated["items"], list) or len(updated["items"]) == 0:
                return json_error("Bill must include at least one item", 400)

            old_bill = normalize_bill_row(existing_row)
            old_items = _bill_items(old_bill["items"])
            new_items = _bill_items(updated["items"])

            old_is_credit = str(old_bill.get("pay", "")).lower() == "credit"
            old_bal_delta = -float(old_bill["total"]) if old_is_credit else 0.0
            new_is_credit = str(updated.get("pay", "")).lower() == "credit"
            new_bal_delta = float(updated["total"]) if new_is_credit else 0.0

            if _bill_customer_changed(old_bill, updated):
                _adjust_customer_summary(
                    conn,
                    name=old_bill["cust"],
                    phone=old_bill["phone"],
                    total_delta=-float(old_bill["total"]),
                    visit_delta=-1,
                    allow_insert=False,
                    balance_delta=old_bal_delta,
                )
                _adjust_customer_summary(
                    conn,
                    name=updated["cust"],
                    phone=updated["phone"],
                    total_delta=float(updated["total"]),
                    visit_delta=1,
                    allow_insert=True,
                    face_vector=data.get("face_vector", ""),
                    balance_delta=new_bal_delta,
                )
            else:
                _adjust_customer_summary(
                    conn,
                    name=updated["cust"],
                    phone=updated["phone"],
                    total_delta=float(updated["total"]) - float(old_bill["total"]),
                    visit_delta=0,
                    allow_insert=False,
                    face_vector=data.get("face_vector", ""),
                    balance_delta=new_bal_delta + old_bal_delta,
                )

            if updated.get("doctor", "Self") and str(updated.get("doctor", "Self")).strip().lower() != "self":
                doctor_name = str(updated.get("doctor", "Self")).strip()
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

            delta_by_med: dict[str, int] = {}
            for item in new_items:
                med_id = str(item.get("id", "")).strip()
                qty = int(item.get("qty", 0) or 0)
                if med_id:
                    delta_by_med[med_id] = delta_by_med.get(med_id, 0) + qty
            for item in old_items:
                med_id = str(item.get("id", "")).strip()
                qty = int(item.get("qty", 0) or 0)
                if med_id:
                    delta_by_med[med_id] = delta_by_med.get(med_id, 0) - qty

            for med_id, delta in delta_by_med.items():
                if delta == 0:
                    continue
                med = conn.execute("SELECT s FROM medicines WHERE id = ?", (med_id,)).fetchone()
                if not med:
                    continue
                current_stock = int(med["s"] or 0)
                next_stock = max(0, current_stock - delta)
                conn.execute("UPDATE medicines SET s = ? WHERE id = ?", (next_stock, med_id))

            _write_bill_row(conn, updated, replace=True)

            row = _get_bill_row(conn, bill_id)
        return jsonify(normalize_bill_row(row))
    except (ValueError, TypeError) as err:
        return json_error("Invalid bill data", 400, str(err))
    except Exception as err:
        return json_error("Failed to update bill", 500, str(err))


@bills_bp.route("/api/bills/<bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    try:
        with get_conn() as conn:
            row = _get_bill_row(conn, bill_id)
            if not row:
                return json_error("Bill not found", 404, {"id": bill_id})

            bill = normalize_bill_row(row)
            _apply_stock_delta(conn, bill["items"], 1)
            _adjust_customer_summary(
                conn,
                name=bill["cust"],
                phone=bill["phone"],
                total_delta=-float(bill["total"]),
                visit_delta=-1,
                allow_insert=False,
            )
            conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        return jsonify({"status": "success", "deleted": bill_id})
    except Exception as err:
        return json_error("Failed to delete bill", 500, str(err))
