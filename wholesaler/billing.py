"""
Counter billing + credit control
================================

The order → confirm → dispatch → invoice path already exists and is right
for a shop that ORDERS AHEAD (phone, WhatsApp, portal, wanted-list). It is
wrong for the other half of a distributor's day: a retailer standing at
the counter, or a van salesman billing on the spot. Making them create an
order and then click through three status changes to hand over a bill is
four screens for what should be one.

COUNTER SALE (/billing) collapses that into a single screen: pick the
shop, search items, hit Bill. Behind the scenes it still writes the same
rows the ordered path does — a sales_order (source='counter', already
'invoiced'), its line items, the stock deduction, and an invoice — so
reports, ledger, outstanding and GST returns see one consistent shape of
data regardless of how the sale started. Nothing downstream needs to know
about counter sales as a special case.

CREDIT CONTROL is the other half. A distributor's real risk isn't a
mispriced line, it's handing goods to a shop that already owes more than
it should. shop_outstanding() has always been able to answer "how much do
they owe" but nothing ever asked before releasing stock. Now both the
counter screen and order confirmation check it.

Deliberately a WARNING WITH AN OVERRIDE, not a hard block: the owner
frequently has context the system doesn't ("he's paying tomorrow, his
brother runs the other shop"). A hard block would just get worked around
by billing under a different shop, which is worse — the debt still exists
but is now attributed to the wrong customer. So: show the number, make
them tick a box, and log who overrode it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import (request, redirect, url_for, render_template, session,
                   flash, jsonify, abort)

from app import (app, conn, login_required, audit, rate_for_shop,
                 next_order_no, next_invoice_no, compute_order_totals,
                 shop_outstanding)


def credit_status(shop_id):
    """
    Everything the UI needs to decide whether to warn. Returns limit,
    current outstanding, and how much headroom is left. A limit of 0 means
    'not set' rather than 'zero credit allowed' — that's how the existing
    shop form treats it (the default), so a shop with no limit configured
    must not be flagged on every single sale.
    """
    with conn() as c:
        shop = c.execute("SELECT id, name, credit_limit, credit_days, price_tier FROM retail_shops WHERE id=?",
                         (shop_id,)).fetchone()
    if not shop:
        return None
    limit = shop["credit_limit"] or 0
    outstanding = shop_outstanding(shop_id)
    return {
        "shop_id": shop["id"],
        "name": shop["name"],
        "price_tier": shop["price_tier"],
        "limit": limit,
        "outstanding": outstanding,
        "has_limit": limit > 0,
        "available": (limit - outstanding) if limit > 0 else None,
        "over": limit > 0 and outstanding >= limit,
    }


@app.route("/api/shop/<int:shop_id>/credit")
@login_required
def api_shop_credit(shop_id):
    """Live credit position for the counter screen, refreshed on shop select."""
    cs = credit_status(shop_id)
    if not cs:
        abort(404)
    return jsonify(cs)


@app.route("/billing", methods=["GET", "POST"])
@login_required
def billing():
    if request.method == "POST":
        shop_id = int(request.form.get("shop_id") or 0)
        item_ids = request.form.getlist("item_id[]")
        qtys = request.form.getlist("qty[]")
        notes = (request.form.get("notes") or "").strip()
        override = request.form.get("credit_override") == "1"
        pay_now = float(request.form.get("pay_now") or 0)
        pay_method = request.form.get("pay_method") or "cash"

        if not shop_id or not item_ids:
            flash("Pick a shop and at least one item.", "err")
            return redirect(url_for("billing"))

        cs = credit_status(shop_id)
        if not cs:
            flash("Unknown shop.", "err")
            return redirect(url_for("billing"))
        if cs["over"] and not override:
            flash(f"{cs['name']} is already over their credit limit "
                  f"(₹{cs['outstanding']:,.2f} outstanding against a ₹{cs['limit']:,.2f} limit). "
                  f"Tick the override box if you still want to bill this.", "err")
            return redirect(url_for("billing"))

        with conn() as c:
            shop = c.execute("SELECT * FROM retail_shops WHERE id=?", (shop_id,)).fetchone()

            order_no = next_order_no()
            cur = c.execute(
                """INSERT INTO sales_orders (order_no, shop_id, notes, source, created_by, status)
                   VALUES (?,?,?,?,?,?)""",
                (order_no, shop_id, notes, "counter", session.get("ws_user") or "admin", "invoiced"))
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
                if item["scheme"] and "+" in (item["scheme"] or ""):
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
                    (order_id, item["id"], item["name"], item["pack_size"], qty, free,
                     rate, item["gst_rate"], qty * rate))
                # Counter sale = goods handed over now, so stock leaves now.
                # The ordered path defers this to dispatch; here there is no
                # dispatch step to defer to.
                c.execute("UPDATE wholesale_items SET stock=MAX(0, stock-?) WHERE id=?",
                          (qty + free, item["id"]))
                added += 1

            if added == 0:
                c.execute("DELETE FROM sales_orders WHERE id=?", (order_id,))
                flash("No valid lines — add quantities and try again.", "err")
                return redirect(url_for("billing"))

        compute_order_totals(order_id)

        with conn() as c:
            order = c.execute("SELECT * FROM sales_orders WHERE id=?", (order_id,)).fetchone()
            inv_no = next_invoice_no()
            due = (date.today() + timedelta(days=shop["credit_days"] or 30)).isoformat()
            cur = c.execute("""INSERT INTO invoices (invoice_no, order_id, shop_id, due_date, total)
                               VALUES (?,?,?,?,?)""",
                            (inv_no, order_id, shop_id, due, order["total"]))
            invoice_id = cur.lastrowid

            if pay_now > 0:
                paid = min(pay_now, order["total"])
                c.execute("INSERT INTO payments (shop_id, invoice_id, amount, method, notes) VALUES (?,?,?,?,?)",
                          (shop_id, invoice_id, paid, pay_method, "Counter sale"))
                c.execute("UPDATE invoices SET paid=?, status=? WHERE id=?",
                          (paid, "paid" if paid >= order["total"] - 0.01 else "partial", invoice_id))

        audit(session.get("ws_user"), "counter_sale", "invoice", invoice_id,
              f"{inv_no} · {shop['name']}" + (" · CREDIT OVERRIDE" if (cs["over"] and override) else ""))
        flash(f"Billed {inv_no} — ₹{order['total']:,.2f} for {shop['name']}.", "ok")
        return redirect(url_for("invoice_detail", inv_id=invoice_id))

    with conn() as c:
        shops = c.execute("""SELECT id, code, name, price_tier, credit_limit
                             FROM retail_shops WHERE status='active' ORDER BY name""").fetchall()
    return render_template("billing.html", shops=shops)


# ══════════════════════════════════════════════════════════════════════
#  CREDIT CHECK ON THE ORDERED PATH
#
#  order_action() lives in app.py and can't import from here (this module
#  imports FROM app), so the check is bolted on by wrapping the already-
#  registered view — the same technique users.py uses for role_required,
#  and for the same reason. Wrapping rather than editing app.py keeps the
#  credit rule in one file instead of smeared across two.
# ══════════════════════════════════════════════════════════════════════
def _wrap_order_action():
    original = app.view_functions.get("order_action")
    if not original:
        import logging
        logging.warning("[billing] order_action not registered — credit check not applied")
        return

    import functools

    @functools.wraps(original)
    def wrapped(order_id, *a, **k):
        # Only gate the step that actually releases goods. Confirming or
        # invoicing an already-dispatched order shouldn't be blocked —
        # the stock has left the building either way.
        if request.form.get("action") == "dispatch" and request.form.get("credit_override") != "1":
            with conn() as c:
                order = c.execute("SELECT shop_id, total FROM sales_orders WHERE id=?", (order_id,)).fetchone()
            if order:
                cs = credit_status(order["shop_id"])
                if cs and cs["over"]:
                    flash(f"⚠ {cs['name']} owes ₹{cs['outstanding']:,.2f} against a "
                          f"₹{cs['limit']:,.2f} limit. Use 'Dispatch anyway' on the order page "
                          f"if you want to release this.", "err")
                    return redirect(url_for("order_detail", order_id=order_id))
        return original(order_id, *a, **k)

    app.view_functions["order_action"] = wrapped


_wrap_order_action()


# ══════════════════════════════════════════════════════════════════════
#  PARTIAL DISPATCH → BACK-ORDER
#
#  Real distribution rarely ships an order complete. Until now dispatch was
#  all-or-nothing: the whole order went out at the ordered quantities, so a
#  short supply meant either invoicing for goods that never left, or
#  editing the order by hand and losing the record of what the shop still
#  wants.
#
#  Now: enter what's actually going out per line. The order is trimmed to
#  what shipped (so the invoice bills exactly that), and the shortfall
#  becomes a NEW draft order flagged as a back-order against the original.
#  The shop's unmet demand stays visible and orderable instead of quietly
#  disappearing.
#
#  Lines dropped to zero are removed from the dispatched order entirely
#  rather than left as zero-qty noise on the invoice - but they still carry
#  into the back-order, because "we sent none of it" is exactly the case
#  where the shop most needs it remembered.
# ══════════════════════════════════════════════════════════════════════
def _ensure_backorder_column():
    """
    Add sales_orders.backorder_of if this tenant's DB predates it.

    Done lazily per tenant rather than at import: module-level schema runs
    against whatever DB is bound at import time (the default one), which is
    how existing tenants have been missed by migrations before in this
    codebase. A PRAGMA check per dispatch is cheap and self-heals every
    tenant on first use.
    """
    with conn() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(sales_orders)").fetchall()}
        if "backorder_of" not in cols:
            c.execute("ALTER TABLE sales_orders ADD COLUMN backorder_of INTEGER")


@app.route("/orders/<int:order_id>/dispatch", methods=["GET", "POST"])
@login_required
def order_dispatch(order_id):
    _ensure_backorder_column()

    with conn() as c:
        order = c.execute("""SELECT o.*, s.name shop_name, s.code shop_code
                             FROM sales_orders o JOIN retail_shops s ON s.id=o.shop_id
                             WHERE o.id=?""", (order_id,)).fetchone()
        if not order:
            abort(404)
        lines = c.execute("""SELECT l.*, i.stock available
                             FROM sales_order_items l
                             LEFT JOIN wholesale_items i ON i.id=l.item_id
                             WHERE l.order_id=?""", (order_id,)).fetchall()

    if order["status"] != "confirmed":
        flash("Only a confirmed order can be dispatched.", "err")
        return redirect(url_for("order_detail", order_id=order_id))

    if request.method == "GET":
        return render_template("order_dispatch.html", order=order, lines=lines,
                               credit=credit_status(order["shop_id"]))

    # ── POST ──────────────────────────────────────────────────────────
    if not request.form.get("credit_override"):
        cs = credit_status(order["shop_id"])
        if cs and cs["over"]:
            flash(f"⚠ {cs['name']} owes ₹{cs['outstanding']:,.2f} against a ₹{cs['limit']:,.2f} limit. "
                  f"Tick the override to release these goods.", "err")
            return redirect(url_for("order_dispatch", order_id=order_id))

    line_ids = request.form.getlist("line_id[]")
    send_qtys = request.form.getlist("send_qty[]")
    sending = {}
    for lid, q in zip(line_ids, send_qtys):
        try:
            sending[int(lid)] = max(0, int(q or 0))
        except ValueError:
            continue

    if not any(sending.values()):
        flash("Nothing to dispatch — enter at least one quantity.", "err")
        return redirect(url_for("order_dispatch", order_id=order_id))

    now = datetime.now().isoformat(timespec="seconds")
    shortfall = []

    with conn() as c:
        for ln in lines:
            ordered = ln["qty"] or 0
            send = min(sending.get(ln["id"], 0), ordered)
            short = ordered - send

            if short > 0:
                shortfall.append({"item_id": ln["item_id"], "item_name": ln["item_name"],
                                  "pack_size": ln["pack_size"], "qty": short,
                                  "rate": ln["rate"], "gst_rate": ln["gst_rate"]})

            if send == 0:
                c.execute("DELETE FROM sales_order_items WHERE id=?", (ln["id"],))
                continue

            # Recompute the free-goods scheme against what actually ships -
            # a 10+1 on an order of 20 that only half-ships is 1 free, not 2.
            free = 0
            if ln["item_id"]:
                item = c.execute("SELECT scheme FROM wholesale_items WHERE id=?", (ln["item_id"],)).fetchone()
                if item and item["scheme"] and "+" in (item["scheme"] or ""):
                    try:
                        b, bs = item["scheme"].split("+")
                        b, bs = int(b), int(bs)
                        if b > 0:
                            free = (send // b) * bs
                    except Exception:
                        pass
            c.execute("UPDATE sales_order_items SET qty=?, free_qty=?, amount=? WHERE id=?",
                      (send, free, send * (ln["rate"] or 0), ln["id"]))
            if ln["item_id"]:
                c.execute("UPDATE wholesale_items SET stock=MAX(0, stock-?) WHERE id=?",
                          (send + free, ln["item_id"]))

        c.execute("UPDATE sales_orders SET status='dispatched', dispatched_at=? WHERE id=?",
                  (now, order_id))

    compute_order_totals(order_id)

    back_no = None
    if shortfall:
        with conn() as c:
            back_no = next_order_no()
            cur = c.execute(
                """INSERT INTO sales_orders (order_no, shop_id, notes, source, created_by, status, backorder_of)
                   VALUES (?,?,?,?,?,?,?)""",
                (back_no, order["shop_id"],
                 f"Back-order — short supply on {order['order_no']}",
                 "backorder", session.get("ws_user") or "admin", "draft", order_id))
            back_id = cur.lastrowid
            for s in shortfall:
                c.execute("""INSERT INTO sales_order_items
                    (order_id, item_id, item_name, pack_size, qty, free_qty, rate, gst_rate, amount)
                    VALUES (?,?,?,?,?,0,?,?,?)""",
                    (back_id, s["item_id"], s["item_name"], s["pack_size"], s["qty"],
                     s["rate"], s["gst_rate"], s["qty"] * (s["rate"] or 0)))
        compute_order_totals(back_id)

    audit(session.get("ws_user"), "dispatch", "order", order_id,
          f"{order['order_no']}" + (f" · back-order {back_no}" if back_no else " · complete"))

    try:
        import whatsapp
        whatsapp.notify_order_confirmed(order_id)
    except Exception:
        pass

    if back_no:
        flash(f"Dispatched {order['order_no']} short — back-order {back_no} created for the balance.", "ok")
    else:
        flash(f"Dispatched {order['order_no']} in full.", "ok")
    return redirect(url_for("order_detail", order_id=order_id))
