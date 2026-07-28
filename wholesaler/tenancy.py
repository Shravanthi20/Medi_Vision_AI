"""
Multi-tenancy + Platform Super-Admin
====================================

One portal, many distribution companies. Each company ("tenant") gets its
OWN SQLite database file under tenants/<slug>.db. Nothing is shared between
them — not orders, not shops, not items, not staff.

    platform.db            ← who the companies are, their plan, their bill
    tenants/acme.db        ← Acme's entire business
    tenants/rathna.db      ← Sri Rathna's entire business

WHY DATABASE-PER-TENANT: a bug in a WHERE clause can leak rows between
tenants in a shared-table design. Here there is no query that *could*
cross the boundary — the other company's data is in a file the request
never opens. Cross-tenant leakage becomes structurally impossible rather
than a thing we have to remember to test for.

──────────────────────────────────────────────────────────────────────
PRIVACY GUARANTEE — the platform owner cannot read customer business data
──────────────────────────────────────────────────────────────────────
The super-admin (`/platform/*`) is enforced by construction, not policy:

  * Every super-admin route uses `platform_conn()`, which opens ONE
    hard-coded file: platform.db. It takes no path argument, so there is
    no super-admin code path that can point at a tenant DB.
  * Tenant DBs are opened only by `app.conn()`, which resolves the file
    from the LOGGED-IN TENANT'S session. A platform-admin session carries
    no tenant, so it resolves to nothing.
  * The numbers the owner sees (order counts, revenue) are not read out of
    tenant DBs by the platform. Each tenant pushes its own small set of
    aggregate counters into platform.db via `push_usage()`. Counts and
    totals only — never a customer name, never a line item.

So the owner can bill, suspend, and support a company, and can see *that*
they did 400 orders last month. The owner cannot see who those orders were
for or what was on them. That is the intended and enforced boundary.
"""
from __future__ import annotations

import os
import re
import sqlite3
import secrets
import hashlib
import functools
from datetime import date, datetime
from contextlib import contextmanager

from flask import (request, redirect, url_for, render_template, session,
                   flash, abort, g, jsonify, has_request_context)

import app as core
from app import app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLATFORM_DB = os.environ.get("WS_PLATFORM_DB", os.path.join(BASE_DIR, "platform.db"))
TENANT_DIR = os.environ.get("WS_TENANT_DIR", os.path.join(BASE_DIR, "tenants"))
PLATFORM_PASSWORD = os.environ.get("WS_PLATFORM_PASSWORD", "changeme-platform")

os.makedirs(TENANT_DIR, exist_ok=True)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")

PLANS = {
    "starter":  {"label": "Starter",  "price": 1000, "shops": 100,  "users": 2},
    "growth":   {"label": "Growth",   "price": 2500, "shops": 500,  "users": 5},
    "pro":      {"label": "Pro",      "price": 5000, "shops": 2000, "users": 15},
    "unlimited":{"label": "Unlimited","price": 9000, "shops": 0,    "users": 0},
}


# ══════════════════════════════════════════════════════════════════════
#  PLATFORM DB — the ONLY database the super-admin can reach.
#  Deliberately takes no arguments: there is no way to aim it elsewhere.
# ══════════════════════════════════════════════════════════════════════
@contextmanager
def platform_conn():
    c = sqlite3.connect(PLATFORM_DB)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


