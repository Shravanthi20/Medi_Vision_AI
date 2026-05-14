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
    ProductCategory, Supplier,
)
from ..models.inventory import StockBatch, ExpiryAlert
from ..models.finance import Expense, GstTransaction
from ..models.purchase import PurchaseInvoice, PurchaseInvoiceItem, PurchasePayment
from ..models.hr import Salesman, AttendanceLog, SalesmanLedger
from ..models.ai import AiFaceLog, CustomerPurchasePattern, PrescriptionOcrLog, WantedList
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


# ===========================================================================
# FINANCIAL & COMPLIANCE REPORTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 9. GST Output & Input Tax Report
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/gst-tax", methods=["GET"])
def api_gst_tax():
    """GST summary grouped by slab for a date range — output (sales) and input (purchases)."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date().replace(day=1)
    if not end_date:
        end_date = datetime.now().date()

    # --- Output Tax (Sales) ---
    sales_bills = SalesBill.query.filter(
        SalesBill.bill_date.between(start_date, end_date),
        SalesBill.is_cancelled.is_(False),
    ).all()

    output_by_slab = {}
    total_output = {"taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_tax": 0}

    for bill in sales_bills:
        for bi in bill.items:
            slab_pct = float(bi.cgst_pct + bi.sgst_pct + bi.igst_pct)
            key = f"{slab_pct:.0f}%"
            if key not in output_by_slab:
                output_by_slab[key] = {"slab": key, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_tax": 0, "count": 0}
            taxable = float(bi.value) - float(bi.gst_amount)
            output_by_slab[key]["taxable"] += taxable
            output_by_slab[key]["cgst"] += float(bi.cgst_pct) / 100 * taxable if bi.cgst_pct else 0
            output_by_slab[key]["sgst"] += float(bi.sgst_pct) / 100 * taxable if bi.sgst_pct else 0
            output_by_slab[key]["igst"] += float(bi.igst_pct) / 100 * taxable if bi.igst_pct else 0
            output_by_slab[key]["total_tax"] += float(bi.gst_amount)
            output_by_slab[key]["count"] += 1

    for v in output_by_slab.values():
        total_output["taxable"] += v["taxable"]
        total_output["cgst"] += v["cgst"]
        total_output["sgst"] += v["sgst"]
        total_output["igst"] += v["igst"]
        total_output["total_tax"] += v["total_tax"]

    # --- Input Tax (Purchases) ---
    purchases = PurchaseInvoice.query.filter(
        PurchaseInvoice.invoice_date.between(start_date, end_date),
    ).all()

    input_by_slab = {}
    total_input = {"taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_tax": 0}

    for pi in purchases:
        for pii in pi.line_items:
            slab_pct = float(pii.cgst_pct + pii.sgst_pct + pii.igst_pct)
            key = f"{slab_pct:.0f}%"
            if key not in input_by_slab:
                input_by_slab[key] = {"slab": key, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0, "total_tax": 0, "count": 0}
            taxable = float(pii.value) - float(pii.gst_amount)
            input_by_slab[key]["taxable"] += taxable
            input_by_slab[key]["cgst"] += float(pii.cgst_pct) / 100 * taxable if pii.cgst_pct else 0
            input_by_slab[key]["sgst"] += float(pii.sgst_pct) / 100 * taxable if pii.sgst_pct else 0
            input_by_slab[key]["igst"] += float(pii.igst_pct) / 100 * taxable if pii.igst_pct else 0
            input_by_slab[key]["total_tax"] += float(pii.gst_amount)
            input_by_slab[key]["count"] += 1

    for v in input_by_slab.values():
        total_input["taxable"] += v["taxable"]
        total_input["cgst"] += v["cgst"]
        total_input["sgst"] += v["sgst"]
        total_input["igst"] += v["igst"]
        total_input["total_tax"] += v["total_tax"]

    # Round everything
    def _round_dict(d):
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in d.items()}

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "output_tax": {
            "by_slab": [_round_dict(v) for v in sorted(output_by_slab.values(), key=lambda x: x["slab"])],
            "totals": _round_dict(total_output),
        },
        "input_tax": {
            "by_slab": [_round_dict(v) for v in sorted(input_by_slab.values(), key=lambda x: x["slab"])],
            "totals": _round_dict(total_input),
        },
        "net_liability": {
            "cgst": round(total_output["cgst"] - total_input["cgst"], 2),
            "sgst": round(total_output["sgst"] - total_input["sgst"], 2),
            "igst": round(total_output["igst"] - total_input["igst"], 2),
            "total": round(total_output["total_tax"] - total_input["total_tax"], 2),
        },
    })


@reports_bp.route("/reports/gst-tax", methods=["GET"])
@login_required
def page_gst_tax():
    return render_template("reports/gst_tax.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 10. Purchase Register (Supplier/Manufacturer Wise)
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/purchase-register", methods=["GET"])
def api_purchase_register():
    """Purchase invoices with date filter and supplier grouping."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))

    query = PurchaseInvoice.query
    if start_date:
        query = query.filter(PurchaseInvoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(PurchaseInvoice.invoice_date <= end_date)

    invoices = query.order_by(PurchaseInvoice.invoice_date.desc()).all()

    rows = []
    supplier_totals = {}
    grand_total = 0

    for pi in invoices:
        supplier = Supplier.query.get(pi.supplier_id)
        sup_name = supplier.supplier_name if supplier else "Unknown"
        items_count = pi.line_items.count()
        net = float(pi.net_amount)
        grand_total += net

        if sup_name not in supplier_totals:
            supplier_totals[sup_name] = {"invoices": 0, "total": 0}
        supplier_totals[sup_name]["invoices"] += 1
        supplier_totals[sup_name]["total"] += net

        rows.append({
            "purchase_id": pi.purchase_id,
            "ref_no": pi.ref_no,
            "invoice_no": pi.invoice_no or "",
            "invoice_date": pi.invoice_date.strftime("%d/%m/%Y") if pi.invoice_date else "",
            "supplier": sup_name,
            "items_count": items_count,
            "gross": float(pi.gross_amount),
            "discount": float(pi.discount_amount),
            "tax": float(pi.cgst_amount) + float(pi.sgst_amount) + float(pi.igst_amount),
            "net": round(net, 2),
        })

    supplier_summary = [{"supplier": k, **v, "total": round(v["total"], 2)} for k, v in sorted(supplier_totals.items())]

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y") if start_date else "",
        "end_date": end_date.strftime("%d/%m/%Y") if end_date else "",
        "total_invoices": len(rows),
        "grand_total": round(grand_total, 2),
        "supplier_summary": supplier_summary,
        "invoices": rows,
    })


