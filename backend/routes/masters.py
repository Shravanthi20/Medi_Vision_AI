from datetime import datetime
import json
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.core import Customer, Doctor, Role, Supplier, User
from ..models.lookups import PaymentMode
from ..models.sales import ReceiptPayment, SalesBill
from ..analytics_logic import get_personalized_suggestions


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


def _family_scope(customer: Customer) -> tuple[int, list[int]]:
    root_id = int(customer.family_head_id or customer.customer_id)
    rows = Customer.query.filter(
        (Customer.customer_id == root_id) | (Customer.family_head_id == root_id)
    ).all()
    customer_ids = sorted({row.customer_id for row in rows})
    if customer.customer_id not in customer_ids:
        customer_ids.append(customer.customer_id)
        customer_ids.sort()
    return root_id, customer_ids


def _family_summary(customer: Customer) -> dict:
    root_id, customer_ids = _family_scope(customer)
    member_rows = Customer.query.filter(Customer.customer_id.in_(customer_ids)).all()
    member_lookup = {row.customer_id: row for row in member_rows}
    head = member_lookup.get(root_id, customer)

    visits = SalesBill.query.filter(
        SalesBill.customer_id.in_(customer_ids),
        SalesBill.is_cancelled.is_(False),
    ).count()
    total_spend = float(
        db.session.query(func.coalesce(func.sum(SalesBill.net_amount), 0))
        .filter(
            SalesBill.customer_id.in_(customer_ids),
            SalesBill.is_cancelled.is_(False),
        )
        .scalar()
    )
    total_payments = float(
        db.session.query(func.coalesce(func.sum(ReceiptPayment.amount), 0))
        .filter(ReceiptPayment.customer_id.in_(customer_ids))
        .scalar()
    )

    if len(customer_ids) == 1:
        balance = float(customer.outstanding_balance or 0)
    else:
        balance = max(0.0, total_spend - total_payments)

    return {
        "family_head_id": root_id,
        "family_head_name": head.customer_name,
        "family_relation": customer.family_relation or ("Head" if root_id == customer.customer_id else "Member"),
        "family_member_count": len(customer_ids),
        "family_member_names": [member_lookup[cid].customer_name for cid in customer_ids if cid in member_lookup],
        "visits": visits,
        "total_spend": total_spend,
        "balance": balance,
    }


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
            (lambda summary: {
                "id": row.customer_id,
                "name": row.customer_name,
                "phone": row.phone or "",
                "visits": summary["visits"],
                "total_spend": summary["total_spend"],
                "address": row.address or "",
                "email": "",
                "face_vector": json.dumps(row.face_embedding.tolist()) if row.face_embedding is not None else "",
                "balance": summary["balance"],
                "family_head_id": summary["family_head_id"],
                "family_head_name": summary["family_head_name"],
                "family_relation": summary["family_relation"],
                "family_member_count": summary["family_member_count"],
                "family_member_names": summary["family_member_names"],
            })(_family_summary(row))
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

        family_head_id = data.get("family_head_id")
        if family_head_id in (None, "", "null"):
            customer.family_head_id = None
        else:
            resolved_head = Customer.query.get(family_head_id)
            if not resolved_head:
                return json_error("Family head customer not found", 404)
            if customer.customer_id and int(resolved_head.customer_id) == int(customer.customer_id):
                return json_error("Customer cannot be its own family head", 400)
            customer.family_head_id = int(resolved_head.family_head_id or resolved_head.customer_id)

        customer.family_relation = str(data.get("family_relation", "")).strip()
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


@masters_bp.route("/api/customers/<id>/family", methods=["GET"])
def get_customer_family(id):
    customer = Customer.query.get(id)
    if not customer:
        return json_error("Customer not found", 404)

    summary = _family_summary(customer)
    _, family_ids = _family_scope(customer)
    members = Customer.query.filter(Customer.customer_id.in_(family_ids)).order_by(Customer.customer_name.asc()).all()

    return jsonify(
        {
            "family_head_id": summary["family_head_id"],
            "family_head_name": summary["family_head_name"],
            "family_relation": summary["family_relation"],
            "family_member_count": summary["family_member_count"],
            "family_member_names": summary["family_member_names"],
            "summary": {
                "visits": summary["visits"],
                "total_spend": summary["total_spend"],
                "balance": summary["balance"],
            },
            "members": [
                {
                    "id": row.customer_id,
                    "name": row.customer_name,
                    "phone": row.phone or "",
                    "relation": row.family_relation or ("Head" if row.customer_id == summary["family_head_id"] else "Member"),
                }
                for row in members
            ],
        }
    )


@masters_bp.route("/api/customers/<id>/suggestions", methods=["GET"])
def get_customer_suggestions(id):
    """
    Get personalized medicine suggestions for a customer based on:
    - Customer's purchase history
    - Market basket analysis (items frequently bought together)
    - Top moving items in inventory
    
    Query parameters:
    - limit: Number of suggestions (default: 10, max: 50)
    - days_back: Look back window for analysis (default: 90)
    - exclude_recent_days: Exclude items purchased recently (default: 30)
    """
    customer = Customer.query.get(id)
    if not customer:
        return json_error("Customer not found", 404)
    
    limit = min(int(request.args.get("limit", 10)), 50)
    days_back = int(request.args.get("days_back", 90))
    exclude_recent_days = int(request.args.get("exclude_recent_days", 30))
    
    try:
        suggestions = get_personalized_suggestions(
            customer_id=int(id),
            limit=limit,
            days_back=days_back,
            exclude_recent_days=exclude_recent_days
        )
        return jsonify({
            "customer_id": int(id),
            "customer_name": customer.customer_name,
            "suggestions": suggestions,
            "count": len(suggestions),
            "parameters": {
                "limit": limit,
                "days_back": days_back,
                "exclude_recent_days": exclude_recent_days
            }
        })
    except Exception as err:
        return json_error("Failed to generate suggestions", 500, str(err))


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
    customer = Customer.query.get(id)
    if not customer:
        return json_error("Customer not found", 404)

    _, family_ids = _family_scope(customer)

    bills = SalesBill.query.filter(
        SalesBill.customer_id.in_(family_ids),
        SalesBill.is_cancelled.is_(False),
    ).all()
    receipts = ReceiptPayment.query.filter(ReceiptPayment.customer_id.in_(family_ids)).all()
    member_lookup = {
        row.customer_id: row.customer_name
        for row in Customer.query.filter(Customer.customer_id.in_(family_ids)).all()
    }

    events = []
    for bill in bills:
        events.append(
            {
                "date": datetime.combine(bill.bill_date, bill.bill_time),
                "kind": "Sale",
                "ref_id": f"B-{bill.bill_id}",
                "description": f"Bill #B-{bill.bill_id} - {member_lookup.get(bill.customer_id, 'Customer')}",
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
                "description": f"{receipt.remarks or 'Manual Payment'} - {member_lookup.get(receipt.customer_id, 'Customer')}",
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
