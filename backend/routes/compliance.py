"""Stage 6 — Compliance routes:
  - GST Returns API  (/api/gst/*)
  - Expiry Return-to-Supplier (/api/expiry-returns/*)
  - Drug License Renewal Tracker (/api/licenses/*)
  - Page routes for each section
"""
from __future__ import annotations

from datetime import date as date_type, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request, session
from sqlalchemy import func, extract, distinct

from ..extensions import db
from .auth import login_required
from ..models.core import (
    Customer, FinancialYear, HsnCode, Item, Supplier, UnitOfMeasure,
)
from ..models.inventory import StockBatch
from ..models.sales import SalesBill, SalesBillItem
from ..models.compliance import ExpiryReturn, ExpiryReturnItem, LicenseDocument
from ..models.finance import Expense

compliance_bp = Blueprint("compliance", __name__)


# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────

def _json_error(msg: str, code: int = 400, details=None):
    payload = {"status": "error", "message": msg}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), code


def _parse_date(value, default=None):
    raw = str(value or "").strip()
    if not raw:
        return default
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return default


def _current_user():
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "name": session.get("name"),
        "role": session.get("role"),
    }


def _default_fy_user():
    from ..models.core import FinancialYear, User, Role
    import hashlib, uuid as _uuid

    fy = FinancialYear.query.filter_by(is_active=True).first()
    if not fy:
        today = date_type.today()
        fy = FinancialYear(
            fy_label=f"{today.year}-{str(today.year + 1)[-2:]}",
            start_date=date_type(today.year, 4, 1),
            end_date=date_type(today.year + 1, 3, 31),
            is_active=True,
        )
        db.session.add(fy)
        db.session.flush()

    user = User.query.first()
    if not user:
        from ..models.core import Role
        role = Role.query.first()
        if not role:
            role = Role(role_name="Admin")
            db.session.add(role)
            db.session.flush()
        user = User(
            user_id=_uuid.uuid4(),
            username="admin",
            password_hash=hashlib.sha256(b"admin").hexdigest(),
            role_id=role.role_id,
            is_super_admin=True,
        )
        db.session.add(user)
        db.session.flush()

    db.session.commit()
    return fy.financial_year_id, user.user_id


# ═══════════════════════════════════════════════════════════════
# GST RETURNS MODULE
# ═══════════════════════════════════════════════════════════════

@compliance_bp.route("/gst")
@login_required
def page_gst():
    return render_template("gst.html", current_user=_current_user())


@compliance_bp.route("/api/gst/months", methods=["GET"])
def api_gst_months():
    """Return distinct YYYY-MM months that have sales data."""
    rows = (
        db.session.query(
            extract("year", SalesBill.bill_date).label("yr"),
            extract("month", SalesBill.bill_date).label("mo"),
        )
        .filter(SalesBill.is_cancelled.is_(False))
        .group_by("yr", "mo")
        .order_by("yr", "mo")
        .all()
    )
    months = [f"{int(r.yr)}-{int(r.mo):02d}" for r in rows]
    return jsonify(months)


def _bills_for_month(month: str | None):
    """Return SalesBill query filtered to a YYYY-MM or all time."""
    q = SalesBill.query.filter(SalesBill.is_cancelled.is_(False))
    if month:
        try:
            yr, mo = int(month[:4]), int(month[5:7])
            start = date_type(yr, mo, 1)
            # last day of month
            if mo == 12:
                end = date_type(yr + 1, 1, 1) - timedelta(days=1)
            else:
                end = date_type(yr, mo + 1, 1) - timedelta(days=1)
            q = q.filter(SalesBill.bill_date.between(start, end))
        except (ValueError, IndexError):
            pass
    return q