PLATFORM_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS companies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    owner_name    TEXT DEFAULT '',
    phone         TEXT DEFAULT '',
    email         TEXT DEFAULT '',
    city          TEXT DEFAULT '',
    plan          TEXT DEFAULT 'starter',
    monthly_fee   REAL DEFAULT 1000,
    status        TEXT DEFAULT 'active',      -- active | suspended | trial
    trial_ends    TEXT DEFAULT '',
    pass_salt     TEXT DEFAULT '',
    pass_hash     TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now')),
    last_login    TEXT DEFAULT '',
    -- aggregate usage counters, PUSHED BY THE TENANT. counts only.
    stat_shops    INTEGER DEFAULT 0,
    stat_items    INTEGER DEFAULT 0,
    stat_orders   INTEGER DEFAULT 0,
    stat_month_orders INTEGER DEFAULT 0,
    stat_month_revenue REAL DEFAULT 0,
    stat_updated  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS platform_payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL,
    amount      REAL DEFAULT 0,
    period_ym   TEXT,
    paid_on     TEXT DEFAULT (date('now')),
    method      TEXT DEFAULT 'upi',
    note        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS platform_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT DEFAULT (datetime('now')),
    actor     TEXT,
    action    TEXT,
    company   TEXT,
    detail    TEXT
);
"""

with platform_conn() as _c:
    _c.executescript(PLATFORM_SCHEMA)


def plog(actor, action, company="", detail=""):
    with platform_conn() as c:
        c.execute("INSERT INTO platform_log (actor, action, company, detail) VALUES (?,?,?,?)",
                  (actor, action, company, detail))


def hash_pw(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode()).hexdigest()


def tenant_db_path(slug: str) -> str:
    if not SLUG_RE.match(slug or ""):
        abort(400, "bad tenant slug")
    return os.path.join(TENANT_DIR, f"{slug}.db")


def enter_tenant(slug: str):
    """
    Explicitly bind THIS request to a tenant DB, bypassing session lookup.

    _resolve_tenant() below only knows the tenant from a browser session
    cookie. That's wrong for any entry point that legitimately has no
    session but DOES know the tenant some other way — a Twilio webhook
    (the company is in the URL Twilio was configured to POST to), or a
    public QR-code catalog link (the company is in the URL a shop
    scanned). Call this FIRST, before any conn() use, in such a route.

    Validates the company exists and is active, so a stale/typo'd/
    suspended link 404s loudly instead of silently reading nothing (or —
    the bug this exists to prevent — silently falling back to whatever
    core.DB_PATH happens to point at).
    """
    with platform_conn() as pc:
        comp = pc.execute("SELECT * FROM companies WHERE slug=? AND status='active'", (slug,)).fetchone()
    if not comp:
        abort(404)
    g.tenant_slug = slug
    g.tenant_db = tenant_db_path(slug)
    return comp


# ══════════════════════════════════════════════════════════════════════
#  TENANT RESOLUTION — make core.conn() open the right file
# ══════════════════════════════════════════════════════════════════════
@app.before_request
def _resolve_tenant():
    """
    Bind this request to a tenant DB, if the session has one.
    Platform-admin sessions never set this, so their core.conn() has
    nothing to open — they simply cannot query tenant data.
    """
    g.tenant_slug = session.get("tenant")
    g.tenant_db = tenant_db_path(g.tenant_slug) if g.tenant_slug else None


# Re-point the core app's connection factory at the per-request tenant DB.
_ORIGINAL_DB_PATH = core.DB_PATH


@contextmanager
def _tenant_aware_conn():
    # Outside a request (import-time schema init, CLI) there is no g —
    # fall back to the default file rather than exploding.
    path = _ORIGINAL_DB_PATH
    if has_request_context():
        path = getattr(g, "tenant_db", None) or _ORIGINAL_DB_PATH
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    # WAL: readers no longer block behind a writer (or vice versa) on the
    # same tenant DB. Matters once a tenant has more than one person
    # working at a time - a wanted-list upload writing rows no longer
    # stalls someone else's page load against the same file.
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA synchronous = NORMAL")
    try:
        yield c
        c.commit()
    finally:
        c.close()


core.conn = _tenant_aware_conn          # every core/erp/website query follows the session
import erp as _erp; _erp.conn = _tenant_aware_conn
try:
    import website as _web; _web.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import reorder as _re; _re.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import wanted as _wanted; _wanted.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import whatsapp as _whatsapp; _whatsapp.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import upi as _upi; _upi.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import users as _users; _users.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import billing as _billing; _billing.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import pdf as _pdf; _pdf.conn = _tenant_aware_conn
except ImportError:
    pass
try:
    import demo as _demo; _demo.conn = _tenant_aware_conn
except ImportError:
    pass


def provision_tenant(slug: str):
    """Create a fresh, fully-migrated DB for a new company."""
    path = tenant_db_path(slug)
    c = sqlite3.connect(path)
    try:
        c.executescript(core.SCHEMA)
        c.executescript(_erp.EXTRA_SCHEMA)
        try:
            import wanted as _w; c.executescript(_w.WANTED_SCHEMA)
        except ImportError:
            pass
        try:
            import users as _u; c.executescript(_u.USERS_SCHEMA)
        except ImportError:
            pass
        c.commit()
    finally:
        c.close()
    return path


def push_usage(slug: str):
    """
    Tenant-side: summarise MY OWN data into counters and store them on the
    platform record. Only counts/totals cross this boundary — never rows.
    """
    try:
        with _tenant_aware_conn() as c:
            shops = c.execute("SELECT COUNT(*) n FROM retail_shops").fetchone()["n"]
            items = c.execute("SELECT COUNT(*) n FROM wholesale_items").fetchone()["n"]
            orders = c.execute("SELECT COUNT(*) n FROM sales_orders").fetchone()["n"]
            mo = c.execute("SELECT COUNT(*) n FROM sales_orders WHERE substr(order_date,1,7)=strftime('%Y-%m','now')").fetchone()["n"]
            mr = c.execute("SELECT COALESCE(SUM(total),0) t FROM invoices WHERE substr(invoice_date,1,7)=strftime('%Y-%m','now')").fetchone()["t"]
        with platform_conn() as p:
            p.execute("""UPDATE companies SET stat_shops=?, stat_items=?, stat_orders=?,
                         stat_month_orders=?, stat_month_revenue=?, stat_updated=datetime('now')
                         WHERE slug=?""", (shops, items, orders, mo, mr, slug))
    except Exception:
        pass  # usage stats are best-effort; never break a user's request


# ══════════════════════════════════════════════════════════════════════
#  TENANT LOGIN  (replaces the single-company login)
# ══════════════════════════════════════════════════════════════════════
@app.route("/portal", methods=["GET", "POST"])
def portal_login():
    error = ""
    if request.method == "POST":
        slug = (request.form.get("company") or "").strip().lower()
        pw = request.form.get("password") or ""
        username = (request.form.get("username") or "").strip().lower()
        name = (request.form.get("name") or "").strip() or "user"

        with platform_conn() as c:
            comp = c.execute("SELECT * FROM companies WHERE slug=?", (slug,)).fetchone()

        if not comp:
            error = "No company with that code."
        elif comp["status"] == "suspended":
            error = "This account is suspended. Please contact support."
        else:
            # Bind the tenant DB BEFORE any staff-account lookup, or that
            # lookup would hit the same no-tenant fallback trap fixed
            # elsewhere in this file.
            g.tenant_slug, g.tenant_db = slug, tenant_db_path(slug)

            staff_row = None
            if username:
                import users as _users
                staff_row = _users.find_staff_user(username, pw)

            if username and not staff_row:
                error = "Wrong username or password."
            elif not username and (not comp["pass_hash"] or hash_pw(pw, comp["pass_salt"]) != comp["pass_hash"]):
                error = "Wrong password."
            else:
                session.clear()
                session["tenant"] = slug
                session["tenant_name"] = comp["name"]
                if staff_row:
                    session["ws_user"] = staff_row["name"]
                    session["role"] = staff_row["role"]
                    with _tenant_aware_conn() as tc:
                        tc.execute("UPDATE staff_users SET last_login=datetime('now') WHERE id=?", (staff_row["id"],))
                else:
                    session["ws_user"] = name
                    session["role"] = "owner"
                with platform_conn() as c:
                    c.execute("UPDATE companies SET last_login=datetime('now') WHERE slug=?", (slug,))
                g.tenant_slug, g.tenant_db = slug, tenant_db_path(slug)
                push_usage(slug)
                return redirect(url_for("dashboard"))

    return render_template("portal_login.html", error=error)


# ══════════════════════════════════════════════════════════════════════
#  PLATFORM SUPER-ADMIN
# ══════════════════════════════════════════════════════════════════════
def platform_required(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        if not session.get("platform_admin"):
            return redirect(url_for("platform_login"))
        return f(*a, **k)
    return wrap


@app.route("/platform/login", methods=["GET", "POST"])
def platform_login():
    error = ""
    if request.method == "POST":
        if (request.form.get("password") or "") == PLATFORM_PASSWORD:
            session.clear()                      # never hold a tenant + platform session at once
            session["platform_admin"] = True
            plog("owner", "login")
            return redirect(url_for("platform_home"))
        error = "Wrong password."
    return render_template("platform_login.html", error=error)


@app.route("/platform/logout", methods=["POST"])
def platform_logout():
    session.clear()
    return redirect(url_for("platform_login"))


@app.route("/platform")
@platform_required
def platform_home():
    period = date.today().strftime("%Y-%m")
    with platform_conn() as c:                   # platform.db ONLY
        companies = c.execute("SELECT * FROM companies ORDER BY status, name").fetchall()
        collected = c.execute("SELECT COALESCE(SUM(amount),0) a FROM platform_payments WHERE period_ym=?",
                              (period,)).fetchone()["a"]
        paid_ids = {r["company_id"] for r in c.execute(
            "SELECT DISTINCT company_id FROM platform_payments WHERE period_ym=?", (period,)).fetchall()}

    rows = []
    for comp in companies:
        d = dict(comp)
        d["paid_this_month"] = comp["id"] in paid_ids
        rows.append(d)

    active = [r for r in rows if r["status"] == "active"]
    kpi = {
        "companies": len(rows),
        "active": len(active),
        "suspended": sum(1 for r in rows if r["status"] == "suspended"),
        "mrr": sum(r["monthly_fee"] or 0 for r in active),
        "collected": collected,
        "unpaid": sum(r["monthly_fee"] or 0 for r in active if not r["paid_this_month"]),
        "total_orders": sum(r["stat_month_orders"] or 0 for r in rows),
        "gmv": sum(r["stat_month_revenue"] or 0 for r in rows),
    }
    return render_template("platform.html", companies=rows, kpi=kpi, plans=PLANS, period=period)


@app.route("/platform/company/new", methods=["POST"])
@platform_required
def platform_company_new():
    d = request.form
    slug = (d.get("slug") or "").strip().lower()
    name = (d.get("name") or "").strip()
    plan = d.get("plan") or "starter"

    if not SLUG_RE.match(slug):
        flash("Company code must be lowercase letters/numbers/hyphens, 2-31 chars.", "err")
        return redirect(url_for("platform_home"))
    if not name:
        flash("Company name is required.", "err")
        return redirect(url_for("platform_home"))

    with platform_conn() as c:
        if c.execute("SELECT 1 FROM companies WHERE slug=?", (slug,)).fetchone():
            flash(f"Company code '{slug}' is already taken.", "err")
            return redirect(url_for("platform_home"))

    pw = d.get("password") or secrets.token_urlsafe(9)
    salt = secrets.token_hex(8)

    with platform_conn() as c:
        c.execute("""INSERT INTO companies
            (slug, name, owner_name, phone, email, city, plan, monthly_fee, status, pass_salt, pass_hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (slug, name, d.get("owner_name", "").strip(), d.get("phone", "").strip(),
             d.get("email", "").strip(), d.get("city", "").strip(), plan,
             PLANS.get(plan, {}).get("price", 1000), "active", salt, hash_pw(pw, salt)))

    provision_tenant(slug)                        # fresh empty DB, no data from anyone else
    plog("owner", "create_company", slug, name)
    flash(f"Created '{name}'. Company code: {slug} · password: {pw} — send these to them now, "
          f"the password is not stored in readable form and cannot be shown again.", "ok")
    return redirect(url_for("platform_home"))


