"""
Multi-user roles per company
=============================

Until now, everyone at a distributor shared ONE company password (set at
onboarding) and logged in as an undifferentiated "ws_user" with no role -
anyone who knew it could edit payroll, see the ledger, and confirm
purchase orders. This adds real per-person accounts with three roles:

    owner       — everything, including staff management and customize
    accountant  — financial: invoices, ledger, expenses, payroll, reports
    salesman    — operational: shops, items, orders, wanted-list, routes

BACKWARD COMPATIBLE BY DESIGN: the original company-password login still
works exactly as before (as 'owner') when no username is given — see
tenancy.py's portal_login(). Staff accounts are additive, created by an
owner at /users once they want to hand out narrower access instead of
sharing the master password.

Financial routes are locked to owner+accountant via @role_required.
Everything else stays reachable by any signed-in role - a salesman not
being able to see the ledger is a real boundary worth enforcing; a
salesman not being able to see the item list would just break their job
for no security benefit.
"""
from __future__ import annotations

import secrets
import hashlib
import functools

from flask import request, redirect, url_for, render_template, session, flash, abort

from app import app, conn, login_required, audit

# Duplicated from tenancy.hash_pw rather than imported: tenancy.py must load
# LAST (it rebinds every other module's conn()), but this module's top-level
# `from app import app` needs to run before that - importing FROM tenancy
# here would create a load-order cycle. It's two lines; not worth the
# coupling.
def hash_pw(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode()).hexdigest()

USERS_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS staff_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'salesman',   -- owner | salesman | accountant
    pass_salt     TEXT NOT NULL,
    pass_hash     TEXT NOT NULL,
    status        TEXT DEFAULT 'active',
    created_at    TEXT DEFAULT (datetime('now')),
    last_login    TEXT DEFAULT ''
);
"""

with conn() as _c:
    _c.executescript(USERS_SCHEMA)

ROLES = {
    "owner":      "Owner (full access)",
    "accountant": "Accountant (invoices, ledger, expenses, payroll, reports)",
    "salesman":   "Salesman (shops, items, orders, wanted-list, routes)",
}


def find_staff_user(username: str, password: str):
    """Returns the staff_users row if username+password match, else None."""
    if not username:
        return None
    with conn() as c:
        row = c.execute("SELECT * FROM staff_users WHERE username=? AND status='active'", (username,)).fetchone()
    if not row or hash_pw(password, row["pass_salt"]) != row["pass_hash"]:
        return None
    return row


def role_required(*allowed_roles):
    """
    Stacks with @login_required (put this one closer to the function).
    A role of 'owner' set at login (the master-password fallback, or a
    staff account explicitly created with role=owner) always has access
    regardless of what's listed here - owner means owner.
    """
    def deco(f):
        @functools.wraps(f)
        def wrap(*a, **k):
            role = session.get("role", "owner")   # sessions from before this feature existed = owner
            if role != "owner" and role not in allowed_roles:
                abort(403)
            return f(*a, **k)
        return wrap
    return deco


@app.route("/users")
@login_required
@role_required("owner")
def users_list():
    with conn() as c:
        rows = c.execute("SELECT * FROM staff_users ORDER BY status, name").fetchall()
    return render_template("users.html", users=rows, roles=ROLES)


@app.route("/users/save", methods=["POST"])
@login_required
@role_required("owner")
def users_save():
    d = request.form
    username = (d.get("username") or "").strip().lower()
    name = (d.get("name") or "").strip()
    role = d.get("role") if d.get("role") in ROLES else "salesman"
    password = d.get("password") or ""

    if not username or not name:
        flash("Username and name are required.", "err")
        return redirect(url_for("users_list"))
    if not password or len(password) < 4:
        flash("Password must be at least 4 characters.", "err")
        return redirect(url_for("users_list"))

    salt = secrets.token_hex(8)
    with conn() as c:
        if c.execute("SELECT 1 FROM staff_users WHERE username=?", (username,)).fetchone():
            flash(f"Username '{username}' is already taken.", "err")
            return redirect(url_for("users_list"))
        c.execute("""INSERT INTO staff_users (username, name, role, pass_salt, pass_hash)
                     VALUES (?,?,?,?,?)""", (username, name, role, salt, hash_pw(password, salt)))
    audit(session.get("ws_user"), "create_user", "staff_user", None, f"{name} ({role})")
    flash(f"Created login for {name}. Username: {username}", "ok")
    return redirect(url_for("users_list"))


@app.route("/users/<int:uid>/<action>", methods=["POST"])
@login_required
@role_required("owner")
def users_action(uid, action):
    if action not in ("suspend", "activate", "resetpw"):
        abort(400)
    with conn() as c:
        u = c.execute("SELECT * FROM staff_users WHERE id=?", (uid,)).fetchone()
        if not u:
            abort(404)
        if action == "suspend":
            c.execute("UPDATE staff_users SET status='suspended' WHERE id=?", (uid,))
            flash(f"{u['name']} suspended.", "ok")
        elif action == "activate":
            c.execute("UPDATE staff_users SET status='active' WHERE id=?", (uid,))
            flash(f"{u['name']} reactivated.", "ok")
        elif action == "resetpw":
            pw = secrets.token_urlsafe(8)
            salt = secrets.token_hex(8)
            c.execute("UPDATE staff_users SET pass_salt=?, pass_hash=? WHERE id=?", (salt, hash_pw(pw, salt), uid))
            flash(f"New password for {u['name']}: {pw} — copy this now, it can't be shown again.", "ok")
    audit(session.get("ws_user"), action, "staff_user", uid, "")
    return redirect(url_for("users_list"))


# ══════════════════════════════════════════════════════════════════════
#  RETROFIT role_required ONTO ROUTES DEFINED IN OTHER MODULES
#
#  app.py cannot import role_required directly - users.py's own first
#  line imports FROM app.py, so the reverse import at app.py's module-load
#  time would be a real circular import (app.py isn't finished loading
#  when users.py tries to import from it back). Instead, wrap the already-
#  registered view functions here, in users.py, which loads after
#  app.py/erp.py/website.py have all registered their routes (see
#  wsgi.py's import order) - by the time this file runs, every endpoint
#  below already exists in app.view_functions.
# ══════════════════════════════════════════════════════════════════════
_FINANCIAL_ENDPOINTS = ["invoices", "invoice_detail", "invoice_pay", "ledger",
                        "expenses", "expense_save", "payroll", "payroll_advance", "reports"]
_OWNER_ONLY_ENDPOINTS = ["customize", "custom_field_add", "custom_field_del", "site_admin"]


def _lock_down_routes():
    missing = []
    for endpoint in _FINANCIAL_ENDPOINTS:
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = role_required("owner", "accountant")(app.view_functions[endpoint])
        else:
            missing.append(endpoint)
    for endpoint in _OWNER_ONLY_ENDPOINTS:
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = role_required("owner")(app.view_functions[endpoint])
        else:
            missing.append(endpoint)
    if missing:
        # Not fatal - a renamed/removed route just stays unrestricted -
        # but worth knowing about rather than silently no-op'ing.
        import logging
        logging.warning("[users] role lock-down: endpoint(s) not found, left unrestricted: %s", missing)


_lock_down_routes()