@compliance_bp.route("/api/gst/summary", methods=["GET"])
def api_gst_summary():
    """GST summary: totals, B2C/B2B split, payment modes, monthly trend."""
    month = request.args.get("month", "").strip()
    bills = _bills_for_month(month).all()

    gross_sales = sum(float(b.gross_amount) for b in bills)
    total_discount = sum(float(b.discount_amount) for b in bills)
    taxable_value = sum(float(b.taxable_amount) for b in bills)
    cgst = sum(float(b.cgst_amount) for b in bills)
    sgst = sum(float(b.sgst_amount) for b in bills)
    igst = sum(float(b.igst_amount) for b in bills)
    total_gst = cgst + sgst + igst
    grand_total = sum(float(b.net_amount) for b in bills)

    # B2C vs B2B — wholesale bills have a customer with GSTIN or bill_type != retail
    b2c = {"bills": 0, "taxable": 0.0, "gst": 0.0}
    b2b = {"bills": 0, "taxable": 0.0, "gst": 0.0}
    payment_modes: dict[str, float] = {}

    for b in bills:
        customer = Customer.query.get(b.customer_id) if b.customer_id else None
        has_gstin = bool(customer and customer.gstin)
        bucket = b2b if has_gstin else b2c
        bucket["bills"] += 1
        bucket["taxable"] += float(b.taxable_amount)
        bucket["gst"] += float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount)

        mode = (b.payment_mode or "cash").lower()
        payment_modes[mode] = payment_modes.get(mode, 0.0) + float(b.net_amount)

    # Monthly trend (last 12 months regardless of filter)
    trend_rows = (
        db.session.query(
            extract("year", SalesBill.bill_date).label("yr"),
            extract("month", SalesBill.bill_date).label("mo"),
            func.sum(SalesBill.net_amount).label("sales"),
            func.sum(SalesBill.cgst_amount + SalesBill.sgst_amount + SalesBill.igst_amount).label("gst"),
        )
        .filter(SalesBill.is_cancelled.is_(False))
        .filter(SalesBill.bill_date >= date_type.today() - timedelta(days=365))
        .group_by("yr", "mo")
        .order_by("yr", "mo")
        .all()
    )
    monthly_trend = [
        {
            "month": f"{int(r.yr)}-{int(r.mo):02d}",
            "sales": float(r.sales or 0),
            "gst": float(r.gst or 0),
        }
        for r in trend_rows
    ]

    return jsonify({
        "total_bills": len(bills),
        "gross_sales": round(gross_sales, 2),
        "total_discount": round(total_discount, 2),
        "taxable_value": round(taxable_value, 2),
        "cgst": round(cgst, 2),
        "sgst": round(sgst, 2),
        "igst": round(igst, 2),
        "total_gst": round(total_gst, 2),
        "grand_total": round(grand_total, 2),
        "b2c": {k: round(v, 2) if isinstance(v, float) else v for k, v in b2c.items()},
        "b2b": {k: round(v, 2) if isinstance(v, float) else v for k, v in b2b.items()},
        "payment_modes": {k: round(v, 2) for k, v in payment_modes.items()},
        "monthly_trend": monthly_trend,
    })


@compliance_bp.route("/api/gst/gstr1", methods=["GET"])
def api_gst_gstr1():
    """GSTR-1 data: B2CS (rate-wise) and B2CL (bill-wise ≥2.5L)."""
    month = request.args.get("month", "").strip()
    bills = _bills_for_month(month).all()

    B2CL_THRESHOLD = 250000.0

    b2cs_by_rate: dict[float, dict] = {}
    b2cl: list[dict] = []

    for b in bills:
        customer = Customer.query.get(b.customer_id) if b.customer_id else None
        has_gstin = bool(customer and customer.gstin)
        net = float(b.net_amount)

        if has_gstin or net >= B2CL_THRESHOLD:
            # B2CL: bill-wise detail
            gst = float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount)
            taxable = float(b.taxable_amount)
            rate = round(gst / taxable * 100, 0) if taxable > 0 else 0.0
            b2cl.append({
                "bill_no": b.bill_no,
                "date": b.bill_date.strftime("%d/%m/%Y"),
                "customer": customer.customer_name if customer else "Walk-in",
                "phone": customer.phone if customer else "",
                "gstin": customer.gstin if customer else "",
                "taxable": round(taxable, 2),
                "rate": rate,
                "cgst": round(float(b.cgst_amount), 2),
                "sgst": round(float(b.sgst_amount), 2),
                "igst": round(float(b.igst_amount), 2),
                "total": round(net, 2),
            })
        else:
            # B2CS: aggregate by rate
            gst = float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount)
            taxable = float(b.taxable_amount)
            rate = round(gst / taxable * 100, 0) if taxable > 0 else 0.0
            if rate not in b2cs_by_rate:
                b2cs_by_rate[rate] = {"rate": rate, "taxable": 0.0, "cgst": 0.0, "sgst": 0.0}
            b2cs_by_rate[rate]["taxable"] += taxable
            b2cs_by_rate[rate]["cgst"] += float(b.cgst_amount)
            b2cs_by_rate[rate]["sgst"] += float(b.sgst_amount)

    b2cs = []
    for rate, d in sorted(b2cs_by_rate.items()):
        b2cs.append({
            "rate": rate,
            "taxable": round(d["taxable"], 2),
            "cgst": round(d["cgst"], 2),
            "sgst": round(d["sgst"], 2),
        })

    return jsonify({"b2cs": b2cs, "b2cl": b2cl})


