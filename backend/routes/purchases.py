from datetime import datetime, date as date_type

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.purchase import PurchaseInvoice, PurchaseInvoiceItem
from ..models.core import Supplier, Item, Location, FinancialYear, GstSlab
from ..models.inventory import StockBatch
from ..models.lookups import PurchaseType

purchases_bp = Blueprint("purchases", __name__)


def _json_error(message, code=400, details=None):
    return jsonify({"error": message, "details": details}), code


def _get_or_create_purchase_defaults():
    """Ensure required FK stubs exist for a PurchaseInvoice."""
    from ..models.core import User

    fy = FinancialYear.query.filter_by(is_active=True).first()
    if not fy:
        today = date_type.today()
        fy = FinancialYear(
            fy_label=f"{today.year}-{str(today.year+1)[-2:]}",
            start_date=date_type(today.year, 4, 1),
            end_date=date_type(today.year + 1, 3, 31),
            is_active=True,
        )
        db.session.add(fy)
        db.session.flush()

    location = Location.query.first()
    if not location:
        location = Location(location_code="MAIN", location_name="Main Store")
        db.session.add(location)
        db.session.flush()

    pt = PurchaseType.query.first()
    if not pt:
        pt = PurchaseType(purchase_type_code="LOC", purchase_type_name="Local Purchase")
        db.session.add(pt)
        db.session.flush()

    user = User.query.first()
    if not user:
        import uuid, hashlib
        from ..models.core import Role
        role = Role.query.first()
        if not role:
            role = Role(role_name="Admin")
            db.session.add(role)
            db.session.flush()
        user = User(
            user_id=uuid.uuid4(),
            username="admin",
            password_hash=hashlib.sha256(b"admin").hexdigest(),
            role_id=role.role_id,
            is_super_admin=True,
        )
        db.session.add(user)
        db.session.flush()

    gst_slab = GstSlab.query.first()
    if not gst_slab:
        gst_slab = GstSlab(
            slab_code="ZERO", slab_rate_pct=0,
            cgst_pct=0, sgst_pct=0, igst_pct=0,
            effective_from=date_type.today()
        )
        db.session.add(gst_slab)
        db.session.flush()

    db.session.commit()
    return fy.financial_year_id, location.location_id, pt.purchase_type_id, user.user_id, gst_slab.gst_slab_id


def _purchase_to_compat(purchase: PurchaseInvoice) -> dict:
    """Serialize a PurchaseInvoice to the flat dict the frontend expects."""
    supplier = Supplier.query.get(purchase.supplier_id)

    # Collect item names from line items
    item_names = []
    batch_no = ""
    expiry_str = ""
    for li in purchase.line_items:
        item = Item.query.get(li.item_id)
        if item:
            item_names.append(item.item_name)
        batch = StockBatch.query.get(li.stock_batch_id) if li.stock_batch_id else None
        if batch:
            batch_no   = batch.batch_no
            expiry_str = str(batch.expiry_date)

    # status: map from model state to legacy strings
    status = "Received"  # default — if it's in the DB it's received

    return {
        "id":       f"P-{purchase.purchase_id}",
        "supplier": supplier.supplier_name if supplier else "Unknown",
        "items":    ", ".join(item_names) or "—",
        "amount":   float(purchase.net_amount),
        "date":     str(purchase.invoice_date or purchase.created_at.date()),
        "status":   status,
        "batch":    batch_no,
        "expiry":   expiry_str,
        "photo":    "",
    }


def _get_or_create_supplier(name: str) -> Supplier:
    """Find supplier by name (case-insensitive) or create a stub."""
    supplier = Supplier.query.filter(
        func.lower(Supplier.supplier_name) == name.strip().lower()
    ).first()
    if not supplier:
        # auto-generate a unique supplier code from the name
        code = name.strip()[:15].upper().replace(" ", "_")
        existing_code = Supplier.query.filter_by(supplier_code=code).first()
        if existing_code:
            code = code[:12] + "_" + str(int(datetime.utcnow().timestamp()))[-3:]
        supplier = Supplier(
            supplier_code=code,
            supplier_name=name.strip(),
        )
        db.session.add(supplier)
        db.session.flush()
    return supplier


@purchases_bp.route("/api/purchases", methods=["GET"])
def get_purchases():
    purchases = PurchaseInvoice.query.order_by(PurchaseInvoice.purchase_id.desc()).all()
    return jsonify([_purchase_to_compat(p) for p in purchases])


