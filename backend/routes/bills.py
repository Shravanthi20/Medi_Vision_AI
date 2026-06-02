from datetime import datetime, date as date_type, timezone

from flask import Blueprint, jsonify, request, render_template, session
from sqlalchemy import func
import logging

from ..extensions import db
from .auth import login_required
from ..models.sales import SalesBill, SalesBillItem, BillingVoucher, ReceiptPayment
from ..models.core import Customer, Doctor, Item, Location
from ..models.inventory import StockBatch, StockLedger
from ..models.lookups import BillType, TxnType, PaymentMode
from ..analytics_logic import update_customer_purchase_pattern
from ..services.whatsapp import send_whatsapp_receipt

bills_bp = Blueprint("bills", __name__)
logger = logging.getLogger(__name__)


def _json_error(message, code=400, details=None):
    return jsonify({"error": message, "details": details}), code


def _get_or_create_bill_type(code: str = "RET") -> BillType:
    bt = BillType.query.filter_by(bill_type_code=code).first()
    if not bt:
        bt = BillType(bill_type_code=code, bill_type_name="Retail")
        db.session.add(bt)
        db.session.flush()
    return bt


def _get_or_create_defaults():
    from ..models.hr import Salesman
    from ..models.core import FinancialYear as FY, Location, Role, User

    role = Role.query.first()
    if not role:
        role = Role(role_name="Admin")
        db.session.add(role)
        db.session.flush()

    fy = FY.query.filter_by(is_active=True).first()
    if not fy:
        today = date_type.today()
        fy = FY(
            fy_label=f"{today.year}-{str(today.year+1)[-2:]}",
            start_date=date_type(today.year, 4, 1),
            end_date=date_type(today.year + 1, 3, 31),
            is_active=True,
        )
        db.session.add(fy)
        db.session.flush()

    salesman = Salesman.query.first()
    if not salesman:
        salesman = Salesman(
            salesman_code="SYS",
            salesman_name="System",
            role_id=role.role_id,
        )
        db.session.add(salesman)
        db.session.flush()

    user = User.query.first()
    if not user:
        import uuid, hashlib
        user = User(
            user_id=uuid.uuid4(),
            username="admin",
            password_hash=hashlib.sha256(b"admin").hexdigest(),
            role_id=role.role_id,
            salesman_id=salesman.salesman_id,
            is_super_admin=True,
        )
        db.session.add(user)
        db.session.flush()

    location = Location.query.first()
    if not location:
        location = Location(location_code="MAIN", location_name="Main Store")
        db.session.add(location)
        db.session.flush()

    bill_type = _get_or_create_bill_type()

    db.session.commit()
    return fy.financial_year_id, salesman.salesman_id, user.user_id, location.location_id, bill_type.bill_type_id


def _bill_to_compat(bill: SalesBill) -> dict:
    bill_items = []
    for bi in bill.items:
        # Use the eagerly loaded relationship instead of querying
        item = bi.item
        bill_items.append({
            "id":    bi.item_id,
            "n":     item.item_name if item else bi.item_id,
            "p":     float(bi.selling_price_at_sale),
            "qty":   bi.qty_sold,
            "s":     bi.qty_sold,
        })

    # Use the eagerly loaded relationships directly
    customer = bill.customer
    doctor   = bill.doctor
    bt       = bill.bill_type

    legacy_id = f"B-{bill.bill_id}"

    return {
        "id":             legacy_id,
        "ts":             int(bill.created_at.timestamp() * 1000),
        "date":           bill.bill_date.strftime("%d/%m/%Y") + " " + bill.bill_time.strftime("%H:%M"),
        "cust":           customer.customer_name if customer else "Walk-in",
        "phone":          customer.phone         if customer else "",
        "pay":            "cash",
        "sub":            float(bill.gross_amount),
        "disc":           float(bill.discount_amount),
        "tax":            float(bill.cgst_amount + bill.sgst_amount + bill.igst_amount),
        "total":          float(bill.net_amount),
        "items":          bill_items,
        "doctor":         doctor.doctor_name if doctor else "Self",
        "customer_type":  "customer",
        "bill_type":      bt.bill_type_code.lower() if bt else "retail",
        "discount_type":  "amt",
        "discount_value": float(bill.discount_amount),
        "prescription":   bill.prescription_base64 or "",
        "rx":             bill.prescription_base64 or "",
    }


