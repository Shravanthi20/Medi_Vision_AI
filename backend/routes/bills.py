from datetime import datetime, date as date_type

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.sales import SalesBill, SalesBillItem
from ..models.core import Customer, Doctor, Item, Location
from ..models.inventory import StockBatch
from ..models.lookups import BillType
from ..services.whatsapp import send_whatsapp_receipt

bills_bp = Blueprint("bills", __name__)


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
        item = Item.query.get(bi.item_id)
        bill_items.append({
            "id":    bi.item_id,
            "n":     item.item_name if item else bi.item_id,
            "p":     float(bi.selling_price_at_sale),
            "qty":   bi.qty_sold,
            "s":     bi.qty_sold,
        })

    customer = Customer.query.get(bill.customer_id) if bill.customer_id else None
    doctor   = Doctor.query.get(bill.doctor_id)     if bill.doctor_id   else None
    bt       = BillType.query.get(bill.bill_type_id)

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


def _adjust_customer(name: str, phone: str, total_delta: float, visit_delta: int,
                     allow_insert: bool = True) -> None:
    """Update or create a Customer record with aggregated sales stats."""
    if not name:
        return
    customer = Customer.query.filter(
        func.lower(Customer.customer_name) == name.strip().lower()
    ).first()

    if customer:
        customer.outstanding_balance = max(0, float(customer.outstanding_balance or 0) + total_delta)
    elif allow_insert:
        customer = Customer(
            customer_name=name.strip(),
            phone=phone or "",
            is_cash_customer=True,
        )
        db.session.add(customer)
    db.session.flush()


def _apply_stock_delta(items: list, multiplier: int) -> None:
    """Adjust StockBatch.current_qty for each item in a bill."""
    for cart_item in items:
        item_id = str(cart_item.get("id", "")).strip()
        qty = int(cart_item.get("qty", 0) or 0)
        if not item_id or qty <= 0:
            continue
        batch = (
            StockBatch.query
            .filter_by(item_id=item_id)
            .order_by(StockBatch.stock_batch_id.desc())
            .first()
        )
        if batch:
            batch.current_qty = max(0, batch.current_qty + qty * multiplier)
    db.session.flush()



@bills_bp.route("/api/bills", methods=["GET"])
def get_bills():
    start_ts = request.args.get("start_date")
    end_ts   = request.args.get("end_date")
    customer = request.args.get("customer", "").lower()
    doctor   = request.args.get("doctor", "").lower()

    query = SalesBill.query.filter_by(is_cancelled=False)

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

    bills = query.order_by(SalesBill.bill_id.desc()).all()
    return jsonify([_bill_to_compat(b) for b in bills])



@bills_bp.route("/api/bills/<bill_id>", methods=["GET"])
def get_bill(bill_id):
    # frontend uses "B-<int>" format
    real_id = bill_id.replace("B-", "").strip()
    bill = SalesBill.query.get(real_id)
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

        now = datetime.utcnow()
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
            prescription_base64=data.get("prescription") or data.get("rx"),
        )
        db.session.add(bill)
        db.session.flush()  # get bill.bill_id

        # Create bill line items
        for cart_item in cart_items:
            item_id = str(cart_item.get("id", "")).strip()
            qty     = int(cart_item.get("qty", 1) or 1)
            price   = float(cart_item.get("p", 0) or 0)
            item_obj = Item.query.get(item_id)

            batch = (
                StockBatch.query
                .filter_by(item_id=item_id)
                .order_by(StockBatch.stock_batch_id.desc())
                .first()
            )
            if not batch or not item_obj:
                continue  # skip items not in inventory

            bill_item = SalesBillItem(
                bill_id=bill.bill_id,
                stock_batch_id=batch.stock_batch_id,
                item_id=item_id,
                qty_sold=qty,
                mrp_at_sale=float(batch.mrp),
                purchase_rate_at_sale=float(batch.purchase_rate),
                selling_price_at_sale=price,
                discount_pct=0,
                net_rate=price,
                gst_slab_id=item_obj.sales_gst_slab_id,
                cgst_pct=2.5,
                sgst_pct=2.5,
                igst_pct=0,
                gst_amount=round(price * qty * 0.05, 2),
                profit_pct=0,
                value=round(price * qty, 2),
            )
            db.session.add(bill_item)

        # Deduct stock
        _apply_stock_delta(cart_items, -1)

        # Update customer totals
        _adjust_customer(customer_name, customer_phone, net, 1)

        db.session.commit()

        # WhatsApp receipt
        if customer_phone:
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

        return jsonify({"status": "success", "id": f"B-{bill.bill_id}"})

    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save bill", 500, str(err))



@bills_bp.route("/api/bills/<bill_id>", methods=["PATCH", "PUT"])
def update_bill(bill_id):
    real_id = bill_id.replace("B-", "").strip()
    bill = SalesBill.query.get(real_id)
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
    bill = SalesBill.query.get(real_id)
    if not bill:
        return _json_error("Bill not found", 404, {"id": bill_id})

    try:
        # Restore stock for all items in this bill
        cart_items = [
            {"id": bi.item_id, "qty": bi.qty_sold}
            for bi in bill.items
        ]
        _apply_stock_delta(cart_items, +1)

        # Soft-delete via cancel
        bill.is_cancelled  = True
        bill.cancel_reason = "Deleted via API"
        bill.cancelled_at  = datetime.utcnow()

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
