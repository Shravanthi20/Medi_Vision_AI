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
        "prescription": prescription,
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

        c_cols = table_columns(conn, "customers")
        if "address" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN address TEXT DEFAULT ''")
        if "email" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN email TEXT DEFAULT ''")
        if "face_vector" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN face_vector TEXT DEFAULT ''")

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
