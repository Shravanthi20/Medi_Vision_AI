"""
Customer-facing report endpoints.

Each report has:
  - An API route that returns structured JSON  (``/api/reports/…``)
  - A page route that serves a printable HTML template (``/reports/…``)

All endpoints are read-only — no writes to the database.
"""

from datetime import datetime, date as date_type

from flask import Blueprint, jsonify, request, render_template, session
from sqlalchemy import func

from ..extensions import db
from .auth import login_required
from ..models.sales import (
    SalesBill,
    SalesBillItem,
    SalesReturn,
    SalesReturnItem,
    ReceiptPayment,
    PrescriptionRegister,
)
from ..models.core import Customer, Doctor, Item, GstSlab, Manufacturer, HsnCode
from ..models.inventory import StockBatch
from ..models.lookups import BillType, ReturnReason


reports_bp = Blueprint("reports", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_error(message, code=400, details=None):
    return jsonify({"error": message, "details": details}), code


def _parse_date(value, *, default=None):
    """Parse a date string in ISO or DD/MM/YYYY format."""
    raw = str(value or "").strip()
    if not raw:
        return default
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return default


def _current_page_user():
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "name": session.get("name"),
        "role": session.get("role"),
    }


# ---------------------------------------------------------------------------
# 1. Sales Invoice
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/invoice/<bill_id>", methods=["GET"])
def api_invoice(bill_id):
    """Return full invoice data for a single bill."""
    real_id = str(bill_id).replace("B-", "").strip()
    bill = SalesBill.query.get(real_id)
    if not bill:
        return _json_error("Bill not found", 404, {"id": bill_id})

    customer = Customer.query.get(bill.customer_id) if bill.customer_id else None
    doctor = Doctor.query.get(bill.doctor_id) if bill.doctor_id else None
    bt = BillType.query.get(bill.bill_type_id) if bill.bill_type_id else None

    line_items = []
    for idx, bi in enumerate(bill.items, start=1):
        item = Item.query.get(bi.item_id)
        batch = StockBatch.query.get(bi.stock_batch_id) if bi.stock_batch_id else None
        hsn = None
        if item and item.hsn_id:
            hsn = HsnCode.query.get(item.hsn_id)

        line_items.append({
            "sno": idx,
            "item_id": bi.item_id,
            "item_name": item.item_name if item else bi.item_id,
            "batch_no": batch.batch_no if batch else "",
            "expiry": batch.expiry_date.strftime("%m/%Y") if batch and batch.expiry_date else "",
            "hsn_code": hsn.hsn_code if hsn else "",
            "qty": int(bi.qty_sold),
            "free_qty": int(bi.free_qty or 0),
            "mrp": float(bi.mrp_at_sale),
            "rate": float(bi.selling_price_at_sale),
            "discount_pct": float(bi.discount_pct or 0),
            "net_rate": float(bi.net_rate),
            "cgst_pct": float(bi.cgst_pct),
            "sgst_pct": float(bi.sgst_pct),
            "igst_pct": float(bi.igst_pct),
            "gst_amount": float(bi.gst_amount),
            "value": float(bi.value),
        })

    return jsonify({
        "bill_id": f"B-{bill.bill_id}",
        "bill_no": bill.bill_no,
        "bill_date": bill.bill_date.strftime("%d/%m/%Y"),
        "bill_time": bill.bill_time.strftime("%H:%M"),
        "bill_type": bt.bill_type_name if bt else "Retail",
        "is_cancelled": bill.is_cancelled,

        "customer_name": customer.customer_name if customer else "Walk-in",
        "customer_phone": customer.phone if customer else "",
        "customer_address": customer.address if customer else "",
        "customer_gstin": customer.gstin if customer else "",

        "doctor_name": doctor.doctor_name if doctor else "Self",

        "items": line_items,

        "gross_amount": float(bill.gross_amount),
        "discount_pct": float(bill.discount_pct),
        "discount_amount": float(bill.discount_amount),
        "taxable_amount": float(bill.taxable_amount),
        "cgst_amount": float(bill.cgst_amount),
        "sgst_amount": float(bill.sgst_amount),
        "igst_amount": float(bill.igst_amount),
        "round_off": float(bill.round_off),
        "net_amount": float(bill.net_amount),

        "remarks": bill.remarks or "",
        "prescription": bill.prescription_base64 or "",
    })


