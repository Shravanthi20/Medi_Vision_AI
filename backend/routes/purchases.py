from datetime import datetime, date as date_type

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.purchase import PurchaseInvoice, PurchaseInvoiceItem
from ..models.core import (
    Supplier,
    Item,
    Location,
    FinancialYear,
    GstSlab,
    Manufacturer,
    ProductCategory,
    UnitOfMeasure,
    HsnCode,
)
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


def _get_or_create_item_defaults(gst_slab_id: int):
    """Ensure minimal lookup rows exist so we can auto-create Item records."""
    mfg = Manufacturer.query.first()
    if not mfg:
        mfg = Manufacturer(manufacturer_code="SYS", manufacturer_name="System Default")
        db.session.add(mfg)
        db.session.flush()

    cat = ProductCategory.query.first()
    if not cat:
        cat = ProductCategory(category_name="General")
        db.session.add(cat)
        db.session.flush()

    hsn = HsnCode.query.first()
    if not hsn:
        hsn = HsnCode(
            hsn_code="00000000",
            description="Default",
            gst_slab_id=gst_slab_id,
        )
        db.session.add(hsn)
        db.session.flush()

    uom = UnitOfMeasure.query.first()
    if not uom:
        uom = UnitOfMeasure(uom_code="NOS", uom_name="Numbers")
        db.session.add(uom)
        db.session.flush()

    return mfg.manufacturer_id, cat.category_id, hsn.hsn_id, uom.uom_id


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


def _next_item_id() -> str:
    """Generate a unique Item.item_id that fits the String(10) schema."""
    base = int(datetime.utcnow().timestamp() * 1000) % 100000000
    candidate = f"M{base:08d}"
    while Item.query.get(candidate):
        base = (base + 1) % 100000000
        candidate = f"M{base:08d}"
    return candidate


def _next_purchase_item_id() -> int:
    """Generate a PK value for PurchaseInvoiceItem on DBs without autoincrement for BigInteger PK."""
    max_id = db.session.query(func.coalesce(func.max(PurchaseInvoiceItem.purchase_item_id), 0)).scalar()
    return int(max_id or 0) + 1


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
        mfg_id, cat_id, hsn_id, uom_id = _get_or_create_item_defaults(gst_slab_id)

        supplier = _get_or_create_supplier(supplier_name)

        line_items = data.get("line_items") if isinstance(data.get("line_items"), list) else []

        def _line_amount(line):
            qty = int(line.get("qty", 0) or 0)
            qty = max(0, qty)
            unit_price = float(line.get("unit_price", 0) or 0)
            basis = str(line.get("pricing_basis", "per_unit") or "per_unit")
            explicit = float(line.get("amount", 0) or 0)
            if explicit > 0:
                return explicit
            return unit_price if basis == "lot_total" else (qty * unit_price)

        amount = float(data.get("amount", 0) or 0)
        if amount <= 0 and line_items:
            amount = sum(_line_amount(li) for li in line_items)

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

        # Preferred path: process structured purchase line items and update stock.
        if line_items:
            next_purchase_item_id = _next_purchase_item_id()
            processed_lines = 0
            for idx, line in enumerate(line_items):
                name = str(line.get("name", "") or "").strip()
                qty = max(0, int(line.get("qty", 0) or 0))
                if not name or qty <= 0:
                    continue
                processed_lines += 1

                unit_price = float(line.get("unit_price", 0) or 0)
                basis = str(line.get("pricing_basis", "per_unit") or "per_unit")
                line_amount = float(_line_amount(line))
                effective_rate = unit_price
                if basis == "lot_total" and qty > 0:
                    effective_rate = line_amount / qty

                matched_item = Item.query.filter(
                    func.lower(Item.item_name) == name.lower()
                ).first()
                if not matched_item:
                    matched_item = Item(
                        item_id=_next_item_id(),
                        item_name=name,
                        manufacturer_id=mfg_id,
                        category_id=cat_id,
                        hsn_id=hsn_id,
                        uom_id=uom_id,
                        purchase_gst_slab_id=gst_slab_id,
                        sales_gst_slab_id=gst_slab_id,
                        default_mrp=effective_rate if effective_rate > 0 else 0,
                        default_selling_price=effective_rate if effective_rate > 0 else 0,
                    )
                    db.session.add(matched_item)
                    db.session.flush()
                elif effective_rate > 0:
                    matched_item.default_selling_price = effective_rate
                    matched_item.default_mrp = effective_rate

                batch_no = str(line.get("batch", "") or "").strip() or "__default__"
                expiry_str = str(line.get("expiry", "") or "").strip()
                expiry_date = date_type(2099, 12, 31)
                if expiry_str:
                    try:
                        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                batch = StockBatch.query.filter_by(
                    item_id=matched_item.item_id,
                    batch_no=batch_no,
                    location_id=loc_id,
                ).first()
                if not batch:
                    batch = StockBatch(
                        item_id=matched_item.item_id,
                        batch_no=batch_no,
                        expiry_date=expiry_date,
                        location_id=loc_id,
                        manufacturer_id=matched_item.manufacturer_id,
                        mrp=float(matched_item.default_mrp or 0),
                        purchase_rate=float(effective_rate or matched_item.default_selling_price or 0),
                        opening_qty=0,
                        current_qty=0,
                        total_stock=0,
                    )
                    db.session.add(batch)
                    db.session.flush()

                batch.current_qty = int(batch.current_qty or 0) + qty
                batch.total_stock = int(batch.total_stock or 0) + qty
                if effective_rate > 0:
                    batch.purchase_rate = effective_rate
                    batch.mrp = effective_rate
                if expiry_str:
                    batch.expiry_date = expiry_date

                li = PurchaseInvoiceItem(
                    purchase_item_id=next_purchase_item_id,
                    purchase_id=purchase.purchase_id,
                    item_id=matched_item.item_id,
                    stock_batch_id=batch.stock_batch_id,
                    pkg_qty=qty,
                    purchase_rate_at_purchase=float(effective_rate or matched_item.default_selling_price or 0),
                    mrp_at_purchase=float(matched_item.default_mrp or effective_rate or 0),
                    net_rate=float(effective_rate or matched_item.default_selling_price or 0),
                    stax_pct=0,
                    gst_slab_id=gst_slab_id,
                    cgst_pct=0,
                    sgst_pct=0,
                    igst_pct=0,
                    gst_amount=0,
                    value=float(line_amount if line_amount > 0 else (effective_rate * qty)),
                )
                db.session.add(li)
                next_purchase_item_id += 1

            if processed_lines == 0:
                db.session.rollback()
                return _json_error("No valid purchase line items provided", 400)

            db.session.commit()
            return jsonify({"status": "success"})

        # Backward compatibility path: legacy comma-separated items string.
        items_str = str(data.get("items", ""))
        batch_no  = str(data.get("batch", "")).strip()
        expiry_str = str(data.get("expiry", "")).strip()

        if items_str:
            next_purchase_item_id = _next_purchase_item_id()
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
                    purchase_item_id=next_purchase_item_id,
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
                next_purchase_item_id += 1

        db.session.commit()
        return jsonify({"status": "success"})

    except (ValueError, TypeError) as err:
        db.session.rollback()
        return _json_error("Invalid purchase payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save purchase", 500, str(err))
