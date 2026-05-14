"""
Report endpoints — customer-facing and management/operational.

Each report has:
  - An API route that returns structured JSON  (``/api/reports/…``)
  - A page route that serves a printable HTML template (``/reports/…``)

All endpoints are read-only — no writes to the database.
"""

from datetime import datetime, date as date_type, timedelta

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
    BillingVoucher,
)
from ..models.core import (
    Customer, Doctor, Item, GstSlab, Manufacturer, HsnCode,
    ProductCategory,
)
from ..models.inventory import StockBatch, ExpiryAlert
from ..models.finance import Expense
from ..models.lookups import BillType, ReturnReason, PaymentMode


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


# ===========================================================================
# MANAGEMENT & OPERATIONAL REPORTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 5. Daily Sales Register & Day Book
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/daily-sales", methods=["GET"])
def api_daily_sales():
    """Daily summary: all bills, payment breakdowns, expenses, cash tally."""
    target_date = _parse_date(request.args.get("date"))
    if not target_date:
        target_date = datetime.now().date()

    bills = SalesBill.query.filter(
        SalesBill.bill_date == target_date,
        SalesBill.is_cancelled.is_(False),
    ).order_by(SalesBill.bill_time).all()

    # Payment mode breakdown from BillingVoucher
    vouchers = BillingVoucher.query.filter(
        BillingVoucher.voucher_date == target_date,
    ).all()

    payment_summary = {}
    for v in vouchers:
        mode = (v.payment_type or "Other").capitalize()
        payment_summary[mode] = payment_summary.get(mode, 0) + float(v.amount)

    # Expenses for the day
    expenses = Expense.query.filter(
        Expense.expense_date == target_date,
        Expense.is_active.is_(True),
    ).all()

    total_expenses = sum(float(e.amount) for e in expenses)

    bill_rows = []
    total_gross = 0
    total_discount = 0
    total_tax = 0
    total_net = 0
    total_items_sold = 0

    for b in bills:
        customer = Customer.query.get(b.customer_id) if b.customer_id else None
        items_count = SalesBillItem.query.filter_by(bill_id=b.bill_id).count()
        total_items_sold += items_count

        gross = float(b.gross_amount)
        disc = float(b.discount_amount)
        tax = float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount)
        net = float(b.net_amount)
        total_gross += gross
        total_discount += disc
        total_tax += tax
        total_net += net

        bill_rows.append({
            "bill_id": f"B-{b.bill_id}",
            "bill_no": b.bill_no,
            "time": b.bill_time.strftime("%H:%M"),
            "customer_name": customer.customer_name if customer else "Walk-in",
            "items_count": items_count,
            "gross": round(gross, 2),
            "discount": round(disc, 2),
            "tax": round(tax, 2),
            "net": round(net, 2),
        })

    expense_rows = []
    for e in expenses:
        expense_rows.append({
            "id": e.expense_id,
            "category": e.expense_category,
            "description": e.description or "",
            "voucher_no": e.voucher_no or "",
            "amount": float(e.amount),
            "gst_amount": float(e.gst_amount),
        })

    return jsonify({
        "report_date": target_date.strftime("%d/%m/%Y"),
        "report_date_iso": target_date.isoformat(),
        "total_bills": len(bill_rows),
        "total_items_sold": total_items_sold,
        "total_gross": round(total_gross, 2),
        "total_discount": round(total_discount, 2),
        "total_tax": round(total_tax, 2),
        "total_net": round(total_net, 2),
        "payment_breakdown": payment_summary,
        "total_expenses": round(total_expenses, 2),
        "net_cash_position": round(total_net - total_expenses, 2),
        "bills": bill_rows,
        "expenses": expense_rows,
    })


