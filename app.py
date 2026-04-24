import json
import os
import sqlite3
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PHARMACY_DB_PATH", os.path.join(BASE_DIR, "database.db"))
DASHBOARD_PATH = os.path.join(BASE_DIR, "/templates/login.html")


app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


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
                max_qty INTEGER DEFAULT 0
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
                ),
            ]
            conn.executemany(
                """
                INSERT INTO medicines
                (id, n, g, c, p, s, batch, expiry, p_rate, p_packing, s_packing, p_gst, s_gst, disc, offer, reorder, max_qty)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                initial_meds,
            )

    migrate_db()


def migrate_db() -> None:
    with get_conn() as conn:
        # Purchases migration
        p_cols = table_columns(conn, "purchases")
        if "batch" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN batch TEXT DEFAULT ''")
        if "expiry" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN expiry TEXT DEFAULT ''")
        if "photo" not in p_cols:
            conn.execute("ALTER TABLE purchases ADD COLUMN photo TEXT DEFAULT ''")

        # Bills migration
        b_cols = table_columns(conn, "bills")
        if "rx" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN rx TEXT DEFAULT ''")
        if "prescription" not in b_cols:
            conn.execute("ALTER TABLE bills ADD COLUMN prescription TEXT DEFAULT ''")

        # Customers migration
        c_cols = table_columns(conn, "customers")
        if "address" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN address TEXT DEFAULT ''")
        if "email" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN email TEXT DEFAULT ''")
        if "face_vector" not in c_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN face_vector TEXT DEFAULT ''")

        # Doctors migration
        d_cols = table_columns(conn, "doctors")
        if "email" not in d_cols:
            conn.execute("ALTER TABLE doctors ADD COLUMN email TEXT DEFAULT ''")

        # Suppliers migration
        s_cols = table_columns(conn, "suppliers")
        if "gst" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN gst TEXT DEFAULT ''")
        if "last_order" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN last_order TEXT DEFAULT '-'")
        if "status" not in s_cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN status TEXT DEFAULT 'Active'")

        # Medicines migration
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
        ]
        for col, col_type in med_new_cols:
            if col not in m_cols:
                conn.execute(f"ALTER TABLE medicines ADD COLUMN {col} {col_type}")


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


@app.route("/")
def dashboard():
    return send_file(DASHBOARD_PATH)


@app.route("/api/health", methods=["GET"])
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


@app.route("/api/backup")
def backup_db():
    return send_file(DB_PATH, as_attachment=True)


# --- BILLS ---
@app.route("/api/bills", methods=["GET"])
def get_bills():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM bills ORDER BY ts DESC").fetchall()
    return jsonify([normalize_bill_row(row) for row in rows])


@app.route("/api/bills", methods=["POST"])
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

            # Update customer records
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

            # Update doctor records
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

            # Update medicine stock (skip non-inventory/manual lines gracefully)
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


# --- MEDICINES (INVENTORY) ---
@app.route("/api/medicines", methods=["GET"])
def get_meds():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM medicines").fetchall()
    keys = [
        "id",
        "n",
        "g",
        "c",
        "p",
        "s",
        "batch",
        "expiry",
        "p_rate",
        "p_packing",
        "s_packing",
        "p_gst",
        "s_gst",
        "disc",
        "offer",
        "reorder",
        "max_qty",
    ]
    return jsonify([dict(zip(keys, tuple(row))) for row in rows])


@app.route("/api/medicines/alerts", methods=["GET"])
def medicine_alerts():
    low_stock_threshold = int(request.args.get("low_stock", 15))
    expiry_days = int(request.args.get("expiry_days", 90))
    now = datetime.now().date()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, n, s, expiry, reorder
            FROM medicines
            ORDER BY n COLLATE NOCASE ASC
            """
        ).fetchall()

    low_stock: list[dict[str, Any]] = []
    expiring_soon: list[dict[str, Any]] = []
    for row in rows:
        med = dict(row)
        stock = int(med.get("s") or 0)
        reorder_level = int(med.get("reorder") or 0)
        threshold = reorder_level if reorder_level > 0 else low_stock_threshold
        if stock <= threshold:
            med["threshold"] = threshold
            low_stock.append(med)

        expiry_raw = (med.get("expiry") or "").strip()
        if expiry_raw:
            try:
                exp_date = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
                days_left = (exp_date - now).days
                if days_left <= expiry_days:
                    expiring_soon.append(
                        {
                            "id": med.get("id"),
                            "n": med.get("n"),
                            "s": stock,
                            "expiry": expiry_raw,
                            "days_left": days_left,
                        }
                    )
            except ValueError:
                pass

    return jsonify(
        {
            "low_stock": low_stock,
            "expiring_soon": sorted(expiring_soon, key=lambda x: x["days_left"]),
            "config": {"low_stock": low_stock_threshold, "expiry_days": expiry_days},
        }
    )


@app.route("/api/medicines", methods=["POST"])
def update_med():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["id", "n", "p", "s"])
    if missing:
        return json_error("Missing required medicine fields", 400, missing)

    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO medicines
                (id, n, g, c, p, s, batch, expiry, p_rate, p_packing, s_packing, p_gst, s_gst, disc, offer, reorder, max_qty)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["id"],
                    data["n"],
                    data.get("g", "Generic"),
                    data.get("c", "Tablet"),
                    float(data["p"]),
                    int(data["s"]),
                    data.get("batch", ""),
                    data.get("expiry", ""),
                    float(data.get("p_rate", 0) or 0),
                    data.get("p_packing", ""),
                    data.get("s_packing", ""),
                    float(data.get("p_gst", 0) or 0),
                    float(data.get("s_gst", 0) or 0),
                    float(data.get("disc", 0) or 0),
                    data.get("offer", ""),
                    int(data.get("reorder", 0) or 0),
                    int(data.get("max_qty", 0) or 0),
                ),
            )
        return jsonify({"status": "success"})
    except (ValueError, TypeError) as err:
        return json_error("Invalid medicine payload", 400, str(err))
    except Exception as err:
        return json_error("Failed to save medicine", 500, str(err))


@app.route("/api/medicines/<id>", methods=["DELETE"])
def delete_med(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM medicines WHERE id = ?", (id,))
    return jsonify({"status": "success"})


# --- PURCHASES ---
@app.route("/api/purchases", methods=["GET"])
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


@app.route("/api/purchases", methods=["POST"])
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


# --- MASTERS (CUSTOMERS / DOCTORS / SUPPLIERS) ---
@app.route("/api/suppliers", methods=["GET"])
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


@app.route("/api/suppliers", methods=["POST"])
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


@app.route("/api/customers", methods=["GET"])
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


@app.route("/api/customers", methods=["POST"])
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


@app.route("/api/doctors", methods=["GET"])
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


@app.route("/api/doctors", methods=["POST"])
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


@app.route("/api/suppliers/<id>", methods=["DELETE"])
def delete_supplier(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@app.route("/api/customers/<id>", methods=["DELETE"])
def delete_customer(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@app.route("/api/doctors/<id>", methods=["DELETE"])
def delete_doctor(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors WHERE id = ?", (id,))
    return jsonify({"status": "success"})


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5001)