def _adjust_customer(name: str, phone: str, outstanding_delta: float, spend_delta: float, visit_delta: int,
                     allow_insert: bool = True) -> None:
    """Update or create a Customer record with aggregated sales stats."""
    if not name:
        return
    customer = Customer.query.filter(
        func.lower(Customer.customer_name) == name.strip().lower()
    ).first()

    if customer:
        customer.outstanding_balance = max(0, float(customer.outstanding_balance or 0) + outstanding_delta)
        # Always update total spend regardless of payment mode
        customer.total_spend = float(customer.total_spend or 0) + spend_delta
        customer.total_visits = (customer.total_visits or 0) + visit_delta
    elif allow_insert:
        customer = Customer(
            customer_name=name.strip(),
            phone=phone or "",
            is_cash_customer=True,
            outstanding_balance=outstanding_delta,
            total_spend=spend_delta,
            total_visits=visit_delta
        )
        db.session.add(customer)
    db.session.flush()


def _cancel_bill_record(bill: SalesBill, reason: str) -> None:
    cart_items = [{"id": bi.item_id, "qty": bi.qty_sold} for bi in bill.items]
    _apply_stock_delta(bill.bill_id, cart_items, +1)

    if bill.customer_id:
        customer = db.session.get(Customer, bill.customer_id)
        if customer:
            customer.outstanding_balance = max(
                0,
                float(customer.outstanding_balance or 0) - float(bill.net_amount or 0),
            )

    bill.is_cancelled = True
    bill.cancel_reason = reason
    bill.cancelled_at = datetime.now(timezone.utc)


def _apply_stock_delta(bill_id: int, items: list, multiplier: int) -> None:
    """Adjust StockBatch.current_qty for each item in a bill using FIFO logic for sales."""
    txn_type_code = "SALE" if multiplier < 0 else "RETURN"
    txn_type = TxnType.query.filter_by(txn_type_code=txn_type_code).first()
    if not txn_type:
        txn_type = TxnType(txn_type_code=txn_type_code, txn_type_name="Sales" if multiplier < 0 else "Sales Return")
        db.session.add(txn_type)
        db.session.flush()

    for cart_item in items:
        item_id = str(cart_item.get("id", "")).strip()
        qty_to_adjust = int(cart_item.get("qty", 0) or 0)
        if not item_id or qty_to_adjust <= 0:
            continue

        if multiplier < 0:
            # --- SALES (FIFO Logic) ---
            # --- SALES (Simplified) ---
            batch = (
                StockBatch.query.filter_by(item_id=item_id)
                .order_by(StockBatch.expiry_date.asc(), StockBatch.stock_batch_id.asc())
                .first()
            )

            if batch:
                deduct = qty_to_adjust
                batch.current_qty -= deduct
                
                # Log to StockLedger
                ledger = StockLedger(
                    stock_batch_id=batch.stock_batch_id,
                    item_id=batch.item_id,
                    txn_type_id=txn_type.txn_type_id,
                    txn_date=date_type.today(),
                    qty_in=0,
                    qty_out=deduct,
                    balance_qty=batch.current_qty,
                    ref_type="SALE",
                    ref_id=bill_id
                )
                db.session.add(ledger)


        else:
            # --- RETURNS (Restore to Newest Batch) ---
            batch = StockBatch.query.filter_by(item_id=item_id).order_by(StockBatch.expiry_date.desc()).first()
            if batch:
                batch.current_qty += qty_to_adjust
                ledger = StockLedger(
                    stock_batch_id=batch.stock_batch_id,
                    item_id=batch.item_id,
                    txn_type_id=txn_type.txn_type_id,
                    txn_date=date_type.today(),
                    qty_in=qty_to_adjust,
                    qty_out=0,
                    balance_qty=batch.current_qty,
                    ref_type="RETURN",
                    ref_id=bill_id
                )
                db.session.add(ledger)
    db.session.flush()


def _parse_ui_date(value: str | None, *, default=None):
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