@reports_bp.route("/reports/purchase-register", methods=["GET"])
@login_required
def page_purchase_register():
    return render_template("reports/purchase_register.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 11. Supplier Ledger & Outstanding Payables
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/supplier-ledger", methods=["GET"])
def api_supplier_ledger():
    """All suppliers with purchase totals, payments, and outstanding balance."""
    suppliers = Supplier.query.filter(Supplier.is_active.is_(True)).all()

    ledger = []
    total_payable = 0
    total_paid = 0

    for sup in suppliers:
        purchase_total = db.session.query(
            func.coalesce(func.sum(PurchaseInvoice.net_amount), 0)
        ).filter(PurchaseInvoice.supplier_id == sup.supplier_id).scalar()

        payment_total = db.session.query(
            func.coalesce(func.sum(PurchasePayment.amount), 0)
        ).filter(PurchasePayment.supplier_id == sup.supplier_id).scalar()

        purchase_total = float(purchase_total)
        payment_total = float(payment_total)
        outstanding = purchase_total - payment_total
        total_payable += purchase_total
        total_paid += payment_total

        if purchase_total > 0 or payment_total > 0:
            ledger.append({
                "supplier_id": sup.supplier_id,
                "supplier_name": sup.supplier_name,
                "gstin": sup.gstin or "",
                "phone": sup.phone or "",
                "total_purchases": round(purchase_total, 2),
                "total_payments": round(payment_total, 2),
                "outstanding": round(outstanding, 2),
            })

    ledger.sort(key=lambda x: x["outstanding"], reverse=True)

    return jsonify({
        "report_date": datetime.now().date().strftime("%d/%m/%Y"),
        "total_suppliers": len(ledger),
        "total_payable": round(total_payable, 2),
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(total_payable - total_paid, 2),
        "suppliers": ledger,
    })


@reports_bp.route("/reports/supplier-ledger", methods=["GET"])
@login_required
def page_supplier_ledger():
    return render_template("reports/supplier_ledger.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 12. Gross Margin / Profit & Loss Summary
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/profit-loss", methods=["GET"])
def api_profit_loss():
    """P&L summary for a date range: sales revenue vs cost of goods vs expenses."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date().replace(day=1)
    if not end_date:
        end_date = datetime.now().date()

    # Revenue from sales
    bills = SalesBill.query.filter(
        SalesBill.bill_date.between(start_date, end_date),
        SalesBill.is_cancelled.is_(False),
    ).all()

    total_revenue = sum(float(b.net_amount) for b in bills)
    total_discount = sum(float(b.discount_amount) for b in bills)
    total_tax_collected = sum(float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount) for b in bills)

    # Cost of goods sold (from SalesBillItem.purchase_rate_at_sale)
    cogs = 0
    for b in bills:
        for bi in b.items:
            cogs += float(bi.purchase_rate_at_sale) * int(bi.qty_sold)

    gross_profit = total_revenue - cogs

    # Operating expenses
    expenses = Expense.query.filter(
        Expense.expense_date.between(start_date, end_date),
        Expense.is_active.is_(True),
    ).all()

    total_expenses = sum(float(e.amount) for e in expenses)

    # Expense breakdown by category
    expense_breakdown = {}
    for e in expenses:
        cat = e.expense_category
        expense_breakdown[cat] = expense_breakdown.get(cat, 0) + float(e.amount)

    expense_categories = [{"category": k, "amount": round(v, 2)} for k, v in sorted(expense_breakdown.items())]

    net_profit = gross_profit - total_expenses
    gross_margin_pct = round((gross_profit / total_revenue) * 100, 1) if total_revenue > 0 else 0
    net_margin_pct = round((net_profit / total_revenue) * 100, 1) if total_revenue > 0 else 0

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "total_bills": len(bills),
        "revenue": {
            "net_sales": round(total_revenue, 2),
            "total_discount": round(total_discount, 2),
            "tax_collected": round(total_tax_collected, 2),
        },
        "cost_of_goods_sold": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": gross_margin_pct,
        "operating_expenses": round(total_expenses, 2),
        "expense_categories": expense_categories,
        "net_profit": round(net_profit, 2),
        "net_margin_pct": net_margin_pct,
    })


@reports_bp.route("/reports/profit-loss", methods=["GET"])
@login_required
def page_profit_loss():
    return render_template("reports/profit_loss.html", current_user=_current_page_user())


# ===========================================================================
# HR & STAFF REPORTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 13. Salesman Performance & Commission Report
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/salesman-performance", methods=["GET"])
def api_salesman_performance():
    """Revenue per salesman with bill counts and commission data."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date().replace(day=1)
    if not end_date:
        end_date = datetime.now().date()

    salesmen = Salesman.query.filter(Salesman.is_active.is_(True)).all()

    rows = []
    grand_revenue = 0
    grand_bills = 0

    for sm in salesmen:
        bills = SalesBill.query.filter(
            SalesBill.salesman_id == sm.salesman_id,
            SalesBill.bill_date.between(start_date, end_date),
            SalesBill.is_cancelled.is_(False),
        ).all()

        bill_count = len(bills)
        revenue = sum(float(b.net_amount) for b in bills)
        items_sold = 0
        cogs = 0
        for b in bills:
            for bi in b.items:
                items_sold += int(bi.qty_sold)
                cogs += float(bi.purchase_rate_at_sale) * int(bi.qty_sold)

        gross_profit = revenue - cogs

        # Commission from ledger entries in period
        commission = db.session.query(
            func.coalesce(func.sum(SalesmanLedger.ai_commission_earned), 0)
        ).filter(
            SalesmanLedger.salesman_id == sm.salesman_id,
            SalesmanLedger.period_from >= start_date,
            SalesmanLedger.period_to <= end_date,
        ).scalar()

        grand_revenue += revenue
        grand_bills += bill_count

        rows.append({
            "salesman_id": sm.salesman_id,
            "salesman_code": sm.salesman_code,
            "salesman_name": sm.salesman_name,
            "phone": sm.phone or "",
            "bill_count": bill_count,
            "items_sold": items_sold,
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "margin_pct": round((gross_profit / revenue) * 100, 1) if revenue > 0 else 0,
            "commission": round(float(commission), 2),
            "avg_bill_value": round(revenue / bill_count, 2) if bill_count > 0 else 0,
        })

    rows.sort(key=lambda x: x["revenue"], reverse=True)

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "total_salesmen": len(rows),
        "grand_revenue": round(grand_revenue, 2),
        "grand_bills": grand_bills,
        "salesmen": rows,
    })


