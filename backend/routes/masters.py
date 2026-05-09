from datetime import datetime
import json
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.core import Customer, Doctor, Role, Supplier, User
from ..models.lookups import PaymentMode
from ..models.sales import ReceiptPayment, SalesBill


masters_bp = Blueprint("masters", __name__)


def json_error(message: str, status_code: int = 400, details=None):
    payload = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def required_fields(payload: dict, fields: list[str]) -> list[str]:
    missing = []
    for field in fields:
        if field not in payload or payload[field] is None:
            missing.append(field)
            continue
        if isinstance(payload[field], str) and not payload[field].strip():
            missing.append(field)
    return missing


def _supplier_code(name: str) -> str:
    base = name.strip().upper().replace(" ", "_")[:20] or "SUP"
    exists = Supplier.query.filter_by(supplier_code=base).first()
    if not exists:
        return base
    return f"{base[:14]}_{int(datetime.utcnow().timestamp()) % 100000}"


def _ensure_payment_context() -> tuple[str, int]:
    role = Role.query.first()
    if not role:
        role = Role(role_name="Admin")
        db.session.add(role)
        db.session.flush()

    user = User.query.first()
    if not user:
        import hashlib
        import uuid

        user = User(
            user_id=uuid.uuid4(),
            username="admin",
            password_hash=hashlib.sha256(b"admin").hexdigest(),
            role_id=role.role_id,
            is_super_admin=True,
        )
        db.session.add(user)
        db.session.flush()

    payment_mode = PaymentMode.query.filter_by(payment_mode_code="CASH").first()
    if not payment_mode:
        payment_mode = PaymentMode(payment_mode_code="CASH", payment_mode_name="Cash")
        db.session.add(payment_mode)
        db.session.flush()

    db.session.commit()
    return str(user.user_id), payment_mode.payment_mode_id


@masters_bp.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    rows = Supplier.query.order_by(Supplier.supplier_name.asc()).all()
    return jsonify(
        [
            {
                "id": row.supplier_id,
                "name": row.supplier_name,
                "phone": row.phone or "",
                "gst": row.gstin or "",
                "last_order": "-",
                "status": "Active" if row.is_active else "Inactive",
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/suppliers", methods=["POST"])
def add_supplier():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "phone"])
    if missing:
        return json_error("Missing required supplier fields", 400, missing)
    try:
        supplier = None
        supplier_id = data.get("id")
        if supplier_id:
            supplier = Supplier.query.get(supplier_id)
        if not supplier:
            supplier = Supplier(
                supplier_code=_supplier_code(data["name"]),
                supplier_name=data["name"],
            )
            db.session.add(supplier)

        supplier.supplier_name = data["name"]
        supplier.phone = data["phone"]
        supplier.gstin = data.get("gst", "")
        supplier.is_active = str(data.get("status", "Active")).lower() == "active"
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to save supplier", 500, str(err))


@masters_bp.route("/api/customers", methods=["GET"])
def get_customers():
    rows = Customer.query.order_by(Customer.customer_name.asc()).all()
    return jsonify(
        [
            {
                "id": row.customer_id,
                "name": row.customer_name,
                "phone": row.phone or "",
                "visits": SalesBill.query.filter_by(customer_id=row.customer_id, is_cancelled=False).count(),
                "total_spend": float(
                    db.session.query(func.coalesce(func.sum(SalesBill.net_amount), 0))
                    .filter(SalesBill.customer_id == row.customer_id, SalesBill.is_cancelled.is_(False))
                    .scalar()
                ),
                "address": row.address or "",
                "email": "",
                "face_vector": json.dumps(row.face_embedding.tolist()) if row.face_embedding is not None else "",
                "balance": float(row.outstanding_balance or 0),
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/customers", methods=["POST"])
def add_customer():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "phone"])
    if missing:
        return json_error("Missing required customer fields", 400, missing)
    try:
        customer = None
        customer_id = data.get("id")
        if customer_id:
            customer = Customer.query.get(customer_id)
        if not customer:
            customer = Customer(customer_name=data["name"], phone=data["phone"])
            db.session.add(customer)

        customer.customer_name = data["name"]
        customer.phone = data["phone"]
        customer.address = data.get("address", "")
        customer.is_active = True
        if "balance" in data:
            customer.outstanding_balance = float(data.get("balance", 0) or 0)
        
        if "face_vector" in data and data["face_vector"]:
            try:
                vector_list = json.loads(data["face_vector"])
                if isinstance(vector_list, list) and len(vector_list) == 128:
                    customer.face_embedding = vector_list
            except (json.JSONDecodeError, ValueError):
                pass

        db.session.commit()
        return jsonify({"status": "success"})
    except (ValueError, TypeError) as err:
        db.session.rollback()
        return json_error("Invalid customer payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to save customer", 500, str(err))


@masters_bp.route("/api/doctors", methods=["GET"])
def get_doctors():
    rows = Doctor.query.order_by(Doctor.doctor_name.asc()).all()
    return jsonify(
        [
            {
                "id": row.doctor_id,
                "name": row.doctor_name,
                "specialty": row.qualification or "",
                "hospital": row.address or "",
                "phone": row.phone or "",
                "email": "",
            }
            for row in rows
        ]
    )


@masters_bp.route("/api/doctors", methods=["POST"])
def add_doctor():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "specialty", "hospital", "phone"])
    if missing:
        return json_error("Missing required doctor fields", 400, missing)
    try:
        doctor = None
        doctor_id = data.get("id")
        if doctor_id:
            doctor = Doctor.query.get(doctor_id)
        if not doctor:
            doctor = Doctor(doctor_name=data["name"])
            db.session.add(doctor)

        doctor.doctor_name = data["name"]
        doctor.qualification = data.get("specialty", "")
        doctor.address = data.get("hospital", "")
        doctor.phone = data.get("phone", "")
        doctor.is_active = True
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to save doctor", 500, str(err))