@compliance_bp.route("/api/gst/bills", methods=["GET"])
def api_gst_bills():
    """Bill-wise GST ledger for the selected month."""
    month = request.args.get("month", "").strip()
    limit = min(int(request.args.get("limit", 500) or 500), 2000)

    bills = _bills_for_month(month).order_by(SalesBill.bill_date.desc(), SalesBill.bill_id.desc()).limit(limit).all()

    rows = []
    for b in bills:
        customer = Customer.query.get(b.customer_id) if b.customer_id else None
        gst = float(b.cgst_amount) + float(b.sgst_amount) + float(b.igst_amount)
        taxable = float(b.taxable_amount)
        rate = round(gst / taxable * 100, 0) if taxable > 0 else 0.0
        has_gstin = bool(customer and customer.gstin)
        rows.append({
            "bill_id": b.bill_id,
            "bill_no": b.bill_no,
            "date": b.bill_date.strftime("%d/%m/%Y"),
            "customer": customer.customer_name if customer else "Walk-in",
            "phone": customer.phone if customer else "",
            "bill_type": "wholesale" if has_gstin else "retail",
            "payment": (b.payment_mode or "cash").capitalize(),
            "gross": round(float(b.gross_amount), 2),
            "discount": round(float(b.discount_amount), 2),
            "taxable": round(taxable, 2),
            "rate": rate,
            "cgst": round(float(b.cgst_amount), 2),
            "sgst": round(float(b.sgst_amount), 2),
            "igst": round(float(b.igst_amount), 2),
            "total": round(float(b.net_amount), 2),
        })

    return jsonify({"count": len(rows), "data": rows})


@compliance_bp.route("/api/gst/hsn-summary", methods=["GET"])
def api_gst_hsn_summary():
    """HSN-wise summary for GSTR-1 Table 12."""
    month = request.args.get("month", "").strip()
    bill_query = _bills_for_month(month)
    bill_ids = [b.bill_id for b in bill_query.with_entities(SalesBill.bill_id).all()]

    if not bill_ids:
        return jsonify([])

    items = (
        db.session.query(SalesBillItem)
        .filter(SalesBillItem.bill_id.in_(bill_ids))
        .all()
    )

    hsn_map: dict[int, dict] = {}
    for bi in items:
        item = Item.query.get(bi.item_id)
        if not item or not item.hsn_id:
            continue
        hsn = HsnCode.query.get(item.hsn_id)
        if not hsn:
            continue
        uom = UnitOfMeasure.query.get(item.uom_id) if item.uom_id else None
        hid = item.hsn_id
        if hid not in hsn_map:
            hsn_map[hid] = {
                "hsn_code": hsn.hsn_code,
                "description": hsn.description or "Pharmaceutical Preparations",
                "uom": uom.uom_code if uom else "NOS",
                "total_qty": 0,
                "taxable": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "igst": 0.0,
                "rate": 0.0,
            }
        entry = hsn_map[hid]
        entry["total_qty"] += int(bi.qty_sold)
        tax = float(bi.gst_amount)
        taxable = float(bi.value) - tax
        entry["taxable"] += taxable
        entry["cgst"] += float(bi.cgst_pct) / 100 * taxable
        entry["sgst"] += float(bi.sgst_pct) / 100 * taxable
        entry["igst"] += float(bi.igst_pct) / 100 * taxable
        entry["rate"] = float(bi.cgst_pct + bi.sgst_pct + bi.igst_pct)

    result = []
    for d in hsn_map.values():
        total_gst = d["cgst"] + d["sgst"] + d["igst"]
        result.append({
            **d,
            "taxable": round(d["taxable"], 2),
            "cgst": round(d["cgst"], 2),
            "sgst": round(d["sgst"], 2),
            "igst": round(d["igst"], 2),
            "total_gst": round(total_gst, 2),
        })

    return jsonify(sorted(result, key=lambda x: x["hsn_code"]))