def _voucher_to_compat(voucher: BillingVoucher) -> dict:
    return {
        "id": voucher.voucher_id,
        "type": voucher.voucher_type,
        "voucher_no": voucher.voucher_no,
        "voucher_date": voucher.voucher_date.isoformat() if voucher.voucher_date else "",
        "account_date": voucher.account_date.isoformat() if voucher.account_date else "",
        "reference_no": voucher.reference_no or "",
        "reference_date": voucher.reference_date.isoformat() if voucher.reference_date else "",
        "customer_code": voucher.customer_code or "",
        "account_code": voucher.account_code or "",
        "account_name": voucher.account_name or "",
        "party_name": voucher.party_name or "",
        "payment_type": voucher.payment_type or "",
        "bank_code": voucher.bank_code or "",
        "amount": float(voucher.amount or 0),
        "remarks": voucher.remarks or "",
        "linked_bill_id": f"B-{voucher.linked_bill_id}" if voucher.linked_bill_id else "",
        "created_at": voucher.created_at.isoformat() + "Z" if voucher.created_at else "",
    }


@bills_bp.route("/billing/debit-notes", methods=["GET"])
@login_required
def debit_note_page():
    return render_template("debitnote.html", current_user=_current_page_user())


@bills_bp.route("/billing/sales-receipts", methods=["GET"])
@login_required
def sales_receipt_page():
    return render_template("SalesReceipt.html", current_user=_current_page_user())


@bills_bp.route("/api/billing/vouchers", methods=["GET"])
def get_billing_vouchers():
    voucher_type = request.args.get("type", "").strip().lower()
    query = BillingVoucher.query
    if voucher_type:
        query = query.filter(BillingVoucher.voucher_type == voucher_type)
    rows = query.order_by(BillingVoucher.voucher_id.desc()).all()
    return jsonify([_voucher_to_compat(row) for row in rows])


@bills_bp.route("/api/billing/vouchers/<int:voucher_id>", methods=["GET"])
def get_billing_voucher(voucher_id):
    row = db.session.get(BillingVoucher, voucher_id)
    if not row:
        return _json_error("Voucher not found", 404, {"id": voucher_id})
    return jsonify(_voucher_to_compat(row))


@bills_bp.route("/api/billing/vouchers", methods=["POST"])
def save_billing_voucher():
    data = request.get_json(silent=True) or {}
    voucher_type = str(data.get("type", "")).strip().lower()
    if voucher_type not in {"debit_note", "sales_receipt_credit"}:
        return _json_error("Unsupported voucher type", 400, {"type": voucher_type})

    voucher_no = str(data.get("voucher_no", "")).strip()
    if not voucher_no:
        return _json_error("Missing required field: voucher_no", 400)

    voucher_date = _parse_ui_date(data.get("voucher_date"), default=date_type.today())
    amount = float(data.get("amount", 0) or 0)
    if amount < 0:
        return _json_error("Amount must be zero or greater", 400)

    try:
        _, _, user_id, _, _ = _get_or_create_defaults()
        row = None
        voucher_id = data.get("id")
        if voucher_id:
            row = db.session.get(BillingVoucher, voucher_id)
            if not row:
                return _json_error("Voucher not found", 404, {"id": voucher_id})
        else:
            duplicate = BillingVoucher.query.filter_by(
                voucher_type=voucher_type,
                voucher_no=voucher_no,
            ).first()
            if duplicate:
                return _json_error("Voucher number already exists", 409, {"voucher_no": voucher_no})
            row = BillingVoucher(voucher_type=voucher_type, voucher_no=voucher_no, user_id=user_id)
            db.session.add(row)

        row.voucher_type = voucher_type
        row.voucher_no = voucher_no
        row.voucher_date = voucher_date
        row.account_date = _parse_ui_date(data.get("account_date"))
        row.reference_no = str(data.get("reference_no", "")).strip()
        row.reference_date = _parse_ui_date(data.get("reference_date"))
        row.customer_code = str(data.get("customer_code", "")).strip()
        row.account_code = str(data.get("account_code", "")).strip()
        row.account_name = str(data.get("account_name", "")).strip()
        row.party_name = str(data.get("party_name", "")).strip()
        row.payment_type = str(data.get("payment_type", "")).strip()
        row.bank_code = str(data.get("bank_code", "")).strip()
        row.amount = amount
        row.remarks = str(data.get("remarks", "")).strip()

        linked_bill_id = str(data.get("linked_bill_id", "")).strip()
        if linked_bill_id:
            real_bill_id = linked_bill_id.replace("B-", "").strip()
            linked_bill = db.session.get(SalesBill, real_bill_id)
            row.linked_bill_id = linked_bill.bill_id if linked_bill else None
        else:
            row.linked_bill_id = None

        customer_code = row.customer_code
        if customer_code.isdigit():
            customer = db.session.get(Customer, int(customer_code))
            if customer and not row.party_name:
                row.party_name = customer.customer_name

        db.session.commit()
        return jsonify({"status": "success", "voucher": _voucher_to_compat(row)})
    except (ValueError, TypeError) as err:
        db.session.rollback()
        return _json_error("Invalid voucher payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save voucher", 500, str(err))