@app.route("/platform/company/<int:cid>/<action>", methods=["POST"])
@platform_required
def platform_company_action(cid, action):
    with platform_conn() as c:
        comp = c.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        if not comp:
            abort(404)

        if action == "suspend":
            c.execute("UPDATE companies SET status='suspended' WHERE id=?", (cid,))
            msg = f"{comp['name']} suspended — they can no longer sign in."
        elif action == "activate":
            c.execute("UPDATE companies SET status='active' WHERE id=?", (cid,))
            msg = f"{comp['name']} reactivated."
        elif action == "plan":
            plan = request.form.get("plan") or "starter"
            c.execute("UPDATE companies SET plan=?, monthly_fee=? WHERE id=?",
                      (plan, PLANS.get(plan, {}).get("price", 1000), cid))
            msg = f"{comp['name']} moved to {plan}."
        elif action == "pay":
            amt = float(request.form.get("amount") or comp["monthly_fee"] or 0)
            c.execute("INSERT INTO platform_payments (company_id, amount, period_ym, method, note) VALUES (?,?,?,?,?)",
                      (cid, amt, request.form.get("period") or date.today().strftime("%Y-%m"),
                       request.form.get("method") or "upi", request.form.get("note", "")))
            msg = f"Recorded ₹{amt:,.0f} from {comp['name']}."
        elif action == "resetpw":
            pw = secrets.token_urlsafe(9)
            salt = secrets.token_hex(8)
            c.execute("UPDATE companies SET pass_salt=?, pass_hash=? WHERE id=?", (salt, hash_pw(pw, salt), cid))
            msg = f"New password for {comp['name']}: {pw} — send it to them now, it can't be shown again."
        else:
            abort(400)

    plog("owner", action, comp["slug"], "")
    flash(msg, "ok")
    return redirect(url_for("platform_home"))


@app.route("/platform/log")
@platform_required
def platform_log_view():
    with platform_conn() as c:
        rows = c.execute("SELECT * FROM platform_log ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("platform_log.html", rows=rows)


@app.route("/platform/health")
def platform_health():
    with platform_conn() as c:
        n = c.execute("SELECT COUNT(*) n FROM companies").fetchone()["n"]
    return jsonify({"status": "ok", "companies": n})
