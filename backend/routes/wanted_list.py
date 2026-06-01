from datetime import date as date_type
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.ai import WantedList
from ..models.core import Customer, Item
from ..models.lookups import WantedStatus
from .auth import role_required

wanted_list_bp = Blueprint("wanted_list", __name__)


def _json_error(message, code=400, details=None):
    return jsonify({"error": message, "details": details}), code


def _get_or_create_default_status():
    """Get or create default 'Active' status for wanted items"""
    status = WantedStatus.query.filter_by(status_name="Active").first()
    if not status:
        status = WantedStatus(status_code="ACTIVE", status_name="Active")
        db.session.add(status)
        db.session.flush()
    return status.wanted_status_id


@wanted_list_bp.route("/api/wanted-list", methods=["GET"])
def get_wanted_list():
    """
    Get all wanted items for a customer.
    Query parameters:
    - customer_id: Customer ID to fetch items for (required)
    - status: Filter by auto_order_status (optional: PENDING, APPROVED, SCRAPING, ORDERED, FAILED)
    """
    customer_id = request.args.get("customer_id")
    status_filter = request.args.get("status")
    
    if not customer_id:
        return _json_error("customer_id is required", 400)
    
    try:
        customer_id = int(customer_id)
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return _json_error("Customer not found", 404)
        
        query = WantedList.query.filter_by(customer_id=customer_id)
        
        if status_filter:
            query = query.filter_by(auto_order_status=status_filter)
        
        wanted_items = query.order_by(WantedList.created_at.desc()).all()
        
        result = []
        for item in wanted_items:
            medicine = db.session.get(Item, item.item_id)
            result.append({
                "wanted_id": item.wanted_id,
                "customer_id": item.customer_id,
                "item_id": item.item_id,
                "item_name": medicine.item_name if medicine else item.item_id,
                "required_qty": item.required_qty,
                "min_qty": item.min_qty,
                "max_qty": item.max_qty,
                "auto_order_status": item.auto_order_status,
                "ml_forecasted_qty": item.ml_forecasted_qty,
                "last_purchase_rate": float(item.last_purchase_rate or 0),
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            })
        
        return jsonify(result)
    
    except ValueError:
        return _json_error("Invalid customer_id", 400)
    except Exception as err:
        return _json_error("Failed to fetch wanted list", 500, str(err))