@bills_bp.route("/api/billing/vouchers/<int:voucher_id>", methods=["DELETE"])
def delete_billing_voucher(voucher_id):
    row = db.session.get(BillingVoucher, voucher_id)
    if not row:
        return _json_error("Voucher not found", 404, {"id": voucher_id})
    try:
        db.session.delete(row)
        db.session.commit()
        return jsonify({"status": "success", "deleted": voucher_id})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete voucher", 500, str(err))


@bills_bp.route("/api/bills/<bill_id>/cancel-preview", methods=["GET"])
def get_cancel_bill_preview(bill_id):
    real_id = bill_id.replace("B-", "").strip()
    bill = db.session.get(SalesBill, real_id)
    if not bill or bill.is_cancelled:
        return _json_error("Bill not found", 404, {"id": bill_id})

    customer = db.session.get(Customer, bill.customer_id) if bill.customer_id else None
    doctor = db.session.get(Doctor, bill.doctor_id) if bill.doctor_id else None
    salesman_name = "System"
    if bill.salesman_id:
        from ..models.hr import Salesman

        salesman = db.session.get(Salesman, bill.salesman_id)
        if salesman and salesman.salesman_name:
            salesman_name = salesman.salesman_name

    items = []
    for idx, bi in enumerate(bill.items, start=1):
        item = db.session.get(Item, bi.item_id)
        batch = db.session.get(StockBatch, bi.stock_batch_id) if bi.stock_batch_id else None
        items.append({
            "line_no": idx,
            "item_code": bi.item_id,
            "item_name": item.item_name if item else bi.item_id,
            "batch": batch.batch_no if batch else "",
            "expiry": batch.expiry_date.strftime("%m/%y") if batch and batch.expiry_date else "",
            "qty": int(bi.qty_sold or 0),
            "mrp": float(bi.mrp_at_sale or 0),
            "value": float(bi.value or 0),
        })

    return jsonify({
        "id": f"B-{bill.bill_id}",
        "bill_no": str(bill.bill_no),
        "cashbill_no": str(bill.bill_no),
        "customer_name": customer.customer_name if customer else "Walk-in",
        "customer_address": customer.address if customer and customer.address else "",
        "doctor_name": doctor.doctor_name if doctor else "Self",
        "salesman_name": salesman_name,
        "remarks": bill.remarks or "",
        "total": float(bill.net_amount or 0),
        "items": items,
    })


@bills_bp.route("/api/bills/<bill_id>/cancel", methods=["POST"])
def cancel_bill_with_reason(bill_id):
    real_id = bill_id.replace("B-", "").strip()
    bill = db.session.get(SalesBill, real_id)
    if not bill:
        return _json_error("Bill not found", 404, {"id": bill_id})
    if bill.is_cancelled:
        return _json_error("Bill already cancelled", 409, {"id": bill_id})

    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason", "")).strip() or "Cancelled via cancel bill screen"

    try:
        _cancel_bill_record(bill, reason)
        db.session.commit()
        return jsonify({"status": "success", "id": bill_id, "reason": reason})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to cancel bill", 500, str(err))



@bills_bp.route("/api/bills/kpis", methods=["GET"])
def get_bills_kpis():
    from datetime import date, timedelta
    from sqlalchemy import func
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    today_stats = db.session.query(
        func.count(SalesBill.bill_id),
        func.sum(SalesBill.net_amount)
    ).filter(SalesBill.bill_date == today, SalesBill.is_cancelled == False).first()
    
    yesterday_stats = db.session.query(
        func.count(SalesBill.bill_id),
        func.sum(SalesBill.net_amount)
    ).filter(SalesBill.bill_date == yesterday, SalesBill.is_cancelled == False).first()
    
    total_bills = db.session.query(func.count(SalesBill.bill_id)).filter_by(is_cancelled=False).scalar()
    
    return jsonify({
        "today_bills": today_stats[0] or 0,
        "today_revenue": float(today_stats[1] or 0.0),
        "yesterday_bills": yesterday_stats[0] or 0,
        "yesterday_revenue": float(yesterday_stats[1] or 0.0),
        "total_bills": total_bills or 0
    })