@reports_bp.route("/reports/salesman-performance", methods=["GET"])
@login_required
def page_salesman_performance():
    return render_template("reports/salesman_performance.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 14. Staff Attendance & Salary Register
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/attendance-salary", methods=["GET"])
def api_attendance_salary():
    """Attendance summary + salary ledger entries for all staff in a period."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date().replace(day=1)
    if not end_date:
        end_date = datetime.now().date()

    salesmen = Salesman.query.filter(Salesman.is_active.is_(True)).all()

    staff_data = []
    total_payable = 0
    total_paid = 0

    for sm in salesmen:
        # Attendance: count unique days with CAME
        attendance_logs = AttendanceLog.query.filter(
            AttendanceLog.salesman_id == sm.salesman_id,
            AttendanceLog.log_date.between(start_date, end_date),
        ).order_by(AttendanceLog.log_date, AttendanceLog.log_time).all()

        days_present = len(set(log.log_date for log in attendance_logs if log.status == 'CAME'))
        total_days = (end_date - start_date).days + 1

        # Calculate total hours from CAME/WENT pairs
        total_hours = 0
        day_logs = {}
        for log in attendance_logs:
            if log.log_date not in day_logs:
                day_logs[log.log_date] = []
            day_logs[log.log_date].append(log)

        for day_date, logs in day_logs.items():
            came_time = None
            for log in sorted(logs, key=lambda l: l.log_time):
                if log.status == 'CAME' and came_time is None:
                    came_time = log.log_time
                elif log.status == 'WENT' and came_time is not None:
                    diff = (log.log_time - came_time).total_seconds() / 3600
                    total_hours += diff
                    came_time = None

        # Salary ledger entries for this period
        ledger_entries = SalesmanLedger.query.filter(
            SalesmanLedger.salesman_id == sm.salesman_id,
            SalesmanLedger.period_from >= start_date,
            SalesmanLedger.period_to <= end_date,
        ).order_by(SalesmanLedger.period_from).all()

        salary_rows = []
        staff_payable = 0
        staff_paid = 0
        for entry in ledger_entries:
            salary_rows.append({
                "period": entry.period_label,
                "from": entry.period_from.strftime("%d/%m/%Y"),
                "to": entry.period_to.strftime("%d/%m/%Y"),
                "hours": float(entry.total_working_hrs),
                "rate_per_hr": float(entry.salary_per_hr),
                "gross": float(entry.gross_salary),
                "advance": float(entry.advance_taken),
                "commission": float(entry.ai_commission_earned),
                "net_payable": float(entry.net_payable),
                "is_paid": entry.is_paid,
                "paid_date": entry.paid_date.strftime("%d/%m/%Y") if entry.paid_date else "",
            })
            staff_payable += float(entry.net_payable)
            if entry.is_paid:
                staff_paid += float(entry.net_payable)

        total_payable += staff_payable
        total_paid += staff_paid

        staff_data.append({
            "salesman_id": sm.salesman_id,
            "salesman_code": sm.salesman_code,
            "salesman_name": sm.salesman_name,
            "phone": sm.phone or "",
            "salary_per_hr": float(sm.salary_per_hr),
            "days_present": days_present,
            "total_days": total_days,
            "attendance_pct": round((days_present / total_days) * 100, 1) if total_days > 0 else 0,
            "total_hours": round(total_hours, 1),
            "salary_entries": salary_rows,
            "total_payable": round(staff_payable, 2),
            "total_paid": round(staff_paid, 2),
            "outstanding": round(staff_payable - staff_paid, 2),
        })

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "total_staff": len(staff_data),
        "total_payable": round(total_payable, 2),
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(total_payable - total_paid, 2),
        "staff": staff_data,
    })


@reports_bp.route("/reports/attendance-salary", methods=["GET"])
@login_required
def page_attendance_salary():
    return render_template("reports/attendance_salary.html", current_user=_current_page_user())


# ===========================================================================
# AI & ANALYTICS REPORTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 15. Customer Retention & Purchase Patterns (CRM)
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/customer-retention", methods=["GET"])
def api_customer_retention():
    """Identifies patients based on purchase patterns and expected return dates."""
    # Filter out inactive customers
    customers = Customer.query.filter(Customer.is_active.is_(True)).all()
    
    rows = []
    total_chronic = 0
    overdue_count = 0
    
    today = datetime.now().date()
    
    for cust in customers:
        patterns = CustomerPurchasePattern.query.filter(
            CustomerPurchasePattern.customer_id == cust.customer_id
        ).all()
        
        if not patterns:
            continue
            
        total_chronic += 1
        
        # Determine the most critical pattern for the customer
        latest_expected = None
        is_overdue = False
        items_tracked = []
        
        for p in patterns:
            item = Item.query.get(p.item_id)
            item_name = item.item_name if item else "Unknown Item"
            items_tracked.append(f"{item_name} (Avg: {int(p.avg_quantity)})")
            
            if p.next_expected_date:
                if latest_expected is None or p.next_expected_date < latest_expected:
                    latest_expected = p.next_expected_date
                    
        if latest_expected and latest_expected < today:
            is_overdue = True
            overdue_count += 1
            
        rows.append({
            "customer_id": cust.customer_id,
            "customer_name": cust.customer_name,
            "phone": cust.phone or "",
            "patterns_count": len(patterns),
            "items_tracked": items_tracked,
            "last_purchase_date": max((p.last_purchased_date for p in patterns if p.last_purchased_date), default=None),
            "next_expected_date": latest_expected.strftime("%d/%m/%Y") if latest_expected else "N/A",
            "is_overdue": is_overdue,
            "days_overdue": (today - latest_expected).days if is_overdue and latest_expected else 0,
        })
        
    rows.sort(key=lambda x: (not x["is_overdue"], -x["days_overdue"]))

    return jsonify({
        "report_date": today.strftime("%d/%m/%Y"),
        "total_customers": len(customers),
        "total_chronic_patients": total_chronic,
        "overdue_count": overdue_count,
        "retention_data": [{
            **r,
            "last_purchase_date": r["last_purchase_date"].strftime("%d/%m/%Y") if r["last_purchase_date"] else "N/A",
        } for r in rows],
    })

@reports_bp.route("/reports/customer-retention", methods=["GET"])
@login_required
def page_customer_retention():
    return render_template("reports/customer_retention.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 16. Facial Recognition Footfall Analytics
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/face-footfall", methods=["GET"])
def api_face_footfall():
    """Analyzes walk-in frequency using camera data, tracking peak shop hours."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date()
    if not end_date:
        end_date = datetime.now().date()
        
    # Get all logs in date range
    logs = AiFaceLog.query.filter(
        db.func.date(AiFaceLog.detected_at).between(start_date, end_date)
    ).all()
    
    total_walkins = len(logs)
    unique_customers = len(set(log.customer_id for log in logs if log.customer_id))
    fraud_alerts = sum(1 for log in logs if log.is_fraud_alert)
    
    # Peak hours calculation
    hourly_distribution = {i: 0 for i in range(24)}
    for log in logs:
        hourly_distribution[log.detected_at.hour] += 1
        
    peak_hours = [{"hour": f"{h:02d}:00", "count": c} for h, c in hourly_distribution.items() if c > 0]
    peak_hours.sort(key=lambda x: x["count"], reverse=True)
    
    # Recent wanted/fraud logs
    recent_alerts = []
    for log in [l for l in logs if l.is_fraud_alert][:10]:
        recent_alerts.append({
            "detected_at": log.detected_at.strftime("%d/%m/%Y %H:%M:%S"),
            "camera_id": log.camera_id,
            "confidence": float(log.confidence_score) if log.confidence_score else 0,
            "action": log.action_triggered or "Flagged",
        })

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "total_walkins": total_walkins,
        "unique_customers": unique_customers,
        "fraud_alerts": fraud_alerts,
        "peak_hours": peak_hours[:5], # Top 5 peak hours
        "hourly_distribution": [{"hour": h, "count": c} for h, c in hourly_distribution.items()],
        "recent_alerts": recent_alerts,
    })