@reports_bp.route("/reports/daily-sales", methods=["GET"])
@login_required
def page_daily_sales():
    return render_template(
        "reports/daily_sales.html",
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 6. Short Expiry & Expired Stock Report
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/expiry-stock", methods=["GET"])
def api_expiry_stock():
    """Return stock batches grouped by expiry status: expired, <=30d, <=60d, <=90d."""
    today = datetime.now().date()
    d30 = today + timedelta(days=30)
    d60 = today + timedelta(days=60)
    d90 = today + timedelta(days=90)

    batches = StockBatch.query.filter(
        StockBatch.current_qty > 0,
        StockBatch.expiry_date <= d90,
    ).order_by(StockBatch.expiry_date).all()

    items = []
    summary = {"expired": 0, "within_30": 0, "within_60": 0, "within_90": 0, "total_at_risk_value": 0}

    for sb in batches:
        item = Item.query.get(sb.item_id)
        mfr = Manufacturer.query.get(sb.manufacturer_id) if sb.manufacturer_id else None
        days_left = (sb.expiry_date - today).days
        risk_value = float(sb.mrp) * sb.current_qty

        if days_left < 0:
            status = "EXPIRED"
            summary["expired"] += 1
        elif days_left <= 30:
            status = "≤30 DAYS"
            summary["within_30"] += 1
        elif days_left <= 60:
            status = "≤60 DAYS"
            summary["within_60"] += 1
        else:
            status = "≤90 DAYS"
            summary["within_90"] += 1

        summary["total_at_risk_value"] += risk_value

        items.append({
            "item_id": sb.item_id,
            "item_name": item.item_name if item else sb.item_id,
            "batch_no": sb.batch_no,
            "manufacturer": mfr.manufacturer_name if mfr else "",
            "expiry_date": sb.expiry_date.strftime("%m/%Y"),
            "days_left": days_left,
            "current_qty": sb.current_qty,
            "mrp": float(sb.mrp),
            "risk_value": round(risk_value, 2),
            "status": status,
        })

    summary["total_at_risk_value"] = round(summary["total_at_risk_value"], 2)
    summary["total_items"] = len(items)

    return jsonify({
        "report_date": today.strftime("%d/%m/%Y"),
        "summary": summary,
        "items": items,
    })


@reports_bp.route("/reports/expiry-stock", methods=["GET"])
@login_required
def page_expiry_stock():
    return render_template(
        "reports/expiry_stock.html",
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 7. Reorder & Low Stock Level Report
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/low-stock", methods=["GET"])
def api_low_stock():
    """Return items where total stock is at or below their reorder level."""
    items = Item.query.filter(Item.is_active.is_(True)).all()

    low_stock_items = []
    for item in items:
        total_qty = db.session.query(
            func.coalesce(func.sum(StockBatch.current_qty), 0)
        ).filter(StockBatch.item_id == item.item_id).scalar()

        if total_qty <= item.reorder_level:
            cat = ProductCategory.query.get(item.category_id) if item.category_id else None
            mfr = Manufacturer.query.get(item.manufacturer_id) if item.manufacturer_id else None
            low_stock_items.append({
                "item_id": item.item_id,
                "item_name": item.item_name,
                "category": cat.category_name if cat else "",
                "manufacturer": mfr.manufacturer_name if mfr else "",
                "current_stock": int(total_qty),
                "reorder_level": item.reorder_level,
                "max_stock": item.max_stock or 0,
                "deficit": max(0, item.reorder_level - int(total_qty)),
                "suggested_order": max(0, (item.max_stock or item.reorder_level * 3) - int(total_qty)),
            })

    low_stock_items.sort(key=lambda x: x["deficit"], reverse=True)

    return jsonify({
        "report_date": datetime.now().date().strftime("%d/%m/%Y"),
        "total_items_checked": len(items),
        "total_below_reorder": len(low_stock_items),
        "items": low_stock_items,
    })


@reports_bp.route("/reports/low-stock", methods=["GET"])
@login_required
def page_low_stock():
    return render_template(
        "reports/low_stock.html",
        current_user=_current_page_user(),
    )


# ---------------------------------------------------------------------------
# 8. Inventory Valuation & Stock Status
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/inventory-valuation", methods=["GET"])
def api_inventory_valuation():
    """Return total inventory valuation at MRP and Purchase Rate."""
    batches = StockBatch.query.filter(StockBatch.current_qty > 0).all()

    total_mrp_value = 0
    total_purchase_value = 0
    category_totals = {}
    items_list = []

    for sb in batches:
        item = Item.query.get(sb.item_id)
        mfr = Manufacturer.query.get(sb.manufacturer_id) if sb.manufacturer_id else None
        cat = None
        cat_name = "Uncategorized"
        if item and item.category_id:
            cat = ProductCategory.query.get(item.category_id)
            cat_name = cat.category_name if cat else "Uncategorized"

        mrp_val = float(sb.mrp) * sb.current_qty
        pur_val = float(sb.purchase_rate) * sb.current_qty
        total_mrp_value += mrp_val
        total_purchase_value += pur_val

        if cat_name not in category_totals:
            category_totals[cat_name] = {"mrp_value": 0, "purchase_value": 0, "items_count": 0, "total_qty": 0}
        category_totals[cat_name]["mrp_value"] += mrp_val
        category_totals[cat_name]["purchase_value"] += pur_val
        category_totals[cat_name]["items_count"] += 1
        category_totals[cat_name]["total_qty"] += sb.current_qty

        items_list.append({
            "item_id": sb.item_id,
            "item_name": item.item_name if item else sb.item_id,
            "batch_no": sb.batch_no,
            "manufacturer": mfr.manufacturer_name if mfr else "",
            "category": cat_name,
            "expiry": sb.expiry_date.strftime("%m/%Y") if sb.expiry_date else "",
            "current_qty": sb.current_qty,
            "mrp": float(sb.mrp),
            "purchase_rate": float(sb.purchase_rate),
            "mrp_value": round(mrp_val, 2),
            "purchase_value": round(pur_val, 2),
            "margin_pct": round(((float(sb.mrp) - float(sb.purchase_rate)) / float(sb.mrp)) * 100, 1) if float(sb.mrp) > 0 else 0,
        })

    category_summary = []
    for cname, totals in sorted(category_totals.items()):
        category_summary.append({
            "category": cname,
            "items_count": totals["items_count"],
            "total_qty": totals["total_qty"],
            "mrp_value": round(totals["mrp_value"], 2),
            "purchase_value": round(totals["purchase_value"], 2),
            "margin": round(totals["mrp_value"] - totals["purchase_value"], 2),
        })

    return jsonify({
        "report_date": datetime.now().date().strftime("%d/%m/%Y"),
        "total_batches": len(items_list),
        "total_mrp_value": round(total_mrp_value, 2),
        "total_purchase_value": round(total_purchase_value, 2),
        "total_margin": round(total_mrp_value - total_purchase_value, 2),
        "margin_pct": round(((total_mrp_value - total_purchase_value) / total_mrp_value) * 100, 1) if total_mrp_value > 0 else 0,
        "category_summary": category_summary,
        "items": items_list,
    })


@reports_bp.route("/reports/inventory-valuation", methods=["GET"])
@login_required
def page_inventory_valuation():
    return render_template(
        "reports/inventory_valuation.html",
        current_user=_current_page_user(),
    )