# ═══════════════════════════════════════════════════════════════
# EXPIRY RETURN-TO-SUPPLIER MODULE
# ═══════════════════════════════════════════════════════════════

@compliance_bp.route("/expiry-returns")
@login_required
def page_expiry_returns():
    return render_template("expiry_returns.html", current_user=_current_user())


@compliance_bp.route("/api/expiry-returns/near-expiry-stock", methods=["GET"])
def api_near_expiry_for_return():
    """Batches expiring within 90 days with stock > 0 — eligible for supplier return."""
    days = int(request.args.get("days", 90))
    today = date_type.today()
    cutoff = today + timedelta(days=days)

    batches = (
        StockBatch.query
        .filter(StockBatch.current_qty > 0)
        .filter(StockBatch.expiry_date <= cutoff)
        .filter(StockBatch.expiry_date >= today)
        .order_by(StockBatch.expiry_date)
        .all()
    )

    rows = []
    for sb in batches:
        item = Item.query.get(sb.item_id)
        supplier = Supplier.query.get(sb.manufacturer_id) if sb.manufacturer_id else None
        days_left = (sb.expiry_date - today).days
        rows.append({
            "stock_batch_id": sb.stock_batch_id,
            "item_id": sb.item_id,
            "item_name": item.item_name if item else sb.item_id,
            "batch_no": sb.batch_no,
            "expiry_date": sb.expiry_date.strftime("%m/%Y"),
            "expiry_date_iso": sb.expiry_date.isoformat(),
            "days_left": days_left,
            "current_qty": sb.current_qty,
            "mrp": float(sb.mrp),
            "purchase_rate": float(sb.purchase_rate),
            "risk_value": round(float(sb.purchase_rate) * sb.current_qty, 2),
        })

    return jsonify(rows)


@compliance_bp.route("/api/expiry-returns/suppliers", methods=["GET"])
def api_expiry_return_suppliers():
    """All active suppliers for the return form dropdown."""
    suppliers = Supplier.query.filter(Supplier.is_active.is_(True)).order_by(Supplier.supplier_name).all()
    return jsonify([
        {"supplier_id": s.supplier_id, "supplier_name": s.supplier_name, "phone": s.phone or ""}
        for s in suppliers
    ])


@compliance_bp.route("/api/expiry-returns", methods=["GET"])
def api_list_expiry_returns():
    """List all expiry return requests."""
    status_filter = request.args.get("status", "").strip()
    q = ExpiryReturn.query.order_by(ExpiryReturn.return_date.desc(), ExpiryReturn.expiry_return_id.desc())
    if status_filter:
        q = q.filter(ExpiryReturn.status == status_filter.upper())

    returns = q.all()
    rows = []
    for r in returns:
        supplier = Supplier.query.get(r.supplier_id)
        rows.append({
            "expiry_return_id": r.expiry_return_id,
            "return_no": r.return_no,
            "return_date": r.return_date.strftime("%d/%m/%Y"),
            "supplier_id": r.supplier_id,
            "supplier_name": supplier.supplier_name if supplier else "—",
            "status": r.status,
            "total_qty": r.total_qty,
            "total_value": float(r.total_value),
            "credit_note_no": r.credit_note_no or "",
            "credit_note_amount": float(r.credit_note_amount or 0),
            "remarks": r.remarks or "",
            "created_at": r.created_at.strftime("%d/%m/%Y"),
        })
    return jsonify(rows)


