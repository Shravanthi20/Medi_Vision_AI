import json
import sqlite3
from typing import Any

from .config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def safe_json_loads(raw: Any, fallback: Any) -> Any:
    if raw is None:
        return fallback
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback


def json_error(message: str, status_code: int = 400, details: Any = None):
    from flask import jsonify

    payload = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def required_fields(payload: dict[str, Any], fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        if field not in payload:
            missing.append(field)
            continue
        value = payload[field]
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(field)
    return missing


def shelf_location_label(data: dict[str, Any]) -> str:
    name = str(data.get("name", "") or "").strip()
    aisle = str(data.get("aisle", "") or "").strip()
    rack = str(data.get("rack", "") or "").strip()
    shelf = str(data.get("shelf", "") or "").strip()
    bin_no = str(data.get("bin", "") or "").strip()

    location_bits = []
    if aisle:
        location_bits.append(f"Aisle {aisle}")
    if rack:
        location_bits.append(f"Rack {rack}")
    if shelf:
        location_bits.append(f"Shelf {shelf}")
    if bin_no:
        location_bits.append(f"Bin {bin_no}")

    if name and location_bits:
        return f"{name} - {' / '.join(location_bits)}"
    if name:
        return name
    if location_bits:
        return " / ".join(location_bits)
    return "Unassigned"


def normalize_medicine_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    shelf_id = data.get("shelf_id", "") or ""
    shelf_name = data.get("shelf_name", "") or ""
    shelf_aisle = data.get("shelf_aisle", "") or ""
    shelf_rack = data.get("shelf_rack", "") or ""
    shelf_slot = data.get("shelf_slot", "") or ""
    shelf_bin = data.get("shelf_bin", "") or ""
    shelf_notes = data.get("shelf_notes", "") or ""
    shelf_status = data.get("shelf_status", "") or ""
    shelf_label = data.get("shelf_label", "") or shelf_location_label(
        {
            "name": shelf_name,
            "aisle": shelf_aisle,
            "rack": shelf_rack,
            "shelf": shelf_slot,
            "bin": shelf_bin,
        }
    )
    return {
        "id": data.get("id"),
        "n": data.get("n"),
        "g": data.get("g"),
        "c": data.get("c"),
        "p": data.get("p"),
        "s": data.get("s"),
        "batch": data.get("batch", ""),
        "expiry": data.get("expiry", ""),
        "p_rate": data.get("p_rate", 0),
        "p_packing": data.get("p_packing", ""),
        "s_packing": data.get("s_packing", ""),
        "p_gst": data.get("p_gst", 0),
        "s_gst": data.get("s_gst", 0),
        "disc": data.get("disc", 0),
        "offer": data.get("offer", ""),
        "reorder": data.get("reorder", 0),
        "max_qty": data.get("max_qty", 0),
        "shelf_id": shelf_id,
        "shelf_name": shelf_name,
        "shelf_aisle": shelf_aisle,
        "shelf_rack": shelf_rack,
        "shelf_slot": shelf_slot,
        "shelf_bin": shelf_bin,
        "shelf_notes": shelf_notes,
        "shelf_status": shelf_status,
        "shelf_label": shelf_label,
    }


def normalize_bill_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    items = safe_json_loads(data.get("items"), [])
    if not isinstance(items, list):
        items = []
    prescription = data.get("prescription", "") or data.get("rx", "") or ""
    return {
        "id": data.get("id"),
        "ts": data.get("ts"),
        "date": data.get("date"),
        "cust": data.get("cust"),
        "phone": data.get("phone"),
        "pay": data.get("pay"),
        "sub": data.get("sub"),
        "disc": data.get("disc"),
        "tax": data.get("tax"),
        "total": data.get("total"),
        "items": items,
        "doctor": data.get("doctor", "Self"),
        "customer_type": data.get("customer_type", "customer"),
        "bill_type": data.get("bill_type", "retail"),
        "discount_type": data.get("discount_type", "pct"),
        "discount_value": data.get("discount_value", 0),
        "prescription": prescription,
    }


def normalize_sms_template_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "body": data.get("body", ""),
        "message_type": data.get("message_type", "custom"),
        "active": int(data.get("active", 1) or 0),
        "created_ts": data.get("created_ts"),
        "updated_ts": data.get("updated_ts"),
    }