@reports_bp.route("/reports/invoice/<bill_id>", methods=["GET"])
@login_required
def page_invoice(bill_id):
    return render_template(
        "reports/invoice.html",
        bill_id=bill_id,
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 2. Credit Note / Sales Return
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/credit-note/<int:return_id>", methods=["GET"])
def api_credit_note(return_id):
    """Return credit note data for a sales return."""
    sr = SalesReturn.query.get(return_id)
    if not sr:
        return _json_error("Sales return not found", 404, {"id": return_id})

    original_bill = SalesBill.query.get(sr.original_bill_id) if sr.original_bill_id else None
    customer = Customer.query.get(sr.customer_id) if sr.customer_id else None
    reason = ReturnReason.query.get(sr.reason_id) if sr.reason_id else None

    items = []
    for idx, ri in enumerate(sr.return_items, start=1):
        item = Item.query.get(ri.item_id)
        batch = StockBatch.query.get(ri.stock_batch_id) if ri.stock_batch_id else None
        items.append({
            "sno": idx,
            "item_id": ri.item_id,
            "item_name": item.item_name if item else ri.item_id,
            "batch_no": batch.batch_no if batch else "",
            "expiry": batch.expiry_date.strftime("%m/%Y") if batch and batch.expiry_date else "",
            "qty_returned": int(ri.qty_returned),
            "return_rate": float(ri.return_rate),
            "gst_amount": float(ri.gst_amount),
            "return_value": float(ri.return_value),
        })

    return jsonify({
        "return_id": sr.sales_return_id,
        "return_no": sr.return_no,
        "return_date": sr.return_date.strftime("%d/%m/%Y"),

        "original_bill_id": f"B-{sr.original_bill_id}" if sr.original_bill_id else "",
        "original_bill_date": original_bill.bill_date.strftime("%d/%m/%Y") if original_bill else "",

        "customer_name": customer.customer_name if customer else "Walk-in",
        "customer_phone": customer.phone if customer else "",
        "customer_address": customer.address if customer else "",

        "reason": reason.reason_name if reason else "",
        "remarks": sr.remarks or "",

        "items": items,

        "total_return_amount": float(sr.total_return_amount),
        "cgst_amount": float(sr.cgst_amount),
        "sgst_amount": float(sr.sgst_amount),
        "igst_amount": float(sr.igst_amount),
        "net_return_amount": float(sr.net_return_amount),
    })


@reports_bp.route("/reports/credit-note/<int:return_id>", methods=["GET"])
@login_required
def page_credit_note(return_id):
    return render_template(
        "reports/credit_note.html",
        return_id=return_id,
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 3. Customer Account Statement
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/customer-statement/<int:customer_id>", methods=["GET"])
def api_customer_statement(customer_id):
    """Return a ledger statement with opening/closing balance for a customer."""
    customer = Customer.query.get(customer_id)
    if not customer:
        return _json_error("Customer not found", 404, {"id": customer_id})

    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    # --- Family scope ---
    root_id = int(customer.family_head_id or customer.customer_id)
    family_rows = Customer.query.filter(
        (Customer.customer_id == root_id) | (Customer.family_head_id == root_id)
    ).all()
    family_ids = sorted({r.customer_id for r in family_rows})
    if customer.customer_id not in family_ids:
        family_ids.append(customer.customer_id)

    # --- Collect all events ---
    bills = SalesBill.query.filter(
        SalesBill.customer_id.in_(family_ids),
        SalesBill.is_cancelled.is_(False),
    ).all()

    receipts = ReceiptPayment.query.filter(
        ReceiptPayment.customer_id.in_(family_ids),
    ).all()

    member_lookup = {
        r.customer_id: r.customer_name
        for r in Customer.query.filter(Customer.customer_id.in_(family_ids)).all()
    }

    events = []
    for bill in bills:
        dt = datetime.combine(bill.bill_date, bill.bill_time)
        events.append({
            "date": dt,
            "kind": "Sale",
            "ref_id": f"B-{bill.bill_id}",
            "description": f"Bill #{bill.bill_no} — {member_lookup.get(bill.customer_id, 'Customer')}",
            "debit": float(bill.net_amount),
            "credit": 0.0,
        })
    for receipt in receipts:
        dt = datetime.combine(receipt.receipt_date, datetime.min.time())
        events.append({
            "date": dt,
            "kind": "Payment",
            "ref_id": f"PAY-{receipt.receipt_id}",
            "description": f"{receipt.remarks or 'Payment Received'} — {member_lookup.get(receipt.customer_id, 'Customer')}",
            "debit": 0.0,
            "credit": float(receipt.amount),
        })

    events.sort(key=lambda e: e["date"])

    # --- Split into before-range (opening balance) and in-range entries ---
    opening_balance = 0.0
    ledger_entries = []

    for ev in events:
        ev_date = ev["date"].date() if isinstance(ev["date"], datetime) else ev["date"]
        if start_date and ev_date < start_date:
            opening_balance += ev["debit"] - ev["credit"]
            continue
        if end_date and ev_date > end_date:
            continue
        ledger_entries.append(ev)

    running = opening_balance
    out_entries = []
    for idx, ev in enumerate(ledger_entries, start=1):
        running += ev["debit"] - ev["credit"]
        out_entries.append({
            "id": idx,
            "date": ev["date"].strftime("%d/%m/%Y"),
            "ref_type": ev["kind"],
            "ref_id": ev["ref_id"],
            "description": ev["description"],
            "debit": ev["debit"],
            "credit": ev["credit"],
            "balance": round(running, 2),
        })

    return jsonify({
        "customer_id": customer.customer_id,
        "customer_name": customer.customer_name,
        "customer_phone": customer.phone or "",
        "customer_address": customer.address or "",
        "family_member_count": len(family_ids),
        "start_date": start_date.strftime("%d/%m/%Y") if start_date else "",
        "end_date": end_date.strftime("%d/%m/%Y") if end_date else "",
        "opening_balance": round(opening_balance, 2),
        "closing_balance": round(running, 2),
        "entries": out_entries,
    })


@reports_bp.route("/reports/customer-statement/<int:customer_id>", methods=["GET"])
@login_required
def page_customer_statement(customer_id):
    return render_template(
        "reports/customer_statement.html",
        customer_id=customer_id,
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 4. Prescription History
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/prescription-history/<int:customer_id>", methods=["GET"])
def api_prescription_history(customer_id):
    """Return full prescription register entries for a customer."""
    customer = Customer.query.get(customer_id)
    if not customer:
        return _json_error("Customer not found", 404, {"id": customer_id})

    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    query = PrescriptionRegister.query.filter_by(customer_id=customer_id)
    if start_date:
        query = query.filter(PrescriptionRegister.rx_date >= start_date)
    if end_date:
        query = query.filter(PrescriptionRegister.rx_date <= end_date)

    rows = query.order_by(PrescriptionRegister.rx_date.desc()).all()

    entries = []
    for idx, rx in enumerate(rows, start=1):
        item = Item.query.get(rx.item_id)
        doctor = Doctor.query.get(rx.doctor_id) if rx.doctor_id else None
        entries.append({
            "sno": idx,
            "rx_date": rx.rx_date.strftime("%d/%m/%Y"),
            "bill_id": f"B-{rx.bill_id}",
            "item_name": item.item_name if item else rx.item_id,
            "batch_no": rx.batch_no,
            "manufacturer": rx.manufacturer_name,
            "qty": int(rx.qty),
            "expiry_date": rx.expiry_date.strftime("%m/%Y") if rx.expiry_date else "",
            "doctor_name": doctor.doctor_name if doctor else "",
            "dispensed_by": rx.dispenser_sign or "",
        })

    return jsonify({
        "customer_id": customer.customer_id,
        "customer_name": customer.customer_name,
        "customer_phone": customer.phone or "",
        "start_date": start_date.strftime("%d/%m/%Y") if start_date else "",
        "end_date": end_date.strftime("%d/%m/%Y") if end_date else "",
        "total_prescriptions": len(entries),
        "entries": entries,
    })


@reports_bp.route("/reports/prescription-history/<int:customer_id>", methods=["GET"])
@login_required
def page_prescription_history(customer_id):
    return render_template(
        "reports/prescription_history.html",
        customer_id=customer_id,
        current_user=_current_page_user(),
    )