@compliance_bp.route("/api/expiry-returns", methods=["POST"])
def api_create_expiry_return():
    """Raise a new expiry return request."""
    data = request.get_json(silent=True) or {}
    supplier_id = data.get("supplier_id")
    items_data = data.get("items", [])

    if not supplier_id:
        return _json_error("supplier_id is required", 400)
    if not items_data:
        return _json_error("At least one item is required", 400)

    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        return _json_error("Supplier not found", 404)

    try:
        fy_id, user_id = _default_fy_user()

        # Generate return number
        count = ExpiryReturn.query.count() + 1
        return_no = f"EXR-{date_type.today().strftime('%Y%m')}-{count:04d}"

        er = ExpiryReturn(
            return_no=return_no,
            return_date=_parse_date(data.get("return_date"), default=date_type.today()),
            supplier_id=int(supplier_id),
            financial_year_id=fy_id,
            status="DRAFT",
            remarks=str(data.get("remarks", "")).strip(),
            user_id=user_id,
        )
        db.session.add(er)
        db.session.flush()

        total_qty = 0
        total_value = 0.0

        for it in items_data:
            sb_id = it.get("stock_batch_id")
            qty = int(it.get("qty_returned", 0))
            if qty <= 0 or not sb_id:
                continue

            sb = StockBatch.query.get(sb_id)
            if not sb:
                continue

            if qty > sb.current_qty:
                return _json_error(
                    f"Return qty ({qty}) exceeds available stock ({sb.current_qty}) for batch {sb.batch_no}",
                    400,
                )

            ret_val = float(sb.purchase_rate) * qty
            eri = ExpiryReturnItem(
                expiry_return_id=er.expiry_return_id,
                stock_batch_id=sb_id,
                item_id=sb.item_id,
                batch_no=sb.batch_no,
                expiry_date=sb.expiry_date,
                qty_returned=qty,
                purchase_rate=float(sb.purchase_rate),
                mrp=float(sb.mrp),
                return_value=ret_val,
            )
            db.session.add(eri)
            total_qty += qty
            total_value += ret_val

        er.total_qty = total_qty
        er.total_value = round(total_value, 2)
        db.session.commit()

        return jsonify({"status": "success", "expiry_return_id": er.expiry_return_id, "return_no": er.return_no})

    except Exception as exc:
        db.session.rollback()
        return _json_error("Failed to create expiry return", 500, str(exc))


@compliance_bp.route("/api/expiry-returns/<int:return_id>", methods=["GET"])
def api_get_expiry_return(return_id: int):
    """Detail of a single expiry return."""
    er = ExpiryReturn.query.get(return_id)
    if not er:
        return _json_error("Expiry return not found", 404)

    supplier = Supplier.query.get(er.supplier_id)
    line_items = []
    for eri in er.items:
        item = Item.query.get(eri.item_id)
        line_items.append({
            "expiry_return_item_id": eri.expiry_return_item_id,
            "item_id": eri.item_id,
            "item_name": item.item_name if item else eri.item_id,
            "batch_no": eri.batch_no,
            "expiry_date": eri.expiry_date.strftime("%m/%Y"),
            "qty_returned": eri.qty_returned,
            "purchase_rate": float(eri.purchase_rate),
            "mrp": float(eri.mrp),
            "return_value": float(eri.return_value),
        })

    return jsonify({
        "expiry_return_id": er.expiry_return_id,
        "return_no": er.return_no,
        "return_date": er.return_date.strftime("%d/%m/%Y"),
        "supplier_id": er.supplier_id,
        "supplier_name": supplier.supplier_name if supplier else "—",
        "status": er.status,
        "total_qty": er.total_qty,
        "total_value": float(er.total_value),
        "credit_note_no": er.credit_note_no or "",
        "credit_note_date": er.credit_note_date.strftime("%d/%m/%Y") if er.credit_note_date else "",
        "credit_note_amount": float(er.credit_note_amount or 0),
        "remarks": er.remarks or "",
        "items": line_items,
    })