@masters_bp.route("/api/suppliers/<id>", methods=["DELETE"])
def delete_supplier(id):
    supplier = Supplier.query.get(id)
    if supplier:
        db.session.delete(supplier)
        db.session.commit()
    return jsonify({"status": "success"})


@masters_bp.route("/api/customers/<id>", methods=["DELETE"])
def delete_customer(id):
    customer = Customer.query.get(id)
    if customer:
        db.session.delete(customer)
        db.session.commit()
    return jsonify({"status": "success"})


@masters_bp.route("/api/customers/<id>/ledger", methods=["GET"])
def get_customer_ledger(id):
    bills = SalesBill.query.filter(
        SalesBill.customer_id == id,
        SalesBill.is_cancelled.is_(False),
    ).all()
    receipts = ReceiptPayment.query.filter_by(customer_id=id).all()

    events = []
    for bill in bills:
        events.append(
            {
                "date": datetime.combine(bill.bill_date, bill.bill_time),
                "kind": "Sale",
                "ref_id": f"B-{bill.bill_id}",
                "description": f"Bill #B-{bill.bill_id}",
                "debit": float(bill.net_amount),
                "credit": 0.0,
            }
        )
    for receipt in receipts:
        events.append(
            {
                "date": datetime.combine(receipt.receipt_date, datetime.min.time()),
                "kind": "Payment",
                "ref_id": f"PAY-{receipt.receipt_id}",
                "description": receipt.remarks or "Manual Payment",
                "debit": 0.0,
                "credit": float(receipt.amount),
            }
        )

    events.sort(key=lambda e: e["date"])
    running_balance = 0.0
    out = []
    for idx, ev in enumerate(events, start=1):
        running_balance += ev["debit"] - ev["credit"]
        out.append(
            {
                "id": idx,
                "customer_id": int(id),
                "date": ev["date"].isoformat() + "Z",
                "ref_type": ev["kind"],
                "ref_id": ev["ref_id"],
                "description": ev["description"],
                "debit": ev["debit"],
                "credit": ev["credit"],
                "balance": running_balance,
            }
        )

    return jsonify(out)


@masters_bp.route("/api/customers/<id>/payment", methods=["POST"])
def record_customer_payment(id):
    data = request.get_json(silent=True) or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return json_error("Amount must be greater than zero", 400)
    
    try:
        customer = Customer.query.get(id)
        if not customer:
            return json_error("Customer not found", 404)

        user_id, payment_mode_id = _ensure_payment_context()

        current_balance = float(customer.outstanding_balance or 0)
        new_balance = current_balance - amount
        customer.outstanding_balance = new_balance

        receipt = ReceiptPayment(
            customer_id=customer.customer_id,
            bill_id=None,
            receipt_date=datetime.utcnow().date(),
            amount=amount,
            payment_mode_id=payment_mode_id,
            user_id=user_id,
            remarks=data.get("description", "Manual Payment"),
        )
        db.session.add(receipt)
        db.session.commit()

        return jsonify({"status": "success", "new_balance": new_balance})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to record payment", 500, str(err))


@masters_bp.route("/api/doctors/<id>", methods=["DELETE"])
def delete_doctor(id):
    doctor = Doctor.query.get(id)
    if doctor:
        db.session.delete(doctor)
        db.session.commit()
    return jsonify({"status": "success"})