@wanted_list_bp.route("/api/wanted-list", methods=["POST"])
def create_wanted_item():
    """
    Create a new wanted item for a customer.
    Required fields:
    - customer_id: Customer ID
    - item_id: Medicine ID to add to wanted list
    - required_qty: Quantity required (default: 1)
    
    Optional fields:
    - min_qty, max_qty, supplier_id, manufacturer_id
    """
    data = request.get_json(silent=True) or {}
    
    required = ["customer_id", "item_id"]
    for field in required:
        if field not in data:
            return _json_error(f"Missing required field: {field}", 400)
    
    try:
        customer_id = int(data.get("customer_id"))
        item_id = str(data.get("item_id")).strip()
        
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return _json_error("Customer not found", 404)
        
        item = db.session.get(Item, item_id)
        if not item:
            return _json_error("Item not found", 404)
        
        existing = WantedList.query.filter_by(
            customer_id=customer_id,
            item_id=item_id
        ).first()
        if existing:
            return _json_error("Item already in wanted list", 409)
        
        status_id = _get_or_create_default_status()
        
        wanted = WantedList(
            customer_id=customer_id,
            item_id=item_id,
            required_qty=int(data.get("required_qty", 1)),
            min_qty=int(data.get("min_qty", 1)) if data.get("min_qty") else None,
            max_qty=int(data.get("max_qty")) if data.get("max_qty") else None,
            supplier_id=int(data.get("supplier_id")) if data.get("supplier_id") else None,
            manufacturer_id=int(data.get("manufacturer_id")) if data.get("manufacturer_id") else None,
            w_date=date_type.today(),
            status_id=status_id,
            auto_order_status=data.get("auto_order_status", "PENDING")
        )
        
        db.session.add(wanted)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "wanted_id": wanted.wanted_id,
            "customer_id": wanted.customer_id,
            "item_id": wanted.item_id,
            "item_name": item.item_name,
            "required_qty": wanted.required_qty,
            "auto_order_status": wanted.auto_order_status,
        }), 201
    
    except ValueError as ve:
        return _json_error(f"Invalid data type: {str(ve)}", 400)
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to create wanted item", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/<int:wanted_id>", methods=["GET"])
def get_wanted_item(wanted_id):
    """Get a specific wanted item by ID"""
    try:
        wanted = db.session.get(WantedList, wanted_id)
        if not wanted:
            return _json_error("Wanted item not found", 404)
        
        item = db.session.get(Item, wanted.item_id)
        
        return jsonify({
            "wanted_id": wanted.wanted_id,
            "customer_id": wanted.customer_id,
            "item_id": wanted.item_id,
            "item_name": item.item_name if item else wanted.item_id,
            "required_qty": wanted.required_qty,
            "min_qty": wanted.min_qty,
            "max_qty": wanted.max_qty,
            "auto_order_status": wanted.auto_order_status,
            "ml_forecasted_qty": wanted.ml_forecasted_qty,
            "last_purchase_rate": float(wanted.last_purchase_rate or 0),
            "created_at": wanted.created_at.isoformat(),
            "updated_at": wanted.updated_at.isoformat(),
        })
    
    except Exception as err:
        return _json_error("Failed to fetch wanted item", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/<int:wanted_id>", methods=["PATCH", "PUT"])
def update_wanted_item(wanted_id):
    """
    Update a wanted item.
    Updateable fields: required_qty, min_qty, max_qty, auto_order_status, ml_forecasted_qty, last_purchase_rate
    """
    data = request.get_json(silent=True) or {}
    
    try:
        wanted = db.session.get(WantedList, wanted_id)
        if not wanted:
            return _json_error("Wanted item not found", 404)
        
        if "required_qty" in data:
            wanted.required_qty = int(data["required_qty"])
        
        if "min_qty" in data:
            wanted.min_qty = int(data["min_qty"]) if data["min_qty"] is not None else None
        
        if "max_qty" in data:
            wanted.max_qty = int(data["max_qty"]) if data["max_qty"] is not None else None
        
        if "auto_order_status" in data:
            status_val = str(data["auto_order_status"]).upper()
            valid_statuses = ["PENDING", "APPROVED", "SCRAPING", "ORDERED", "FAILED"]
            if status_val not in valid_statuses:
                return _json_error(f"Invalid status. Must be one of: {', '.join(valid_statuses)}", 400)
            wanted.auto_order_status = status_val
        
        if "ml_forecasted_qty" in data:
            wanted.ml_forecasted_qty = int(data["ml_forecasted_qty"]) if data["ml_forecasted_qty"] is not None else None
        
        if "last_purchase_rate" in data:
            wanted.last_purchase_rate = float(data["last_purchase_rate"]) if data["last_purchase_rate"] is not None else None
        
        db.session.commit()
        
        item = db.session.get(Item, wanted.item_id)
        
        return jsonify({
            "status": "success",
            "wanted_id": wanted.wanted_id,
            "customer_id": wanted.customer_id,
            "item_id": wanted.item_id,
            "item_name": item.item_name if item else wanted.item_id,
            "required_qty": wanted.required_qty,
            "auto_order_status": wanted.auto_order_status,
            "updated_at": wanted.updated_at.isoformat(),
        })
    
    except ValueError as ve:
        return _json_error(f"Invalid data type: {str(ve)}", 400)
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to update wanted item", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/<int:wanted_id>", methods=["DELETE"])
def delete_wanted_item(wanted_id):
    """Delete a wanted item"""
    try:
        wanted = db.session.get(WantedList, wanted_id)
        if not wanted:
            return _json_error("Wanted item not found", 404)
        
        customer_id = wanted.customer_id
        item_id = wanted.item_id
        
        db.session.delete(wanted)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "wanted_id": wanted_id,
            "customer_id": customer_id,
            "item_id": item_id,
            "message": "Wanted item deleted successfully"
        })
    
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete wanted item", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/bulk-status-update", methods=["PATCH"])
def bulk_update_status():
    """
    Bulk update auto_order_status for multiple wanted items.
    Request body:
    {
        "wanted_ids": [1, 2, 3],
        "auto_order_status": "APPROVED"
    }
    """
    data = request.get_json(silent=True) or {}
    wanted_ids = data.get("wanted_ids", [])
    new_status = data.get("auto_order_status")
    
    if not wanted_ids or not new_status:
        return _json_error("Missing wanted_ids or auto_order_status", 400)
    
    try:
        valid_statuses = ["PENDING", "APPROVED", "SCRAPING", "ORDERED", "FAILED"]
        if new_status.upper() not in valid_statuses:
            return _json_error(f"Invalid status. Must be one of: {', '.join(valid_statuses)}", 400)
        
        updated_count = db.session.query(WantedList).filter(
            WantedList.wanted_id.in_(wanted_ids)
        ).update({WantedList.auto_order_status: new_status.upper()}, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "updated_count": updated_count,
            "auto_order_status": new_status.upper()
        })
    
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to update items", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/<int:wanted_id>/approve", methods=["POST"])
@role_required("admin")
def approve_wanted_item(wanted_id):
    """Approve a wanted item. Requires admin role."""
    try:
        wanted = db.session.get(WantedList, wanted_id)
        if not wanted:
            return _json_error("Wanted item not found", 404)

        if wanted.auto_order_status != "PENDING":
            return _json_error("Only PENDING items can be approved", 400)

        wanted.auto_order_status = "APPROVED"
        db.session.commit()

        item = db.session.get(Item, wanted.item_id)
        return jsonify({
            "status": "success",
            "wanted_id": wanted.wanted_id,
            "auto_order_status": wanted.auto_order_status,
            "item_name": item.item_name if item else wanted.item_id,
        })
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to approve wanted item", 500, str(err))


@wanted_list_bp.route("/api/wanted-list/<int:wanted_id>/mark-ordered", methods=["POST"])
@role_required("admin")
def mark_wanted_ordered(wanted_id):
    """Mark a wanted item as ORDERED or FAILED. Accepts JSON: {"result":"ORDERED","order_ref":"REF123","error":"..."} """
    data = request.get_json(silent=True) or {}
    result = str(data.get("result", "ORDERED")).upper()
    order_ref = data.get("order_ref")
    error_msg = data.get("error")

    try:
        wanted = db.session.get(WantedList, wanted_id)
        if not wanted:
            return _json_error("Wanted item not found", 404)

        if result not in ("ORDERED", "FAILED"):
            return _json_error("Invalid result, must be ORDERED or FAILED", 400)

        wanted.auto_order_status = result
        db.session.commit()

        return jsonify({"status": "success", "wanted_id": wanted.wanted_id, "auto_order_status": wanted.auto_order_status, "order_ref": order_ref or None, "error": error_msg or None})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to update order status", 500, str(err))