@compliance_bp.route("/api/expiry-returns/<int:return_id>/status", methods=["PUT"])
def api_update_expiry_return_status(return_id: int):
    """Advance status: DRAFT → DISPATCHED → CREDIT_NOTE_RECEIVED → CLOSED."""
    er = ExpiryReturn.query.get(return_id)
    if not er:
        return _json_error("Expiry return not found", 404)

    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip().upper()
    valid = {"DRAFT", "DISPATCHED", "CREDIT_NOTE_RECEIVED", "CLOSED"}
    if new_status not in valid:
        return _json_error(f"Invalid status. Must be one of: {', '.join(sorted(valid))}", 400)

    try:
        er.status = new_status
        if new_status == "CREDIT_NOTE_RECEIVED":
            er.credit_note_no = str(data.get("credit_note_no", "")).strip() or er.credit_note_no
            cn_date = _parse_date(data.get("credit_note_date"))
            if cn_date:
                er.credit_note_date = cn_date
            cn_amt = data.get("credit_note_amount")
            if cn_amt is not None:
                er.credit_note_amount = float(cn_amt)

        # When dispatching, reduce stock for each item
        if new_status == "DISPATCHED" and er.status != "DISPATCHED":
            for eri in er.items:
                sb = StockBatch.query.get(eri.stock_batch_id)
                if sb:
                    sb.current_qty = max(0, sb.current_qty - eri.qty_returned)

        db.session.commit()
        return jsonify({"status": "success", "new_status": er.status})
    except Exception as exc:
        db.session.rollback()
        return _json_error("Failed to update status", 500, str(exc))


# ═══════════════════════════════════════════════════════════════
# DRUG LICENSE RENEWAL TRACKER
# ═══════════════════════════════════════════════════════════════

@compliance_bp.route("/licenses")
@login_required
def page_licenses():
    return render_template("licenses.html", current_user=_current_user())


@compliance_bp.route("/api/licenses", methods=["GET"])
def api_list_licenses():
    """List all licenses with computed days-to-expiry and alert status."""
    today = date_type.today()
    licenses = LicenseDocument.query.filter(LicenseDocument.is_active.is_(True)).order_by(LicenseDocument.expiry_date).all()

    rows = []
    for lic in licenses:
        days_left = (lic.expiry_date - today).days
        if days_left < 0:
            alert_level = "EXPIRED"
        elif days_left <= 30:
            alert_level = "CRITICAL"
        elif days_left <= 60:
            alert_level = "WARNING"
        elif days_left <= 90:
            alert_level = "ATTENTION"
        else:
            alert_level = "OK"

        rows.append({
            "license_id": lic.license_id,
            "license_type": lic.license_type,
            "license_name": lic.license_name,
            "license_no": lic.license_no,
            "issuing_authority": lic.issuing_authority or "",
            "issued_date": lic.issued_date.strftime("%d/%m/%Y") if lic.issued_date else "",
            "expiry_date": lic.expiry_date.strftime("%d/%m/%Y"),
            "expiry_date_iso": lic.expiry_date.isoformat(),
            "days_left": days_left,
            "alert_level": alert_level,
            "doc_url": lic.doc_url or "",
            "notes": lic.notes or "",
            "renewal_cost": float(lic.renewal_cost or 0),
            "renewal_contact": lic.renewal_contact or "",
        })

    return jsonify(rows)