def normalize_sms_message_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    provider_response = safe_json_loads(data.get("provider_response"), {})
    if not isinstance(provider_response, dict):
        provider_response = {"raw": provider_response}
    return {
        "id": data.get("id"),
        "created_ts": data.get("created_ts"),
        "updated_ts": data.get("updated_ts"),
        "recipient_phone": data.get("recipient_phone", ""),
        "customer_id": data.get("customer_id", ""),
        "customer_name": data.get("customer_name", ""),
        "bill_id": data.get("bill_id", ""),
        "template_id": data.get("template_id", ""),
        "message_type": data.get("message_type", "custom"),
        "body": data.get("body", ""),
        "send_status": data.get("send_status", "queued"),
        "provider_name": data.get("provider_name", ""),
        "provider_message_id": data.get("provider_message_id", ""),
        "failure_reason": data.get("failure_reason", ""),
        "retry_count": int(data.get("retry_count", 0) or 0),
        "last_attempt_ts": data.get("last_attempt_ts", 0),
        "sent_ts": data.get("sent_ts", 0),
        "delivered_ts": data.get("delivered_ts", 0),
        "source": data.get("source", "manual"),
        "provider_response": provider_response,
    }


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                id TEXT PRIMARY KEY,
                ts INTEGER,
                date TEXT,
                cust TEXT,
                phone TEXT,
                pay TEXT,
                sub REAL,
                disc REAL,
                tax REAL,
                total REAL,
                items TEXT,
                doctor TEXT,
                customer_type TEXT DEFAULT 'customer',
                bill_type TEXT DEFAULT 'retail',
                discount_type TEXT DEFAULT 'pct',
                discount_value REAL DEFAULT 0,
                rx TEXT DEFAULT '',
                prescription TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id TEXT PRIMARY KEY,
                n TEXT,
                g TEXT,
                c TEXT,
                p REAL,
                s INTEGER,
                batch TEXT DEFAULT '',
                expiry TEXT DEFAULT '',
                p_rate REAL DEFAULT 0,
                p_packing TEXT DEFAULT '',
                s_packing TEXT DEFAULT '',
                p_gst REAL DEFAULT 0,
                s_gst REAL DEFAULT 0,
                disc REAL DEFAULT 0,
                offer TEXT DEFAULT '',
                reorder INTEGER DEFAULT 0,
                max_qty INTEGER DEFAULT 0,
                shelf_id TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shelf_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                aisle TEXT DEFAULT '',
                rack TEXT DEFAULT '',
                shelf TEXT DEFAULT '',
                bin TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'Active'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id TEXT PRIMARY KEY,
                supplier TEXT,
                items TEXT,
                amount REAL,
                date TEXT,
                status TEXT,
                batch TEXT DEFAULT '',
                expiry TEXT DEFAULT '',
                photo TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                visits INTEGER DEFAULT 1,
                total REAL DEFAULT 0,
                address TEXT DEFAULT '',
                email TEXT DEFAULT '',
                face_vector TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                specialty TEXT,
                hospital TEXT,
                phone TEXT,
                email TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_templates (
                id TEXT PRIMARY KEY,
                name TEXT,
                body TEXT,
                message_type TEXT DEFAULT 'custom',
                active INTEGER DEFAULT 1,
                created_ts INTEGER,
                updated_ts INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_messages (
                id TEXT PRIMARY KEY,
                created_ts INTEGER,
                updated_ts INTEGER,
                recipient_phone TEXT,
                customer_id TEXT DEFAULT '',
                customer_name TEXT DEFAULT '',
                bill_id TEXT DEFAULT '',
                template_id TEXT DEFAULT '',
                message_type TEXT DEFAULT 'custom',
                body TEXT,
                send_status TEXT DEFAULT 'queued',
                provider_name TEXT DEFAULT '',
                provider_message_id TEXT DEFAULT '',
                provider_response TEXT DEFAULT '',
                failure_reason TEXT DEFAULT '',
                retry_count INTEGER DEFAULT 0,
                last_attempt_ts INTEGER DEFAULT 0,
                sent_ts INTEGER DEFAULT 0,
                delivered_ts INTEGER DEFAULT 0,
                source TEXT DEFAULT 'manual'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                gst TEXT DEFAULT '',
                last_order TEXT DEFAULT '-',
                status TEXT DEFAULT 'Active'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id TEXT,
                customer_phone TEXT,
                status TEXT DEFAULT 'pending',
                message TEXT,
                timestamp TEXT,
                provider_message_id TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                is_active INTEGER DEFAULT 1
            )
            """
        )

        med_count = conn.execute("SELECT COUNT(*) AS c FROM medicines").fetchone()["c"]
        if med_count == 0:
            initial_meds = [
                (
                    "1",
                    "Dolo 650mg",
                    "Paracetamol",
                    "Tablet",
                    28,
                    3,
                    "B101",
                    "2026-12-31",
                    20.5,
                    "1x10",
                    "1x10",
                    12.0,
                    12.0,
                    0.0,
                    "None",
                    10,
                    100,
                    "",
                ),
                (
                    "2",
                    "Augmentin 625",
                    "Amoxicillin",
                    "Tablet",
                    142,
                    24,
                    "B202",
                    "2026-12-31",
                    110.0,
                    "1x10",
                    "1x10",
                    12.0,
                    12.0,
                    0.0,
                    "None",
                    20,
                    200,
                    "",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO medicines
                (id, n, g, c, p, s, batch, expiry, p_rate, p_packing, s_packing, p_gst, s_gst, disc, offer, reorder, max_qty, shelf_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                initial_meds,
            )

        template_count = conn.execute("SELECT COUNT(*) AS c FROM message_templates").fetchone()["c"]
        if template_count == 0:
            conn.execute(
                """
                INSERT INTO message_templates (name, content, is_active)
                VALUES ('Default Bill WhatsApp', 'Hello! Your bill for Rs. {total} is ready. Thank you for visiting Medi Vision.', 1)
                """
            )

    migrate_db()


def migrate_db() -> None:
    with get_conn() as conn:
        p_cols = table_columns(conn, "purchases")
        if "batch" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN batch TEXT DEFAULT ''")
        if "expiry" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN expiry TEXT DEFAULT ''")
        if "photo" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN photo TEXT DEFAULT ''")

        b_cols = table_columns(conn, "bills")
        if "rx" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN rx TEXT DEFAULT ''")
        if "prescription" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN prescription TEXT DEFAULT ''")
        if "customer_type" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN customer_type TEXT DEFAULT 'customer'")
        if "bill_type" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN bill_type TEXT DEFAULT 'retail'")
        if "discount_type" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN discount_type TEXT DEFAULT 'pct'")
        if "discount_value" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN discount_value REAL DEFAULT 0")

        c_cols = table_columns(conn, "customers")
        if "address" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN address TEXT DEFAULT ''")
        if "email" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN email TEXT DEFAULT ''")
        if "face_vector" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN face_vector TEXT DEFAULT ''")

        sms_template_cols = table_columns(conn, "sms_templates")
        sms_template_new_cols = [
            ("message_type", "TEXT DEFAULT 'custom'"),
            ("active", "INTEGER DEFAULT 1"),
            ("created_ts", "INTEGER"),
            ("updated_ts", "INTEGER"),
        ]
        for col, col_type in sms_template_new_cols:
            if col not in sms_template_cols:
                conn.execute(f"ALTER TABLE sms_templates ADD COLUMN {col} {col_type}")

        sms_message_cols = table_columns(conn, "sms_messages")
        sms_message_new_cols = [
            ("created_ts", "INTEGER"),
            ("updated_ts", "INTEGER"),
            ("customer_id", "TEXT DEFAULT ''"),
            ("customer_name", "TEXT DEFAULT ''"),
            ("bill_id", "TEXT DEFAULT ''"),
            ("template_id", "TEXT DEFAULT ''"),
            ("message_type", "TEXT DEFAULT 'custom'"),
            ("send_status", "TEXT DEFAULT 'queued'"),
            ("provider_name", "TEXT DEFAULT ''"),
            ("provider_message_id", "TEXT DEFAULT ''"),
            ("provider_response", "TEXT DEFAULT ''"),
            ("failure_reason", "TEXT DEFAULT ''"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("last_attempt_ts", "INTEGER DEFAULT 0"),
            ("sent_ts", "INTEGER DEFAULT 0"),
            ("delivered_ts", "INTEGER DEFAULT 0"),
            ("source", "TEXT DEFAULT 'manual'"),
        ]
        for col, col_type in sms_message_new_cols:
            if col not in sms_message_cols:
                conn.execute(f"ALTER TABLE sms_messages ADD COLUMN {col} {col_type}")

        d_cols = table_columns(conn, "doctors")
        if "email" not in d_cols:
            conn.execute("ALTER TABLE doctors ADD COLUMN email TEXT DEFAULT ''")

        s_cols = table_columns(conn, "suppliers")
        if "gst" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN gst TEXT DEFAULT ''")
        if "last_order" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN last_order TEXT DEFAULT '-'")
        if "status" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN status TEXT DEFAULT 'Active'")

        m_cols = table_columns(conn, "medicines")
        med_new_cols = [
            ("batch", "TEXT DEFAULT ''"),
            ("expiry", "TEXT DEFAULT ''"),
            ("p_rate", "REAL DEFAULT 0"),
            ("p_packing", "TEXT DEFAULT ''"),
            ("s_packing", "TEXT DEFAULT ''"),
            ("p_gst", "REAL DEFAULT 0"),
            ("s_gst", "REAL DEFAULT 0"),
            ("disc", "REAL DEFAULT 0"),
            ("offer", "TEXT DEFAULT ''"),
            ("reorder", "INTEGER DEFAULT 0"),
            ("max_qty", "INTEGER DEFAULT 0"),
            ("shelf_id", "TEXT DEFAULT ''"),
        ]
        for col, col_type in med_new_cols:
            if col not in m_cols:
                conn.execute(f"ALTER TABLE medicines ADD COLUMN {col} {col_type}")

        # Safety check for new tables in existing dbs
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id TEXT,
                customer_phone TEXT,
                status TEXT DEFAULT 'pending',
                message TEXT,
                timestamp TEXT,
                provider_message_id TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT,
                is_active INTEGER DEFAULT 1
            )
            """
        )

        template_count = conn.execute("SELECT COUNT(*) AS c FROM sms_templates").fetchone()["c"]
        if template_count == 0:
            now_ts = int(__import__("time").time() * 1000)
            default_templates = [
                (
                    "tpl-bill-ready",
                    "Bill Ready",
                    "Dear {customer_name}, your bill #{bill_id} for Rs. {bill_total} is ready. Thank you for visiting {store_name}.",
                    "bill_ready",
                    1,
                    now_ts,
                    now_ts,
                ),
                (
                    "tpl-pickup-reminder",
                    "Pickup Reminder",
                    "Dear {customer_name}, your medicines from bill #{bill_id} are ready for pickup at {store_name}.",
                    "reminder",
                    1,
                    now_ts,
                    now_ts,
                ),
                (
                    "tpl-follow-up",
                    "Follow Up",
                    "Hello {customer_name}, this is a follow-up from {store_name}. Please contact us for any assistance.",
                    "follow_up",
                    1,
                    now_ts,
                    now_ts,
                ),
                (
                    "tpl-low-stock",
                    "Low Stock Alert",
                    "Stock alert for {item_name}: current quantity is {stock_qty}. Please review the reorder level.",
                    "stock_alert",
                    1,
                    now_ts,
                    now_ts,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO sms_templates
                (id, name, body, message_type, active, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                default_templates,
            )