@purchases_bp.route("/api/purchases", methods=["POST"])
def add_purchase():
    data = request.get_json(silent=True) or {}

    supplier_name = str(data.get("supplier", "")).strip()
    if not supplier_name:
        return _json_error("Missing required field: supplier", 400)

    try:
        fy_id, loc_id, pt_id, user_id, gst_slab_id = _get_or_create_purchase_defaults()

        supplier = _get_or_create_supplier(supplier_name)

        amount = float(data.get("amount", 0))
        inv_date_str = data.get("date", "")
        try:
            inv_date = datetime.strptime(inv_date_str, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            inv_date = date_type.today()

        # Parse a ref_no from the legacy id (e.g. "PO-001"), or generate one
        legacy_id = str(data.get("id", "")).strip()
        ref_no = legacy_id or f"PO-{int(datetime.utcnow().timestamp())}"

        # Check if this purchase already exists (for INSERT OR REPLACE behaviour)
        existing = None
        if legacy_id.startswith("P-"):
            real_id = legacy_id.replace("P-", "").strip()
            existing = PurchaseInvoice.query.get(real_id)

        if existing:
            # Update status / photo only (the frontend uses PATCH-like POST)
            # Nothing critical to update in new schema from status alone
            db.session.commit()
            return jsonify({"status": "success"})

        purchase = PurchaseInvoice(
            ref_no=ref_no,
            financial_year_id=fy_id,
            supplier_id=supplier.supplier_id,
            location_id=loc_id,
            invoice_no=data.get("id", ""),
            invoice_date=inv_date,
            ac_date=inv_date,
            purchase_type_id=pt_id,
            gross_amount=amount,
            discount_amount=0,
            taxable_amount=amount,
            cgst_amount=0,
            sgst_amount=0,
            igst_amount=0,
            round_off=0,
            net_amount=amount,
            ac_amount=amount,
            user_id=user_id,
            remarks=data.get("status", ""),
        )
        db.session.add(purchase)
        db.session.flush()

        # If items string is given, try to match item names and create line items
        items_str = str(data.get("items", ""))
        batch_no  = str(data.get("batch", "")).strip()
        expiry_str = str(data.get("expiry", "")).strip()

        if items_str:
            item_names = [n.strip() for n in items_str.split(",") if n.strip()]
            for iname in item_names:
                matched_item = Item.query.filter(
                    func.lower(Item.item_name) == iname.lower()
                ).first()
                if not matched_item:
                    continue

                # find or create a batch
                batch = None
                if batch_no:
                    expiry_date = None
                    if expiry_str:
                        try:
                            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                        except ValueError:
                            expiry_date = date_type(2099, 12, 31)
                    batch = StockBatch.query.filter_by(
                        item_id=matched_item.item_id, batch_no=batch_no
                    ).first()
                    if not batch:
                        batch = StockBatch(
                            item_id=matched_item.item_id,
                            batch_no=batch_no,
                            expiry_date=expiry_date or date_type(2099, 12, 31),
                            location_id=loc_id,
                            manufacturer_id=matched_item.manufacturer_id,
                            mrp=float(matched_item.default_mrp or 0),
                            purchase_rate=float(matched_item.default_selling_price or 0),
                            opening_qty=0,
                            current_qty=0,
                            total_stock=0,
                        )
                        db.session.add(batch)
                        db.session.flush()

                li = PurchaseInvoiceItem(
                    purchase_id=purchase.purchase_id,
                    item_id=matched_item.item_id,
                    stock_batch_id=batch.stock_batch_id if batch else None,
                    pkg_qty=1,
                    purchase_rate_at_purchase=float(matched_item.default_selling_price or 0),
                    mrp_at_purchase=float(matched_item.default_mrp or 0),
                    net_rate=float(matched_item.default_selling_price or 0),
                    stax_pct=0,
                    gst_slab_id=gst_slab_id,
                    cgst_pct=0,
                    sgst_pct=0,
                    igst_pct=0,
                    gst_amount=0,
                    value=float(matched_item.default_selling_price or 0),
                )
                db.session.add(li)

        db.session.commit()
        return jsonify({"status": "success"})

    except (ValueError, TypeError) as err:
        db.session.rollback()
        return _json_error("Invalid purchase payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save purchase", 500, str(err))
