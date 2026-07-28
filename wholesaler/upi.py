"""
UPI Pay Now — deep link + QR, no payment-gateway account needed
=================================================================

Generates a `upi://pay?...` link (opens the shop's own UPI app, prefilled
with the distributor's VPA, the amount, and the invoice number as the
note) and a QR code image of that same link. A shop on a phone taps the
link directly; a shop on a laptop, or a delivery visit in person, scans
the QR with any UPI app.

WHY NOT A GATEWAY (Razorpay/PayU/etc.): this needs zero setup beyond the
distributor's own UPI ID, which they already have. No merchant account,
no KYC, no per-transaction fee. The trade-off, and it's a real one: there
is no webhook telling us the money arrived. "Record payment" on the
invoice stays a manual step, same as it is today for cash/bank/cheque —
this just makes initiating the payment itself effortless for the shop.
A gateway integration later would close that last gap (auto-reconcile);
this is deliberately the 80% that needed no new account to ship today.

Requires `company.upi` set in /customize (a VPA like `name@okhdfcbank`).
Without it, the pay button/QR simply don't render — nothing breaks.
"""
from __future__ import annotations

import io
from urllib.parse import quote

from flask import Response, abort, session

from app import app, conn
from erp import setting_get

try:
    import qrcode
    HAVE_QRCODE = True
except ImportError:
    HAVE_QRCODE = False


def upi_configured() -> bool:
    return bool(setting_get("company.upi", "").strip()) and HAVE_QRCODE


def build_upi_link(amount: float, note: str) -> str:
    vpa = setting_get("company.upi", "").strip()
    payee = setting_get("company.name", "MediVision Wholesale").strip()
    # UPI deep link params must be percent-encoded; amounts always 2dp.
    return (f"upi://pay?pa={quote(vpa)}&pn={quote(payee)}&am={amount:.2f}"
            f"&cu=INR&tn={quote(note[:50])}")


def _invoice_for(inv_id: int):
    """Fetch an invoice, or None. Doesn't enforce access — caller does."""
    with conn() as c:
        return c.execute("""SELECT i.*, s.name shop_name FROM invoices i
                            JOIN retail_shops s ON s.id=i.shop_id WHERE i.id=?""", (inv_id,)).fetchone()


@app.route("/api/upi-qr/<int:inv_id>.png")
def upi_qr_png(inv_id):
    """
    PNG QR for one invoice's balance due. Access control matters here —
    without it, anyone who guesses an invoice id could see another shop's
    outstanding amount (not device-critical, but still their business
    data). Allowed for: an admin logged into this tenant, OR the shop
    session that actually owns this invoice.
    """
    if not HAVE_QRCODE:
        abort(404)
    inv = _invoice_for(inv_id)
    if not inv:
        abort(404)

    is_admin = bool(session.get("ws_user") and session.get("tenant"))
    is_owning_shop = session.get("shop_id") == inv["shop_id"]
    if not (is_admin or is_owning_shop):
        abort(403)

    balance = round((inv["total"] or 0) - (inv["paid"] or 0), 2)
    link = build_upi_link(balance, f"{inv['invoice_no']}")

    img = qrcode.make(link, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png",
                    headers={"Cache-Control": "no-store"})
