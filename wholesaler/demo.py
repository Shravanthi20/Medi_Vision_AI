"""
Public, no-password wholesaler demo — for prospects like Medistar
====================================================================

/demo — one click, no password, drops a visitor straight into a full,
EDITABLE owner session on the isolated 'demo' tenant. Nothing they do
here can touch any real company's data — it's the same per-tenant-
database isolation every other tenant gets, just entered without the
usual login step.

/demo/reset — wipes the demo tenant back to the standard sample dataset.
Deliberately public (no auth): the blast radius of abuse is "the demo
looks different for the next visitor", not a security incident. A
visible Reset button in the demo banner lets anyone (Medistar included)
start over without waiting on us.

The RETAILER/shop side (/shop/login) is completely untouched by this -
that stays exactly as password-gated as it already was. Only the
wholesaler ADMIN side gets an open door, and only into this one
sandbox tenant.
"""
from __future__ import annotations

from flask import redirect, url_for, session, g, request

from app import app, conn
import tenancy
from seed import SHOPS, ITEMS, ROUTES, SUPPLIERS, STAFF

DEMO_SLUG = "demo"


def reset_demo_data():
    """Wipe and reload the demo tenant's sample data. Idempotent, self-contained."""
    with conn() as c:
        # Order matters for FKs; children before parents.
        for tbl in ("sales_order_items", "sales_orders", "invoices", "payments",
                    "purchase_order_items", "purchase_orders", "wanted_lines",
                    "wanted_uploads", "item_aliases", "demand_log", "expenses",
                    "attendance", "advances", "payslips", "custom_field_values",
                    "shop_logins", "retail_shops", "wholesale_items", "suppliers",
                    "staff", "delivery_routes", "audit_log"):
            try:
                c.execute(f"DELETE FROM {tbl}")
            except Exception:
                pass  # table may not exist yet on a very first run - fine

        route_ids = {}
        for name, dow, sm in ROUTES:
            cur = c.execute("INSERT INTO delivery_routes (name, day_of_week, salesman) VALUES (?,?,?)", (name, dow, sm))
            route_ids[name] = cur.lastrowid

        for i, (code, name, cp, phone, city, gstin, credit, days, tier) in enumerate(SHOPS):
            rid = list(route_ids.values())[i % len(route_ids)]
            c.execute("""INSERT INTO retail_shops
                (code, name, contact_person, phone, whatsapp, city, gstin, credit_limit, credit_days, price_tier, route_id, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,'active')""",
                (code, name, cp, phone, phone, city, gstin, credit, days, tier, rid))

        for row in ITEMS:
            c.execute("""INSERT INTO wholesale_items
                (code, name, generic, manufacturer, pack_size, mrp, ptr, ptr_b, ptr_c, gst_rate, scheme, stock, category, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active')""", row)

        for code, name, cp, phone, city, gstin, terms in SUPPLIERS:
            c.execute("""INSERT INTO suppliers (code, name, contact_person, phone, address, gstin, payment_terms)
                         VALUES (?,?,?,?,?,?,?)""", (code, name, cp, phone, city, gstin, terms))

        from datetime import date, timedelta
        import random
        random.seed(7)
        for name, role, phone, base, ot in STAFF:
            c.execute("""INSERT INTO staff (name, role, phone, join_date, base_salary, ot_rate_per_hr, status)
                         VALUES (?,?,?,?,?,?,'active')""",
                      (name, role, phone, (date.today() - timedelta(days=random.randint(60, 900))).isoformat(), base, ot))

        # A handful of orders/invoices so the dashboard isn't a wall of zeros.
        shops = c.execute("SELECT id, price_tier FROM retail_shops").fetchall()
        items = c.execute("SELECT * FROM wholesale_items").fetchall()
        for i in range(15):
            shop = random.choice(shops)
            days_ago = random.randint(0, 25)
            ord_date = (date.today() - timedelta(days=days_ago)).isoformat()
            n = c.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0]
            order_no = f"SO/DEMO/{n + 1:05d}"
            cur = c.execute("""INSERT INTO sales_orders (order_no, shop_id, order_date, status, source, created_by)
                               VALUES (?,?,?,?,'seed','demo-reset')""",
                            (order_no, shop["id"], ord_date, random.choice(["invoiced", "invoiced", "dispatched", "draft"])))
            oid = cur.lastrowid
            subtotal = gst = 0.0
            for it in random.sample(items, min(5, len(items))):
                qty = random.randint(2, 15)
                tier = shop["price_tier"]
                rate = it["ptr_b"] if tier == "B" and it["ptr_b"] else (it["ptr_c"] if tier == "C" and it["ptr_c"] else it["ptr"])
                amt = qty * rate
                subtotal += amt
                gst += amt * it["gst_rate"] / 100
                c.execute("""INSERT INTO sales_order_items
                    (order_id, item_id, item_name, pack_size, qty, rate, gst_rate, amount)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (oid, it["id"], it["name"], it["pack_size"], qty, rate, it["gst_rate"], amt))
            total = subtotal + gst
            c.execute("UPDATE sales_orders SET subtotal=?, gst_amount=?, total=? WHERE id=?", (subtotal, gst, total, oid))

            if c.execute("SELECT status FROM sales_orders WHERE id=?", (oid,)).fetchone()["status"] == "invoiced":
                inv_n = c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
                inv_no = f"INV/DEMO/{inv_n + 1:05d}"
                due = (date.today() - timedelta(days=days_ago) + timedelta(days=30)).isoformat()
                paid = total if random.random() < 0.4 else 0
                status = "paid" if paid >= total else "open"
                c.execute("""INSERT INTO invoices (invoice_no, order_id, shop_id, invoice_date, due_date, total, paid, status)
                             VALUES (?,?,?,?,?,?,?,?)""", (inv_no, oid, shop["id"], ord_date, due, total, paid, status))


def _rename_demo_company():
    """One-time: the platform-side display name for slug=demo -> Medistar."""
    with tenancy.platform_conn() as pc:
        pc.execute("UPDATE companies SET name=? WHERE slug=?", ("Medistar", DEMO_SLUG))


@app.route("/demo")
def demo_enter():
    with tenancy.platform_conn() as pc:
        comp = pc.execute("SELECT * FROM companies WHERE slug=? AND status='active'", (DEMO_SLUG,)).fetchone()
    if not comp:
        return "Demo is temporarily unavailable.", 503

    session.clear()
    session["tenant"] = DEMO_SLUG
    session["tenant_name"] = comp["name"]
    session["ws_user"] = "Guest"
    session["role"] = "owner"
    session["is_demo"] = True
    g.tenant_slug, g.tenant_db = DEMO_SLUG, tenancy.tenant_db_path(DEMO_SLUG)
    return redirect(url_for("dashboard"))


@app.route("/demo/reset", methods=["POST"])
def demo_reset_route():
    g.tenant_slug, g.tenant_db = DEMO_SLUG, tenancy.tenant_db_path(DEMO_SLUG)
    reset_demo_data()
    session.clear()
    session["tenant"] = DEMO_SLUG
    session["tenant_name"] = "Medistar"
    session["ws_user"] = "Guest"
    session["role"] = "owner"
    session["is_demo"] = True
    return redirect(url_for("dashboard"))