@bills_bp.route("/api/bills", methods=["GET"])
def get_bills():
    page     = request.args.get("page", 1, type=int)
    limit    = request.args.get("limit", 50, type=int)
    start_ts = request.args.get("start_date")
    end_ts   = request.args.get("end_date")
    customer = request.args.get("customer", "").lower()
    doctor   = request.args.get("doctor", "").lower()

    # Eager load the required relationships to avoid N+1 queries
    query = SalesBill.query.options(
        db.joinedload(SalesBill.customer),
        db.joinedload(SalesBill.doctor),
        db.joinedload(SalesBill.salesman),
        db.joinedload(SalesBill.bill_type),
        db.joinedload(SalesBill.items).joinedload(SalesBillItem.item)
    ).filter_by(is_cancelled=False)

    if start_ts:
        dt = datetime.fromtimestamp(int(start_ts) / 1000)
        query = query.filter(SalesBill.bill_date >= dt.date())
    if end_ts:
        dt = datetime.fromtimestamp(int(end_ts) / 1000)
        query = query.filter(SalesBill.bill_date <= dt.date())
    if customer:
        matched = Customer.query.filter(
            func.lower(Customer.customer_name).contains(customer)
        ).all()
        ids = [c.customer_id for c in matched]
        query = query.filter(SalesBill.customer_id.in_(ids))
    if doctor:
        matched = Doctor.query.filter(
            func.lower(Doctor.doctor_name).contains(doctor)
        ).all()
        ids = [d.doctor_id for d in matched]
        query = query.filter(SalesBill.doctor_id.in_(ids))

    # Perform pagination instead of returning all rows
    paginated = query.order_by(SalesBill.bill_id.desc()).paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        "items": [_bill_to_compat(b) for b in paginated.items],
        "total": paginated.total,
        "pages": paginated.pages,
        "current_page": page,
        "limit": limit
    })



@bills_bp.route("/api/bills/<bill_id>", methods=["GET"])
def get_bill(bill_id):
    # frontend uses "B-<int>" format
    real_id = bill_id.replace("B-", "").strip()
    bill = db.session.get(SalesBill, real_id)
    if not bill or bill.is_cancelled:
        return _json_error("Bill not found", 404, {"id": bill_id})
    return jsonify(_bill_to_compat(bill))



