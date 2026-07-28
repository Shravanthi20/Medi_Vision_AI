"""
WhatsApp Business API wiring (Twilio)
======================================

INBOUND (/api/whatsapp/inbound): a Twilio webhook. A shop texts something
like "SEL001: Dolo 650 x5, Crocin x2" and gets a WhatsApp reply confirming
what was understood — via the EXACT SAME alias/exact/fuzzy matcher the
wanted-list file uploads use (wanted.py's match_line). That means a shop's
WhatsApp order benefits from every alias already taught through a file
upload, and a name confirmed here is remembered for their next file upload
too — one shared vocabulary, not two.

OUTBOUND (send_whatsapp): order confirmations, payment reminders. Safely
no-ops with a log line until real Twilio credentials exist; nothing here
needs a redeploy to activate once they're added to .env.

──────────────────────────────────────────────────────────────────────
SETUP NEEDED FROM THE DISTRIBUTOR — none of this exists yet. This is a
checklist for turning it on, not something already configured:

  1. A Twilio account (twilio.com) — the free trial is enough to test.
  2. WhatsApp enabled on a Twilio number:
       - Sandbox (free, instant, for testing): Twilio Console -> Messaging
         -> Try it out -> Send a WhatsApp message. Each shop must first
         send the shown join code to the sandbox number ONCE before the
         sandbox will talk to them.
       - Production (paid, ~1-2 week Meta approval): Twilio's WhatsApp
         Business Profile process — needs a real registered business.
  3. Three values from the Twilio console, added to /var/www/wholesaler/.env:
       TWILIO_ACCOUNT_SID=AC...
       TWILIO_AUTH_TOKEN=...
       TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   (sandbox number shown
                                                       in the console, or
                                                       your own once live)
     then: systemctl restart wholesaler.service
  4. Point the Twilio webhook at this URL, method POST — note YOUR
     COMPANY CODE is part of the URL (this is how the app knows whose
     shops/catalog/aliases to use for a request that carries no login
     session, since Twilio never sends one):
       https://wholesale.selvammedicals.in/api/whatsapp/inbound/<your-company-code>
     e.g. https://wholesale.selvammedicals.in/api/whatsapp/inbound/rathna
     (Console -> WhatsApp Sandbox Settings -> "When a message comes in")

If two companies both used Twilio, each configures their OWN Twilio
number's webhook to their OWN /inbound/<slug> URL — there's one WhatsApp
number per company, same as there'd be one phone line per shop.

That's the whole activation — no code changes needed once those exist.
Until they do, /customize shows "WhatsApp: not configured" and inbound
messages simply won't arrive (there's nothing pointed at this URL yet).
"""
from __future__ import annotations

import os
import hmac
import base64
import hashlib
import logging
from xml.sax.saxutils import escape

from flask import request, Response

from app import app, conn, rate_for_shop, next_order_no, compute_order_totals, audit
import wanted as W  # reuse the exact same alias/exact/fuzzy matcher

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")

_client_cache = None


def whatsapp_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)


def _client():
    global _client_cache
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    if _client_cache is None:
        try:
            from twilio.rest import Client
            _client_cache = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        except ImportError:
            logging.warning("[whatsapp] 'twilio' package not installed — pip install twilio")
            return None
    return _client_cache


def send_whatsapp(to: str, body: str):
    """
    to: any phone (E.164 preferred, e.g. '+919843012345'). 'whatsapp:' prefix
    added automatically. Returns (ok: bool, detail: str) — detail is the
    Twilio message SID on success, or a human-readable reason on failure.
    Never raises: a WhatsApp send failure should never break the caller's
    request (e.g. confirming an order must succeed even if the ping fails).
    """
    if not to:
        return False, "no phone number on file for this shop"
    c = _client()
    if not c:
        logging.info("[whatsapp] (not configured) would send to %s: %s", to, body[:80])
        return False, "WhatsApp not configured yet — see whatsapp.py docstring for setup steps"
    to_addr = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
    try:
        msg = c.messages.create(from_=TWILIO_WHATSAPP_FROM, to=to_addr, body=body)
        return True, msg.sid
    except Exception as e:
        logging.warning("[whatsapp] send to %s failed: %s", to, e)
        return False, str(e)


