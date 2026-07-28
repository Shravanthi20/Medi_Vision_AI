"""
MediVision Wholesale — dedicated distributor / wholesaler app
=============================================================

Single-file Flask app. Runs on port 3002 via gunicorn.
Separate from the retail MediVision app: own DB, own login, own domain
(wholesale.selvammedicals.in) or path fallback (/wholesale/).

Features:
  - Retail-shop customer master with GSTIN, DL, credit terms, price tier
  - Wholesale item master with MRP / PTR / scheme / MOQ / GST
  - Sales order lifecycle: draft → confirmed → dispatched → invoiced → paid
  - Invoice generation + GST breakup + printable HTML
  - Payment recording and per-shop ledger with outstanding + ageing
  - Delivery routes (beats) with day-of-week + salesman
  - Public browsable catalog (`/catalog`) — retail shops can place orders
    without logging in, just by entering their shop code
  - Simple single-password admin login (WS_ADMIN_PASSWORD env)

Author: MediVision AI
"""
from __future__ import annotations

import os
import sqlite3
import secrets
import functools
from datetime import datetime, timedelta, date
from contextlib import contextmanager

from flask import (Flask, request, render_template, redirect, url_for,
                   session, flash, jsonify, abort, Response, g)
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_PATH = os.environ.get("WS_DB_PATH", os.path.join(BASE_DIR, "wholesaler.db"))
ADMIN_PASSWORD = os.environ.get("WS_ADMIN_PASSWORD", "changeme")
SECRET_KEY = os.environ.get("WS_SECRET_KEY", secrets.token_urlsafe(32))
COMPANY_NAME = os.environ.get("WS_COMPANY_NAME", "Selvam Medicals — Wholesale")
COMPANY_GSTIN = os.environ.get("WS_COMPANY_GSTIN", "")
COMPANY_ADDRESS = os.environ.get("WS_COMPANY_ADDRESS", "Coimbatore, Tamil Nadu")
COMPANY_PHONE = os.environ.get("WS_COMPANY_PHONE", "")

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ═════════════════════════════════════════════════════════════════════
#  DATABASE
# ═════════════════════════════════════════════════════════════════════
SCHEMA = r"""
CREATE TABLE IF NOT EXISTS retail_shops (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE,
    name            TEXT NOT NULL,
    contact_person  TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    whatsapp        TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    pincode         TEXT DEFAULT '',
    gstin           TEXT DEFAULT '',
    drug_license    TEXT DEFAULT '',
    credit_limit    REAL DEFAULT 0,
    credit_days     INTEGER DEFAULT 30,
    price_tier      TEXT DEFAULT 'A',
    route_id        INTEGER,
    status          TEXT DEFAULT 'active',
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wholesale_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE,
    name            TEXT NOT NULL,
    generic         TEXT DEFAULT '',
    manufacturer    TEXT DEFAULT '',
    pack_size       TEXT DEFAULT '',
    hsn             TEXT DEFAULT '30049099',
    gst_rate        REAL DEFAULT 12,
    mrp             REAL DEFAULT 0,
    ptr             REAL DEFAULT 0,
    ptr_b           REAL DEFAULT 0,
    ptr_c           REAL DEFAULT 0,
    scheme          TEXT DEFAULT '',
    moq             INTEGER DEFAULT 1,
    stock           INTEGER DEFAULT 0,
    reorder_level   INTEGER DEFAULT 0,
    category        TEXT DEFAULT '',
    batch           TEXT DEFAULT '',
    expiry          TEXT DEFAULT '',
    status          TEXT DEFAULT 'active',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no        TEXT UNIQUE,
    shop_id         INTEGER NOT NULL,
    order_date      TEXT DEFAULT (date('now')),
    status          TEXT DEFAULT 'draft',
    subtotal        REAL DEFAULT 0,
    gst_amount      REAL DEFAULT 0,
    discount        REAL DEFAULT 0,
    total           REAL DEFAULT 0,
    notes           TEXT DEFAULT '',
    source          TEXT DEFAULT 'admin',
    created_by      TEXT DEFAULT 'system',
    created_at      TEXT DEFAULT (datetime('now')),
    confirmed_at    TEXT,
    dispatched_at   TEXT,
    invoiced_at     TEXT,
    paid_at         TEXT,
    FOREIGN KEY(shop_id) REFERENCES retail_shops(id)
);

CREATE TABLE IF NOT EXISTS sales_order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER NOT NULL,
    item_id         INTEGER,
    item_name       TEXT,
    pack_size       TEXT,
    qty             INTEGER DEFAULT 0,
    free_qty        INTEGER DEFAULT 0,
    rate            REAL DEFAULT 0,
    gst_rate        REAL DEFAULT 0,
    amount          REAL DEFAULT 0,
    FOREIGN KEY(order_id) REFERENCES sales_orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no      TEXT UNIQUE,
    order_id        INTEGER,
    shop_id         INTEGER NOT NULL,
    invoice_date    TEXT DEFAULT (date('now')),
    due_date        TEXT,
    total           REAL DEFAULT 0,
    paid            REAL DEFAULT 0,
    status          TEXT DEFAULT 'open',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id         INTEGER NOT NULL,
    invoice_id      INTEGER,
    amount          REAL DEFAULT 0,
    method          TEXT DEFAULT 'cash',
    reference       TEXT DEFAULT '',
    paid_on         TEXT DEFAULT (date('now')),
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS delivery_routes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,
    day_of_week     TEXT DEFAULT '',
    salesman        TEXT DEFAULT '',
    notes           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT DEFAULT (datetime('now')),
    actor           TEXT,
    action          TEXT,
    entity          TEXT,
    entity_id       INTEGER,
    details         TEXT
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)


def audit(actor, action, entity=None, entity_id=None, details=""):
    try:
        with conn() as c:
            c.execute(
                "INSERT INTO audit_log (actor, action, entity, entity_id, details) VALUES (?,?,?,?,?)",
                (actor, action, entity, entity_id, details),
            )
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
#  AUTH
# ═════════════════════════════════════════════════════════════════════
def login_required(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        # Require BOTH a signed-in user AND a resolved tenant. A platform-owner
        # session has no tenant, so it can never reach a company's screens.
        if not session.get("ws_user") or not session.get("tenant"):
            return redirect("/portal")
        return f(*a, **k)
    return wrap


@app.route("/login", methods=["GET", "POST"])
def login():
    # Superseded by the multi-company /portal sign-in.
    return redirect("/portal")


def _legacy_login_unused():
    error = ""
    if request.method == "POST":
        pw = request.form.get("password", "")
        name = request.form.get("name", "").strip() or "admin"
        if pw == ADMIN_PASSWORD:
            session["ws_user"] = name
            audit(name, "login")
            nxt = request.args.get("next") or "/"
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = "/"
            return redirect(nxt)
        error = "Wrong password"
    return render_template("login.html", error=error, company=COMPANY_NAME)


@app.route("/logout", methods=["POST"])
def logout():
    audit(session.get("ws_user") or "unknown", "logout")
    session.clear()
    return redirect(url_for("login"))


# ═════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════
def money(n):
    try:
        return "₹" + f"{float(n or 0):,.2f}"
    except Exception:
        return "₹0.00"


app.jinja_env.filters["money"] = money


def next_order_no():
    fy = _current_fy()
    with conn() as c:
        n = c.execute("SELECT COUNT(*) FROM sales_orders WHERE order_no LIKE ?", (f"SO/{fy}/%",)).fetchone()[0]
    return f"SO/{fy}/{n + 1:05d}"


def next_invoice_no():
    fy = _current_fy()
    with conn() as c:
        n = c.execute("SELECT COUNT(*) FROM invoices WHERE invoice_no LIKE ?", (f"INV/{fy}/%",)).fetchone()[0]
    return f"INV/{fy}/{n + 1:05d}"


def _current_fy():
    today = date.today()
    y = today.year if today.month >= 4 else today.year - 1
    return f"{str(y)[-2:]}-{str(y + 1)[-2:]}"


def compute_order_totals(order_id):
    with conn() as c:
        rows = c.execute("SELECT qty, rate, gst_rate FROM sales_order_items WHERE order_id=?", (order_id,)).fetchall()
        subtotal = 0.0
        gst = 0.0
        for r in rows:
            line = (r["qty"] or 0) * (r["rate"] or 0)
            subtotal += line
            gst += line * (r["gst_rate"] or 0) / 100
        c.execute(
            "UPDATE sales_orders SET subtotal=?, gst_amount=?, total=? WHERE id=?",
            (round(subtotal, 2), round(gst, 2), round(subtotal + gst, 2), order_id),
        )


def rate_for_shop(item_row, tier):
    if tier == "B" and (item_row["ptr_b"] or 0) > 0:
        return item_row["ptr_b"]
    if tier == "C" and (item_row["ptr_c"] or 0) > 0:
        return item_row["ptr_c"]
    return item_row["ptr"] or 0


def shop_outstanding(shop_id):
    with conn() as c:
        inv = c.execute(
            "SELECT COALESCE(SUM(total-paid),0) o FROM invoices WHERE shop_id=? AND status!='paid'",
            (shop_id,),
        ).fetchone()["o"]
        # subtract on-account payments not tied to invoices
        credits = c.execute(
            "SELECT COALESCE(SUM(amount),0) c FROM payments WHERE shop_id=? AND invoice_id IS NULL",
            (shop_id,),
        ).fetchone()["c"]
    return max(0.0, inv - credits)


# ═════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═════════════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def dashboard():
    with conn() as c:
        shops_count = c.execute("SELECT COUNT(*) FROM retail_shops WHERE status='active'").fetchone()[0]
        items_count = c.execute("SELECT COUNT(*) FROM wholesale_items WHERE status='active'").fetchone()[0]
        orders_open = c.execute("SELECT COUNT(*) FROM sales_orders WHERE status IN ('draft','confirmed','dispatched')").fetchone()[0]
        pipeline = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM sales_orders WHERE status IN ('draft','confirmed','dispatched','invoiced') GROUP BY status"
        ).fetchall()}
        today_sales = c.execute("SELECT COALESCE(SUM(total),0) t FROM invoices WHERE invoice_date=date('now')").fetchone()["t"]
        month_sales = c.execute("SELECT COALESCE(SUM(total),0) t FROM invoices WHERE substr(invoice_date,1,7)=strftime('%Y-%m','now')").fetchone()["t"]
        outstanding = c.execute("SELECT COALESCE(SUM(total-paid),0) o FROM invoices WHERE status!='paid'").fetchone()["o"]
        overdue = c.execute("SELECT COALESCE(SUM(total-paid),0) o FROM invoices WHERE status!='paid' AND due_date<date('now')").fetchone()["o"]
        low_stock = c.execute("SELECT COUNT(*) FROM wholesale_items WHERE stock<=reorder_level AND reorder_level>0").fetchone()[0]

        top_shops = c.execute("""
            SELECT s.name, COALESCE(SUM(i.total),0) t
            FROM retail_shops s LEFT JOIN invoices i ON i.shop_id=s.id
            WHERE substr(i.invoice_date,1,7)=strftime('%Y-%m','now')
            GROUP BY s.id ORDER BY t DESC LIMIT 5
        """).fetchall()

        recent_orders = c.execute("""
            SELECT o.order_no, o.status, o.total, o.order_date, s.name shop_name
            FROM sales_orders o JOIN retail_shops s ON s.id=o.shop_id
            ORDER BY o.id DESC LIMIT 8
        """).fetchall()

        overdue_shops = c.execute("""
            SELECT s.id, s.name, COALESCE(SUM(i.total-i.paid),0) o
            FROM retail_shops s JOIN invoices i ON i.shop_id=s.id
            WHERE i.status!='paid' AND i.due_date<date('now')
            GROUP BY s.id ORDER BY o DESC LIMIT 5
        """).fetchall()

    return render_template(
        "dashboard.html",
        kpi={
            "shops": shops_count,
            "items": items_count,
            "orders_open": orders_open,
            "today_sales": today_sales,
            "month_sales": month_sales,
            "outstanding": outstanding,
            "overdue": overdue,
            "low_stock": low_stock,
        },
        top_shops=top_shops,
        recent_orders=recent_orders,
        overdue_shops=overdue_shops,
        pipeline=pipeline,
    )


# ═════════════════════════════════════════════════════════════════════
#  RETAIL SHOPS
# ═════════════════════════════════════════════════════════════════════
@app.route("/shops")
@login_required
def shops():
    q = (request.args.get("q") or "").strip()
    with conn() as c:
        if q:
            like = f"%{q}%"
            rows = c.execute(
                "SELECT * FROM retail_shops WHERE name LIKE ? OR code LIKE ? OR phone LIKE ? ORDER BY name",
                (like, like, like),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM retail_shops ORDER BY name").fetchall()
        routes = c.execute("SELECT * FROM delivery_routes ORDER BY name").fetchall()
    # attach outstanding for each shop
    shops_with_outstanding = []
    for r in rows:
        d = dict(r)
        d["outstanding"] = shop_outstanding(r["id"])
        shops_with_outstanding.append(d)
    return render_template("shops.html", shops=shops_with_outstanding, q=q, routes=routes)


@app.route("/shops/save", methods=["POST"])
@login_required
def shop_save():
    d = request.form
    shop_id = d.get("id")
    fields = ("code", "name", "contact_person", "phone", "whatsapp", "email",
              "address", "city", "pincode", "gstin", "drug_license",
              "credit_limit", "credit_days", "price_tier", "route_id",
              "status", "notes")
    vals = {}
    for f in fields:
        v = (d.get(f) or "").strip()
        if f in ("credit_limit",):
            vals[f] = float(v or 0)
        elif f in ("credit_days", "route_id"):
            vals[f] = int(v) if v else None
        else:
            vals[f] = v
    if not vals["name"]:
        flash("Name is required.", "err")
        return redirect(url_for("shops"))
    if not vals["code"]:
        # auto-generate a code
        with conn() as c:
            n = c.execute("SELECT COUNT(*) FROM retail_shops").fetchone()[0]
        vals["code"] = f"S{n + 1:04d}"

    with conn() as c:
        if shop_id:
            sets = ", ".join([f"{k}=?" for k in vals.keys()])
            c.execute(f"UPDATE retail_shops SET {sets} WHERE id=?", (*vals.values(), shop_id))
            audit(session.get("ws_user"), "update", "shop", int(shop_id), vals["name"])
        else:
            cols = ", ".join(vals.keys())
            qm = ", ".join("?" * len(vals))
            cur = c.execute(f"INSERT INTO retail_shops ({cols}) VALUES ({qm})", tuple(vals.values()))
            audit(session.get("ws_user"), "create", "shop", cur.lastrowid, vals["name"])
    flash("Shop saved.", "ok")
    return redirect(url_for("shops"))


@app.route("/shops/<int:shop_id>")
@login_required
def shop_detail(shop_id):
    with conn() as c:
        shop = c.execute("SELECT * FROM retail_shops WHERE id=?", (shop_id,)).fetchone()
        if not shop:
            abort(404)
        orders = c.execute(
            "SELECT * FROM sales_orders WHERE shop_id=? ORDER BY id DESC LIMIT 25",
            (shop_id,),
        ).fetchall()
        invoices = c.execute(
            "SELECT * FROM invoices WHERE shop_id=? ORDER BY id DESC LIMIT 25",
            (shop_id,),
        ).fetchall()
        payments = c.execute(
            "SELECT * FROM payments WHERE shop_id=? ORDER BY id DESC LIMIT 25",
            (shop_id,),
        ).fetchall()
    outstanding = shop_outstanding(shop_id)
    return render_template(
        "shop_detail.html",
        shop=shop, orders=orders, invoices=invoices, payments=payments,
        outstanding=outstanding,
    )


# ═════════════════════════════════════════════════════════════════════
#  WHOLESALE ITEMS
# ═════════════════════════════════════════════════════════════════════
@app.route("/items")
@login_required
def items():
    q = (request.args.get("q") or "").strip()
    with conn() as c:
        if q:
            like = f"%{q}%"
            rows = c.execute(
                "SELECT * FROM wholesale_items WHERE name LIKE ? OR generic LIKE ? OR code LIKE ? ORDER BY name",
                (like, like, like),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM wholesale_items ORDER BY name LIMIT 500").fetchall()
    return render_template("items.html", items=rows, q=q)


@app.route("/items/save", methods=["POST"])
@login_required
def item_save():
    d = request.form
    item_id = d.get("id")
    fields = ("code", "name", "generic", "manufacturer", "pack_size", "hsn",
              "gst_rate", "mrp", "ptr", "ptr_b", "ptr_c", "scheme",
              "moq", "stock", "reorder_level", "category", "batch", "expiry", "status")
    vals = {}
    for f in fields:
        v = (d.get(f) or "").strip()
        if f in ("gst_rate", "mrp", "ptr", "ptr_b", "ptr_c"):
            vals[f] = float(v or 0)
        elif f in ("moq", "stock", "reorder_level"):
            vals[f] = int(v or 0)
        else:
            vals[f] = v
    if not vals["name"]:
        flash("Item name required.", "err")
        return redirect(url_for("items"))
    if not vals["code"]:
        with conn() as c:
            n = c.execute("SELECT COUNT(*) FROM wholesale_items").fetchone()[0]
        vals["code"] = f"I{n + 1:05d}"
    with conn() as c:
        if item_id:
            sets = ", ".join([f"{k}=?" for k in vals.keys()])
            c.execute(f"UPDATE wholesale_items SET {sets} WHERE id=?", (*vals.values(), item_id))
            audit(session.get("ws_user"), "update", "item", int(item_id), vals["name"])
        else:
            cols = ", ".join(vals.keys())
            qm = ", ".join("?" * len(vals))
            cur = c.execute(f"INSERT INTO wholesale_items ({cols}) VALUES ({qm})", tuple(vals.values()))
            audit(session.get("ws_user"), "create", "item", cur.lastrowid, vals["name"])
    flash("Item saved.", "ok")
    return redirect(url_for("items"))


# ═════════════════════════════════════════════════════════════════════
#  ORDERS
# ═════════════════════════════════════════════════════════════════════
@app.route("/orders")
@login_required
def orders():
    status = request.args.get("status") or ""
    with conn() as c:
        q = """SELECT o.*, s.name shop_name, s.code shop_code
               FROM sales_orders o JOIN retail_shops s ON s.id=o.shop_id"""
        if status:
            q += " WHERE o.status=? ORDER BY o.id DESC LIMIT 200"
            rows = c.execute(q, (status,)).fetchall()
        else:
            q += " ORDER BY o.id DESC LIMIT 200"
            rows = c.execute(q).fetchall()
    return render_template("orders.html", orders=rows, status=status)


@app.route("/orders/new", methods=["GET", "POST"])
@login_required
def order_new():
    with conn() as c:
        shops = c.execute("SELECT id, code, name, price_tier FROM retail_shops WHERE status='active' ORDER BY name").fetchall()

    if request.method == "POST":
        shop_id = int(request.form.get("shop_id") or 0)
        item_ids = request.form.getlist("item_id[]")
        qtys = request.form.getlist("qty[]")
        rates = request.form.getlist("rate[]")
        notes = request.form.get("notes", "").strip()

        if not shop_id or not item_ids:
            flash("Shop and at least one item required.", "err")
            return redirect(url_for("order_new"))

        with conn() as c:
            shop = c.execute("SELECT * FROM retail_shops WHERE id=?", (shop_id,)).fetchone()
            if not shop:
                flash("Invalid shop.", "err")
                return redirect(url_for("order_new"))

            order_no = next_order_no()
            cur = c.execute(
                "INSERT INTO sales_orders (order_no, shop_id, notes, source, created_by) VALUES (?,?,?,?,?)",
                (order_no, shop_id, notes, "admin", session.get("ws_user") or "admin"),
            )
            order_id = cur.lastrowid

            for iid, q_str, r_str in zip(item_ids, qtys, rates):
                if not iid or not q_str:
                    continue
                iid = int(iid)
                qty = int(q_str or 0)
                if qty <= 0:
                    continue
                item = c.execute("SELECT * FROM wholesale_items WHERE id=?", (iid,)).fetchone()
                if not item:
                    continue
                rate = float(r_str or 0) or rate_for_shop(item, shop["price_tier"])
                # apply scheme like "10+1"
                free = 0
                if item["scheme"]:
                    try:
                        base, bonus = item["scheme"].split("+")
                        base, bonus = int(base), int(bonus)
                        if base > 0:
                            free = (qty // base) * bonus
                    except Exception:
                        pass
                amount = qty * rate
                c.execute("""INSERT INTO sales_order_items
                    (order_id, item_id, item_name, pack_size, qty, free_qty, rate, gst_rate, amount)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (order_id, iid, item["name"], item["pack_size"], qty, free, rate, item["gst_rate"], amount))

        compute_order_totals(order_id)
        audit(session.get("ws_user"), "create", "order", order_id, order_no)
        flash(f"Order {order_no} created.", "ok")
        return redirect(url_for("order_detail", order_id=order_id))

    return render_template("order_new.html", shops=shops)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    with conn() as c:
        order = c.execute("""SELECT o.*, s.name shop_name, s.code shop_code, s.gstin shop_gstin,
                                    s.address shop_address, s.city shop_city, s.pincode shop_pincode
                             FROM sales_orders o JOIN retail_shops s ON s.id=o.shop_id
                             WHERE o.id=?""", (order_id,)).fetchone()
        if not order:
            abort(404)
        lines = c.execute("SELECT * FROM sales_order_items WHERE order_id=?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, lines=lines)


@app.route("/orders/<int:order_id>/action", methods=["POST"])
@login_required
def order_action(order_id):
    action = request.form.get("action")
    with conn() as c:
        order = c.execute("SELECT * FROM sales_orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            abort(404)
        now = datetime.now().isoformat(timespec="seconds")
        if action == "confirm" and order["status"] == "draft":
            c.execute("UPDATE sales_orders SET status='confirmed', confirmed_at=? WHERE id=?", (now, order_id))
        elif action == "dispatch" and order["status"] == "confirmed":
            # deduct stock
            lines = c.execute("SELECT item_id, qty, free_qty FROM sales_order_items WHERE order_id=?", (order_id,)).fetchall()
            for ln in lines:
                if ln["item_id"]:
                    total_out = (ln["qty"] or 0) + (ln["free_qty"] or 0)
                    c.execute("UPDATE wholesale_items SET stock=MAX(0, stock-?) WHERE id=?", (total_out, ln["item_id"]))
            c.execute("UPDATE sales_orders SET status='dispatched', dispatched_at=? WHERE id=?", (now, order_id))
        elif action == "invoice" and order["status"] == "dispatched":
            inv_no = next_invoice_no()
            shop = c.execute("SELECT credit_days FROM retail_shops WHERE id=?", (order["shop_id"],)).fetchone()
            due = (date.today() + timedelta(days=shop["credit_days"] or 30)).isoformat()
            c.execute("""INSERT INTO invoices (invoice_no, order_id, shop_id, due_date, total)
                         VALUES (?,?,?,?,?)""",
                      (inv_no, order_id, order["shop_id"], due, order["total"]))
            c.execute("UPDATE sales_orders SET status='invoiced', invoiced_at=? WHERE id=?", (now, order_id))
        elif action == "cancel" and order["status"] in ("draft", "confirmed"):
            c.execute("UPDATE sales_orders SET status='cancelled' WHERE id=?", (order_id,))
        else:
            flash("Action not allowed at current status.", "err")
            return redirect(url_for("order_detail", order_id=order_id))
    audit(session.get("ws_user"), action, "order", order_id, order["order_no"])
    if action == "confirm":
        # Lazy import: by request time wsgi.py has already loaded whatsapp.py
        # into sys.modules, this is just a cache lookup, not a re-import -
        # avoids a circular import at module-load time (whatsapp.py imports
        # from app.py). Never let a notification failure break the confirm.
        try:
            import whatsapp
            whatsapp.notify_order_confirmed(order_id)
        except Exception:
            pass
    flash(f"Order {action}ed.", "ok")
    return redirect(url_for("order_detail", order_id=order_id))


# ═════════════════════════════════════════════════════════════════════
#  INVOICES
# ═════════════════════════════════════════════════════════════════════
@app.route("/invoices")
@login_required
def invoices():
    status = request.args.get("status") or ""
    with conn() as c:
        base_q = """SELECT i.*, s.name shop_name, s.code shop_code
                    FROM invoices i JOIN retail_shops s ON s.id=i.shop_id"""
        if status == "overdue":
            q = base_q + " WHERE i.status!='paid' AND i.due_date<date('now') ORDER BY i.due_date ASC LIMIT 300"
            rows = c.execute(q).fetchall()
        elif status:
            rows = c.execute(base_q + " WHERE i.status=? ORDER BY i.id DESC LIMIT 300", (status,)).fetchall()
        else:
            rows = c.execute(base_q + " ORDER BY i.id DESC LIMIT 300").fetchall()
    return render_template("invoices.html", invoices=rows, status=status)


@app.route("/invoices/<int:inv_id>")
@login_required
def invoice_detail(inv_id):
    with conn() as c:
        inv = c.execute("""SELECT i.*, s.name shop_name, s.code shop_code, s.gstin shop_gstin,
                                  s.address shop_address, s.city shop_city, s.drug_license shop_dl
                           FROM invoices i JOIN retail_shops s ON s.id=i.shop_id
                           WHERE i.id=?""", (inv_id,)).fetchone()
        if not inv:
            abort(404)
        lines = c.execute("""SELECT * FROM sales_order_items WHERE order_id=?""", (inv["order_id"],)).fetchall() if inv["order_id"] else []
        pays = c.execute("SELECT * FROM payments WHERE invoice_id=? ORDER BY id", (inv_id,)).fetchall()
    company = {
        "name": COMPANY_NAME, "gstin": COMPANY_GSTIN,
        "address": COMPANY_ADDRESS, "phone": COMPANY_PHONE,
    }
    upi_configured, upi_link = False, ""
    try:
        import upi
        upi_configured = upi.upi_configured()
        if upi_configured:
            upi_link = upi.build_upi_link(round((inv["total"] or 0) - (inv["paid"] or 0), 2), inv["invoice_no"])
    except ImportError:
        pass
    return render_template("invoice_detail.html", inv=inv, lines=lines, pays=pays, company=company,
                           upi_configured=upi_configured, upi_link=upi_link)


@app.route("/invoices/<int:inv_id>/pay", methods=["POST"])
@login_required
def invoice_pay(inv_id):
    amount = float(request.form.get("amount") or 0)
    method = request.form.get("method") or "cash"
    reference = request.form.get("reference", "").strip()
    if amount <= 0:
        flash("Enter a valid amount.", "err")
        return redirect(url_for("invoice_detail", inv_id=inv_id))
    with conn() as c:
        inv = c.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
        if not inv:
            abort(404)
        c.execute("""INSERT INTO payments (shop_id, invoice_id, amount, method, reference)
                     VALUES (?,?,?,?,?)""",
                  (inv["shop_id"], inv_id, amount, method, reference))
        new_paid = (inv["paid"] or 0) + amount
        status = "paid" if new_paid >= (inv["total"] or 0) - 0.01 else "partial"
        c.execute("UPDATE invoices SET paid=?, status=? WHERE id=?", (new_paid, status, inv_id))
    audit(session.get("ws_user"), "payment", "invoice", inv_id, f"₹{amount} via {method}")
    flash("Payment recorded.", "ok")
    return redirect(url_for("invoice_detail", inv_id=inv_id))


# ═════════════════════════════════════════════════════════════════════
#  LEDGER (outstanding across all shops)
# ═════════════════════════════════════════════════════════════════════
@app.route("/ledger")
@login_required
def ledger():
    with conn() as c:
        rows = c.execute("""
            SELECT s.id, s.code, s.name, s.phone, s.credit_limit, s.credit_days,
                   COALESCE(SUM(CASE WHEN i.status!='paid' THEN i.total-i.paid ELSE 0 END), 0) outstanding,
                   COALESCE(SUM(CASE WHEN i.status!='paid' AND i.due_date<date('now') THEN i.total-i.paid ELSE 0 END), 0) overdue,
                   COUNT(CASE WHEN i.status!='paid' THEN 1 END) open_bills
            FROM retail_shops s LEFT JOIN invoices i ON i.shop_id=s.id
            GROUP BY s.id
            HAVING outstanding > 0
            ORDER BY overdue DESC, outstanding DESC
        """).fetchall()
    total_out = sum(r["outstanding"] for r in rows)
    total_over = sum(r["overdue"] for r in rows)
    return render_template("ledger.html", rows=rows, total_out=total_out, total_over=total_over)


# ═════════════════════════════════════════════════════════════════════
#  DELIVERY ROUTES
# ═════════════════════════════════════════════════════════════════════
@app.route("/routes")
@login_required
def routes():
    with conn() as c:
        routes_ = c.execute("SELECT * FROM delivery_routes ORDER BY name").fetchall()
        routes_with_shops = []
        for r in routes_:
            shops = c.execute("SELECT id, code, name, phone, city FROM retail_shops WHERE route_id=? ORDER BY name", (r["id"],)).fetchall()
            routes_with_shops.append({"route": dict(r), "shops": [dict(s) for s in shops]})
    return render_template("routes.html", data=routes_with_shops)


@app.route("/routes/save", methods=["POST"])
@login_required
def route_save():
    d = request.form
    rid = d.get("id")
    name = (d.get("name") or "").strip()
    dow = (d.get("day_of_week") or "").strip()
    salesman = (d.get("salesman") or "").strip()
    if not name:
        flash("Route name required.", "err")
        return redirect(url_for("routes"))
    with conn() as c:
        if rid:
            c.execute("UPDATE delivery_routes SET name=?, day_of_week=?, salesman=? WHERE id=?", (name, dow, salesman, rid))
        else:
            c.execute("INSERT INTO delivery_routes (name, day_of_week, salesman) VALUES (?,?,?)", (name, dow, salesman))
    flash("Route saved.", "ok")
    return redirect(url_for("routes"))


# ═════════════════════════════════════════════════════════════════════
#  PUBLIC CATALOG (no login) — retail shops can browse + place orders
# ═════════════════════════════════════════════════════════════════════
@app.route("/catalog")
def catalog():
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    with conn() as c:
        cats = [r["category"] for r in c.execute("SELECT DISTINCT category FROM wholesale_items WHERE category!='' ORDER BY category").fetchall()]
        if q:
            like = f"%{q}%"
            rows = c.execute(
                "SELECT * FROM wholesale_items WHERE status='active' AND (name LIKE ? OR generic LIKE ?) ORDER BY name LIMIT 200",
                (like, like),
            ).fetchall()
        elif category:
            rows = c.execute("SELECT * FROM wholesale_items WHERE status='active' AND category=? ORDER BY name LIMIT 200", (category,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM wholesale_items WHERE status='active' ORDER BY name LIMIT 100").fetchall()
    # Lazy import: website.py does `from app import app, conn, ...` at module
    # level, so app.py importing it at import time would be circular. By the
    # time a request is being handled, website.py has long since finished
    # loading. sv() carries the same DEFAULTS fallback /company uses, so the
    # catalog header shows the tenant's real name instead of the env-var
    # COMPANY_NAME meant only for the pre-multi-tenant fallback DB.
    import website
    company_name = website.sv("site.company")
    return render_template("catalog.html", items=rows, categories=cats, q=q, category=category,
                           company=company_name, public_catalog_slug=getattr(g, "public_catalog_slug", None))


@app.route("/catalog/search")
def catalog_search():
    """
    JSON search for the catalog page's live-search box.

    Deliberately does NOT reuse /api/items: that endpoint resolves its
    tenant from session["tenant"], but an anonymous catalog visitor never
    has one — enter_tenant() (called by public_catalog() on the initial
    page load) only binds g for that single request, not the session, so a
    follow-up fetch() from the browser would silently fall back to the
    empty pre-multi-tenant DB and return zero results. Take the slug
    explicitly instead, exactly like public_catalog()/public_catalog_order()
    already do.
    """
    slug = (request.args.get("slug") or "").strip()
    if slug:
        import tenancy
        tenancy.enter_tenant(slug)
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit") or 15), 50)
    if len(q) < 2:
        return jsonify([])
    like = f"%{q}%"
    with conn() as c:
        rows = c.execute(
            "SELECT id, name, generic, manufacturer, pack_size, mrp, ptr, scheme FROM wholesale_items "
            "WHERE status='active' AND (name LIKE ? OR generic LIKE ?) ORDER BY name LIMIT ?",
            (like, like, limit),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


def _catalog_redirect():
    """
    Back to the catalog the visitor actually came from. The tenant-scoped
    public_catalog() wrapper stamps g.public_catalog_slug before calling
    through here — without that, a redirect to bare url_for('catalog')
    would lose the tenant (no session on a public link) and 404/misbehave.
    """
    slug = getattr(g, "public_catalog_slug", None)
    return redirect(url_for("public_catalog", slug=slug)) if slug else redirect(url_for("catalog"))


@app.route("/catalog/order", methods=["POST"])
def catalog_order():
    shop_code = (request.form.get("shop_code") or "").strip().upper()
    item_ids = request.form.getlist("item_id[]")
    qtys = request.form.getlist("qty[]")
    notes = request.form.get("notes", "").strip()
    contact = request.form.get("contact", "").strip()

    if not shop_code:
        flash("Please enter your shop code so we can identify you.", "err")
        return _catalog_redirect()

    with conn() as c:
        shop = c.execute("SELECT * FROM retail_shops WHERE code=? OR phone=? OR whatsapp=?",
                         (shop_code, shop_code, shop_code)).fetchone()
        if not shop:
            # auto-create a pending shop entry so wholesaler can approve later
            cur = c.execute(
                "INSERT INTO retail_shops (code, name, phone, notes, status) VALUES (?,?,?,?,?)",
                (shop_code, f"[Pending] {shop_code}", contact, "auto-created from public catalog order", "hold"),
            )
            shop_id = cur.lastrowid
            shop = c.execute("SELECT * FROM retail_shops WHERE id=?", (shop_id,)).fetchone()

        order_no = next_order_no()
        cur = c.execute(
            "INSERT INTO sales_orders (order_no, shop_id, notes, source, created_by, status) VALUES (?,?,?,?,?,?)",
            (order_no, shop["id"], notes, "catalog", contact or shop_code, "draft"),
        )
        order_id = cur.lastrowid
        added = 0
        for iid, q_str in zip(item_ids, qtys):
            if not iid or not q_str:
                continue
            qty = int(q_str or 0)
            if qty <= 0:
                continue
            item = c.execute("SELECT * FROM wholesale_items WHERE id=?", (int(iid),)).fetchone()
            if not item:
                continue
            rate = rate_for_shop(item, shop["price_tier"])
            free = 0
            if item["scheme"]:
                try:
                    b, bs = item["scheme"].split("+")
                    b, bs = int(b), int(bs)
                    if b > 0:
                        free = (qty // b) * bs
                except Exception:
                    pass
            c.execute("""INSERT INTO sales_order_items
                (order_id, item_id, item_name, pack_size, qty, free_qty, rate, gst_rate, amount)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (order_id, item["id"], item["name"], item["pack_size"], qty, free, rate, item["gst_rate"], qty * rate))
            added += 1

    if added == 0:
        with conn() as c:
            c.execute("DELETE FROM sales_orders WHERE id=?", (order_id,))
        flash("No valid items in your order. Add quantities and resubmit.", "err")
        return _catalog_redirect()

    compute_order_totals(order_id)
    audit(shop_code, "public_order", "order", order_id, order_no)
    return render_template("catalog_thanks.html", order_no=order_no, shop_code=shop_code)


# ── Tenant-scoped public entry point — THE URL to actually share/QR-code.
#    Bare /catalog above has no way to know the tenant without a session
#    (see enter_tenant()'s docstring for why that's a real bug, not a
#    style preference); a fresh visitor with no prior login must arrive
#    through here so the tenant comes from the URL itself. ──────────────
@app.route("/c/<slug>/catalog")
def public_catalog(slug):
    import tenancy
    tenancy.enter_tenant(slug)
    g.public_catalog_slug = slug
    return catalog()


@app.route("/c/<slug>/catalog/order", methods=["POST"])
def public_catalog_order(slug):
    import tenancy
    tenancy.enter_tenant(slug)
    g.public_catalog_slug = slug
    return catalog_order()


# WhatsApp inbound/outbound now lives in whatsapp.py (Twilio webhook +
# TwiML replies + real send capability), imported via wsgi.py. Removed
# from here to avoid double-registering /api/whatsapp/inbound.


# ═════════════════════════════════════════════════════════════════════
#  SETTINGS + HEALTH
# ═════════════════════════════════════════════════════════════════════
@app.route("/settings")
@login_required
def settings_page():
    return render_template(
        "settings.html",
        company=dict(name=COMPANY_NAME, gstin=COMPANY_GSTIN, address=COMPANY_ADDRESS, phone=COMPANY_PHONE),
        db_path=DB_PATH,
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "medivision-wholesale"})


# ═════════════════════════════════════════════════════════════════════
#  BOOT
# ═════════════════════════════════════════════════════════════════════
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    app.run(host="0.0.0.0", port=port, debug=False)