@bills_bp.route("/api/bills", methods=["POST"])
def save_bill():
    data = request.get_json(silent=True) or {}
    required = ["cust", "pay", "sub", "disc", "tax", "total", "items"]
    for field in required:
        if field not in data:
            return _json_error(f"Missing required field: {field}", 400)

    cart_items = data.get("items", [])
    if not cart_items:
        return _json_error("Bill must include at least one item", 400)

    try:
        fy_id, salesman_id, user_id, location_id, bt_id = _get_or_create_defaults()

        # Resolve or create customer
        customer_name  = str(data.get("cust", "")).strip()
        customer_phone = str(data.get("phone", "")).strip()
        customer = None
        if customer_name and customer_name.lower() != "walk-in":
            customer = Customer.query.filter(
                func.lower(Customer.customer_name) == customer_name.lower()
            ).first()
            if not customer:
                customer = Customer(
                    customer_name=customer_name,
                    phone=customer_phone,
                    is_cash_customer=True,
                )
                db.session.add(customer)
                db.session.flush()
            
            if "is_chronic" in data:
                logger.debug("UPDATING CHRONIC STATUS for %s: %s", customer.customer_name, data['is_chronic'])
                customer.is_chronic_patient = (data["is_chronic"] is True)
                db.session.add(customer)
                db.session.flush()

        # Resolve or create doctor
        doctor_name = str(data.get("doctor", "Self")).strip()
        doctor_id = None
        if doctor_name and doctor_name.lower() not in ("", "self"):
            doc = Doctor.query.filter(
                func.lower(Doctor.doctor_name) == doctor_name.lower()
            ).first()
            if not doc:
                doc = Doctor(doctor_name=doctor_name)
                db.session.add(doc)
                db.session.flush()
            doctor_id = doc.doctor_id

        now = datetime.now(timezone.utc)
        gross   = float(data.get("sub", 0))
        disc_amt = float(data.get("disc", 0))
        tax_amt  = float(data.get("tax", 0))
        net      = float(data.get("total", 0))
        tax_half = round(tax_amt / 2, 2)

        bill = SalesBill(
            bill_no=db.session.query(func.coalesce(func.max(SalesBill.bill_no), 0)).scalar() + 1,
            bill_date=now.date(),
            bill_time=now.time(),
            financial_year_id=fy_id,
            customer_id=customer.customer_id if customer else None,
            doctor_id=doctor_id,
            salesman_id=salesman_id,
            user_id=user_id,
            location_id=location_id,
            bill_type_id=bt_id,
            gross_amount=gross,
            discount_pct=0,
            discount_amount=disc_amt,
            taxable_amount=gross - disc_amt,
            cgst_amount=tax_half,
            sgst_amount=tax_half,
            igst_amount=0,
            round_off=0,
            net_amount=net,
            payment_mode=data.get("pay", "cash").lower(),
            prescription_base64=data.get("prescription") or data.get("rx"),
        )
        db.session.add(bill)
        db.session.flush()  # get bill.bill_id

        # Create bill line items using FIFO batches
        for cart_item in cart_items:
            item_id = str(cart_item.get("id", "")).strip()
            qty_needed = int(cart_item.get("qty", 1) or 1)
            price = float(cart_item.get("p", 0) or 0)
            item_obj = db.session.get(Item, item_id)
            if not item_obj: continue

            # Find the primary batch for this item
            batch = StockBatch.query.filter_by(item_id=item_id).order_by(StockBatch.expiry_date.asc()).first()
            if batch:
                bill_item = SalesBillItem(
                    bill_id=bill.bill_id, 
                    stock_batch_id=batch.stock_batch_id, 
                    item_id=item_id, 
                    qty_sold=qty_needed, 
                    mrp_at_sale=float(batch.mrp), 
                    purchase_rate_at_sale=float(batch.purchase_rate), 
                    selling_price_at_sale=price, 
                    discount_pct=0, 
                    net_rate=price, 
                    gst_slab_id=item_obj.sales_gst_slab_id, 
                    cgst_pct=2.5, 
                    sgst_pct=2.5, 
                    igst_pct=0, 
                    gst_amount=round(price * qty_needed * 0.05, 2), 
                    profit_pct=0, 
                    value=round(price * qty_needed, 2)
                )
                db.session.add(bill_item)


        # Deduct stock
        _apply_stock_delta(bill.bill_id, cart_items, -1)

        # Update customer totals
        payment_mode = data.get("pay", "cash").lower()
        default_paid = 0 if payment_mode == 'credit' else net
        paid_amt = float(data.get("paid_amount", default_paid))
        outstanding = max(0, net - paid_amt)
        _adjust_customer(customer_name, customer_phone, outstanding, net, 1)
        
        # If any amount was paid, record a ReceiptPayment
        if paid_amt > 0 and customer:
            pm_code = payment_mode.upper()
            if pm_code == "CREDIT": pm_code = "CASH" # Default to cash if they paid something on a credit bill
            
            pm_obj = PaymentMode.query.filter(func.upper(PaymentMode.payment_mode_code) == pm_code).first()
            if not pm_obj:
                pm_obj = PaymentMode.query.filter_by(payment_mode_code="CASH").first()
                
            if pm_obj:
                payment = ReceiptPayment(
                    customer_id=customer.customer_id,
                    bill_id=bill.bill_id,
                    receipt_date=now.date(),
                    amount=paid_amt,
                    payment_mode_id=pm_obj.payment_mode_id,
                    user_id=user_id,
                    remarks=f"Partial/Full payment for Bill #{bill.bill_no}"
                )
                db.session.add(payment)
        
        # Explicitly update chronic status again to be sure
        target_cust = None
        db.session.commit()

        if customer:
            for cart_item in cart_items:
                item_id = str(cart_item.get("id", "")).strip()
                qty = int(cart_item.get("qty", 1) or 1)
                is_chr = bool(cart_item.get("is_chronic", False))
                if item_id and qty > 0:
                    update_customer_purchase_pattern(customer.customer_id, item_id, qty, is_chronic=is_chr)
        
        db.session.commit()

        # WhatsApp receipt (Twilio Backup)
        if customer_phone and data.get("send_twilio_whatsapp"):
            try:
                items_str = "\n".join(
                    f"- {ci.get('n','Item')} (Qty:{ci.get('qty',1)}) : Rs.{float(ci.get('p',0))*int(ci.get('qty',1)):.2f}"
                    for ci in cart_items
                )
                msg = (
                    f"Hello {customer_name},\n\n"
                    f"Your bill for Rs. {net:.2f} is ready.\n\n"
                    f"*Purchases:*\n{items_str}\n"
                    f"Subtotal: Rs. {gross:.2f}\n"
                    f"Discount: Rs. {disc_amt:.2f}\n"
                    f"GST: Rs. {tax_amt:.2f}\n"
                    f"*Total: Rs. {net:.2f}*\n\n"
                    f"Thank you for visiting Selvam Medicals! 💊"
                )
                send_whatsapp_receipt(f"B-{bill.bill_id}", customer_phone, msg)
            except Exception:
                pass  # non-critical

        # Fetch latest summary if customer exists
        customer_summary = None
        if customer:
            from .masters import _family_summary
            customer_summary = _family_summary(customer)

        return jsonify({
            "status": "success", 
            "id": f"B-{bill.bill_id}",
            "customer": customer_summary
        })

    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save bill", 500, str(err))