def _verify_twilio_signature(req) -> bool:
    """
    Twilio signs every webhook: HMAC-SHA1 over (full URL + sorted POST
    params concatenated as key+value), base64'd, keyed by the auth token,
    sent as X-Twilio-Signature. Without this, anyone who finds the webhook
    URL could POST fake orders. Only skipped (with a log line) when no
    auth token is configured yet — i.e. before setup step 3 above exists,
    there's nothing to sign against anyway.
    """
    if not TWILIO_AUTH_TOKEN:
        logging.info("[whatsapp] signature check skipped — TWILIO_AUTH_TOKEN not set")
        return True
    sig = req.headers.get("X-Twilio-Signature", "")
    if not sig:
        return False
    data = "".join(f"{k}{v}" for k, v in sorted(req.form.items()))
    expected = base64.b64encode(
        hmac.new(TWILIO_AUTH_TOKEN.encode(), (req.url + data).encode(), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(sig, expected)


def notify_order_confirmed(order_id: int):
    """
    Best-effort WhatsApp ping when an order moves draft -> confirmed. Called
    from app.py's order_action via a lazy import (see there for why).
    Never raises — a notification failure must not block confirming an
    order in front of a distributor's staff.
    """
    try:
        with conn() as c:
            row = c.execute("""SELECT o.order_no, o.total, s.name shop_name, s.phone, s.whatsapp
                               FROM sales_orders o JOIN retail_shops s ON s.id=o.shop_id
                               WHERE o.id=?""", (order_id,)).fetchone()
        if not row:
            return
        to = row["whatsapp"] or row["phone"]
        if not to:
            return
        body = (f"Hi {row['shop_name']}, your order {row['order_no']} "
                f"(₹{row['total']:.2f}) is confirmed and will be dispatched shortly. "
                f"— MediVision Wholesale")
        send_whatsapp(to, body)
    except Exception as e:
        logging.warning("[whatsapp] order-confirmed notify failed for order %s: %s", order_id, e)


def notify_payment_reminder(shop_id: int, amount: float) -> tuple[bool, str]:
    """Used by /ledger's WhatsApp-reminder action once Twilio is configured."""
    try:
        with conn() as c:
            shop = c.execute("SELECT name, phone, whatsapp FROM retail_shops WHERE id=?", (shop_id,)).fetchone()
        if not shop:
            return False, "shop not found"
        to = shop["whatsapp"] or shop["phone"]
        body = (f"Hi {shop['name']}, this is a reminder that ₹{amount:.2f} is outstanding "
                f"on your account. Please arrange payment at your earliest convenience. "
                f"— MediVision Wholesale")
        return send_whatsapp(to, body)
    except Exception as e:
        return False, str(e)


def _phone_suffix(s: str, n: int = 10) -> str:
    """
    Last N digits only. Twilio sends E.164 ('+919843012345'); shops are
    typically saved in whatever format the person entering them used
    ('9843012345', '09843012345', '+91 98430 12345'...). Comparing full
    strings would silently fail to recognise a real shop's own number.
    """
    digits = "".join(ch for ch in (s or "") if ch.isdigit())
    return digits[-n:] if len(digits) >= n else digits


def _twiml(message: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(message)}</Message></Response>'
    return Response(xml, mimetype="text/xml")


@app.route("/api/whatsapp/inbound/<slug>", methods=["POST"])
def whatsapp_inbound(slug):
    # Twilio sends no session cookie - the company has to come from the URL
    # itself (see the setup checklist above), or this would silently read
    # whatever DB core.DB_PATH's fallback happens to point at instead of
    # this company's actual shops/catalog/aliases. enter_tenant() 404s if
    # the slug is wrong/unknown rather than guessing.
    import tenancy
    tenancy.enter_tenant(slug)

    if not _verify_twilio_signature(request):
        return Response("signature check failed", status=403)

    text = (request.form.get("Body") or "").strip()
    from_number = (request.form.get("From") or "").replace("whatsapp:", "").strip()

    if not text:
        return _twiml("Didn't catch an order in that. Send it like:\nSEL001: Dolo 650 x5, Crocin x2")

    shop_code = None
    body = text
    if ":" in text:
        shop_code, body = text.split(":", 1)
        shop_code = shop_code.strip().upper()

    with conn() as c:
        shop = None
        if shop_code:
            shop = c.execute("SELECT * FROM retail_shops WHERE code=? OR phone=? OR whatsapp=?",
                             (shop_code, shop_code, shop_code)).fetchone()
        if not shop and from_number:
            # No recognised "CODE: ..." prefix — try matching by the sender's
            # own WhatsApp number instead, treating the whole text as the
            # order. Compared by last-10-digits: Twilio sends E.164
            # ('+919843012345'), shops are saved in whatever format someone
            # typed ('9843012345', '098430 12345', ...) - exact string
            # equality would silently never match a real shop's own number.
            suffix = _phone_suffix(from_number)
            if suffix:
                shop = c.execute(
                    "SELECT * FROM retail_shops WHERE substr(phone,-10)=? OR substr(whatsapp,-10)=?",
                    (suffix, suffix)).fetchone()
            if shop:
                body = text

        if not shop:
            return _twiml("We couldn't match your shop. Please start your message with your "
                          "shop code, e.g.:\nSEL001: Dolo 650 x5, Crocin x2")

        order_no = next_order_no()
        cur = c.execute(
            "INSERT INTO sales_orders (order_no, shop_id, source, created_by, notes, status) VALUES (?,?,?,?,?,?)",
            (order_no, shop["id"], "whatsapp", shop_code or from_number, text[:400], "draft"))
        order_id = cur.lastrowid

        catalog = W.load_catalog(c)
        index = W.build_catalog_index(catalog)

        matched_lines, unmatched_names = [], []
        for part in body.split(","):
            part = part.strip()
            if not part:
                continue
            qty = 1
            name_part = part
            if "x" in part.lower():
                p1, p2 = part.lower().rsplit("x", 1)
                try:
                    qty = max(1, int(p2.strip()))
                    name_part = p1.strip()
                except ValueError:
                    pass

            item_id, mtype, conf, sugg = W.match_line(c, index, shop["id"], name_part)
            if item_id and mtype in ("alias", "global", "exact"):
                item = c.execute("SELECT * FROM wholesale_items WHERE id=?", (item_id,)).fetchone()
                rate = rate_for_shop(item, shop["price_tier"])
                c.execute("""INSERT INTO sales_order_items
                    (order_id, item_id, item_name, pack_size, qty, rate, gst_rate, amount)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (order_id, item["id"], item["name"], item["pack_size"], qty, rate, item["gst_rate"], qty * rate))
                matched_lines.append(f"{item['name']} x{qty}")
            else:
                # High-confidence fuzzy but not auto-applied over WhatsApp
                # (no click-to-confirm channel here) — logged as demand so
                # it still surfaces for a human, same as an unmatched
                # wanted-list line does.
                unmatched_names.append(name_part)
                W.record_demand(c, [{"norm": W.norm(name_part), "raw": name_part, "qty": qty}], shop["id"])

        if not matched_lines:
            c.execute("DELETE FROM sales_orders WHERE id=?", (order_id,))
            return _twiml("We couldn't recognise any items in that message. "
                          "Our team will call to confirm, or try again with exact item names.")

    compute_order_totals(order_id)
    audit(shop_code or from_number, "whatsapp_order", "order", order_id, order_no)

    reply = f"Got it! Order {order_no} for {shop['name']}:\n" + "\n".join(f"• {l}" for l in matched_lines)
    if unmatched_names:
        reply += "\n\nCouldn't match: " + ", ".join(unmatched_names) + " — we'll follow up on these."
    reply += "\n\nWe'll confirm and dispatch shortly."
    return _twiml(reply)