@compliance_bp.route("/api/licenses/alerts", methods=["GET"])
def api_license_alerts():
    """Return only licenses needing attention (≤90 days or expired)."""
    today = date_type.today()
    cutoff = today + timedelta(days=90)
    licenses = (
        LicenseDocument.query
        .filter(LicenseDocument.is_active.is_(True))
        .filter(LicenseDocument.expiry_date <= cutoff)
        .order_by(LicenseDocument.expiry_date)
        .all()
    )
    alerts = []
    for lic in licenses:
        days_left = (lic.expiry_date - today).days
        alerts.append({
            "license_id": lic.license_id,
            "license_name": lic.license_name,
            "license_type": lic.license_type,
            "expiry_date": lic.expiry_date.strftime("%d/%m/%Y"),
            "days_left": days_left,
            "alert_level": "EXPIRED" if days_left < 0 else ("CRITICAL" if days_left <= 30 else ("WARNING" if days_left <= 60 else "ATTENTION")),
        })
    return jsonify(alerts)


@compliance_bp.route("/api/licenses", methods=["POST"])
def api_create_license():
    """Add a new license document."""
    data = request.get_json(silent=True) or {}
    required = ["license_type", "license_name", "license_no", "expiry_date"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return _json_error("Missing required fields", 400, missing)

    expiry = _parse_date(data.get("expiry_date"))
    if not expiry:
        return _json_error("Invalid expiry_date format (use YYYY-MM-DD)", 400)

    try:
        lic = LicenseDocument(
            license_type=str(data["license_type"]).strip().upper(),
            license_name=str(data["license_name"]).strip(),
            license_no=str(data["license_no"]).strip(),
            issuing_authority=str(data.get("issuing_authority", "")).strip() or None,
            issued_date=_parse_date(data.get("issued_date")),
            expiry_date=expiry,
            doc_url=str(data.get("doc_url", "")).strip() or None,
            notes=str(data.get("notes", "")).strip() or None,
            renewal_cost=float(data["renewal_cost"]) if data.get("renewal_cost") else None,
            renewal_contact=str(data.get("renewal_contact", "")).strip() or None,
        )
        db.session.add(lic)
        db.session.commit()
        return jsonify({"status": "success", "license_id": lic.license_id})
    except Exception as exc:
        db.session.rollback()
        return _json_error("Failed to save license", 500, str(exc))


@compliance_bp.route("/api/licenses/<int:license_id>", methods=["PUT"])
def api_update_license(license_id: int):
    """Update an existing license."""
    lic = LicenseDocument.query.get(license_id)
    if not lic:
        return _json_error("License not found", 404)

    data = request.get_json(silent=True) or {}
    try:
        if data.get("license_type"):
            lic.license_type = str(data["license_type"]).strip().upper()
        if data.get("license_name"):
            lic.license_name = str(data["license_name"]).strip()
        if data.get("license_no"):
            lic.license_no = str(data["license_no"]).strip()
        if "issuing_authority" in data:
            lic.issuing_authority = str(data["issuing_authority"]).strip() or None
        if data.get("expiry_date"):
            new_expiry = _parse_date(data["expiry_date"])
            if not new_expiry:
                return _json_error("Invalid expiry_date format", 400)
            lic.expiry_date = new_expiry
        if data.get("issued_date"):
            lic.issued_date = _parse_date(data["issued_date"])
        if "doc_url" in data:
            lic.doc_url = str(data["doc_url"]).strip() or None
        if "notes" in data:
            lic.notes = str(data["notes"]).strip() or None
        if "renewal_cost" in data:
            lic.renewal_cost = float(data["renewal_cost"]) if data["renewal_cost"] else None
        if "renewal_contact" in data:
            lic.renewal_contact = str(data["renewal_contact"]).strip() or None

        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as exc:
        db.session.rollback()
        return _json_error("Failed to update license", 500, str(exc))


@compliance_bp.route("/api/licenses/<int:license_id>", methods=["DELETE"])
def api_delete_license(license_id: int):
    """Soft-delete a license."""
    lic = LicenseDocument.query.get(license_id)
    if not lic:
        return _json_error("License not found", 404)
    try:
        lic.is_active = False
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as exc:
        db.session.rollback()
        return _json_error("Failed to delete license", 500, str(exc))