@bills_bp.route("/api/bills/<bill_id>", methods=["PATCH", "PUT"])
def update_bill(bill_id):
    real_id = bill_id.replace("B-", "").strip()
    bill = db.session.get(SalesBill, real_id)
    if not bill or bill.is_cancelled:
        return _json_error("Bill not found", 404, {"id": bill_id})

    data = request.get_json(silent=True) or {}
    try:
        gross   = float(data.get("sub",   float(bill.gross_amount)))
        disc    = float(data.get("disc",  float(bill.discount_amount)))
        tax     = float(data.get("tax",   float(bill.cgst_amount + bill.sgst_amount)))
        net     = float(data.get("total", float(bill.net_amount)))
        tax_half = round(tax / 2, 2)

        bill.gross_amount    = gross
        bill.discount_amount = disc
        bill.taxable_amount  = gross - disc
        bill.cgst_amount     = tax_half
        bill.sgst_amount     = tax_half
        bill.net_amount      = net

        db.session.commit()
        return jsonify(_bill_to_compat(bill))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to update bill", 500, str(err))



@bills_bp.route("/api/bills/<bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    real_id = bill_id.replace("B-", "").strip()
    bill = db.session.get(SalesBill, real_id)
    if not bill:
        return _json_error("Bill not found", 404, {"id": bill_id})

    try:
        _cancel_bill_record(bill, "Deleted via API")

        db.session.commit()
        return jsonify({"status": "success", "deleted": bill_id})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete bill", 500, str(err))



@bills_bp.route("/api/reports/gst", methods=["GET"])
def get_gst_report():
    start_ts = request.args.get("start_date")
    end_ts   = request.args.get("end_date")

    query = SalesBill.query.filter_by(is_cancelled=False)
    if start_ts:
        query = query.filter(
            SalesBill.bill_date >= datetime.fromtimestamp(int(start_ts) / 1000).date()
        )
    if end_ts:
        query = query.filter(
            SalesBill.bill_date <= datetime.fromtimestamp(int(end_ts) / 1000).date()
        )

    total_sales = total_tax = taxable = non_taxable = 0.0
    for bill in query.all():
        t = float(bill.net_amount)
        tx = float(bill.cgst_amount + bill.sgst_amount + bill.igst_amount)
        total_sales += t
        total_tax   += tx
        if tx > 0:
            taxable     += float(bill.taxable_amount)
        else:
            non_taxable += float(bill.taxable_amount)

    return jsonify({
        "total_sales":        total_sales,
        "total_tax":          total_tax,
        "taxable_amount":     taxable,
        "non_taxable_amount": non_taxable,
        "net_revenue":        total_sales - total_tax,
    })