@reports_bp.route("/reports/face-footfall", methods=["GET"])
@login_required
def page_face_footfall():
    return render_template("reports/face_footfall.html", current_user=_current_page_user())


# ---------------------------------------------------------------------------
# 17. Prescription OCR Analytics
# ---------------------------------------------------------------------------

@reports_bp.route("/api/reports/ocr-analytics", methods=["GET"])
def api_ocr_analytics():
    """Report showing the success/failure rate of the AI OCR feature."""
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    if not start_date:
        start_date = datetime.now().date().replace(day=1)
    if not end_date:
        end_date = datetime.now().date()
        
    logs = PrescriptionOcrLog.query.filter(
        db.func.date(PrescriptionOcrLog.processed_at).between(start_date, end_date)
    ).all()
    
    total_processed = len(logs)
    human_verification_required = sum(1 for log in logs if log.requires_human_verification)
    auto_processed = total_processed - human_verification_required
    
    avg_confidence = 0
    if total_processed > 0:
        confidences = [float(log.confidence_score) for log in logs if log.confidence_score]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            
    recent_logs = []
    for log in sorted(logs, key=lambda l: l.processed_at, reverse=True)[:50]:
        recent_logs.append({
            "log_id": log.ocr_log_id,
            "processed_at": log.processed_at.strftime("%d/%m/%Y %H:%M:%S"),
            "confidence": float(log.confidence_score) if log.confidence_score else 0,
            "requires_human": log.requires_human_verification,
            "is_verified": log.verified_at is not None,
            "medicines_parsed": len(log.parsed_medicines) if log.parsed_medicines else 0,
        })

    return jsonify({
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "total_processed": total_processed,
        "auto_processed": auto_processed,
        "human_verification_required": human_verification_required,
        "automation_rate_pct": round((auto_processed / total_processed * 100) if total_processed > 0 else 0, 1),
        "avg_confidence_pct": round(avg_confidence, 1),
        "recent_logs": recent_logs,
    })

@reports_bp.route("/reports/ocr-analytics", methods=["GET"])
@login_required
def page_ocr_analytics():
    return render_template("reports/ocr_analytics.html", current_user=_current_page_user())
