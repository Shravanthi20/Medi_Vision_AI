from datetime import datetime, date

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.core import (
    Item, Location, Manufacturer, ProductCategory, UnitOfMeasure,
    GstSlab, HsnCode, Combination
)
from ..models.inventory import StockBatch, ExpiryAlert

inventory_bp = Blueprint("inventory", __name__)


def _json_error(message, code=400, details=None):
    return jsonify({"error": message, "details": details}), code


def _item_to_compat(item: Item) -> dict:
    """Serialize an Item ORM object to the flat dict the frontend expects."""

    # aggregate stock from all batches
    total_stock = (
        db.session.query(func.coalesce(func.sum(StockBatch.current_qty), 0))
        .filter_by(item_id=item.item_id)
        .scalar()
    )

    # latest batch (by primary key — newest inserted)
    latest = (
        StockBatch.query
        .filter_by(item_id=item.item_id)
        .order_by(StockBatch.stock_batch_id.desc())
        .first()
    )

    # related lookup names
    category = ProductCategory.query.get(item.category_id)
    combination = Combination.query.get(item.combination_id) if item.combination_id else None
    p_gst_slab = GstSlab.query.get(item.purchase_gst_slab_id)
    s_gst_slab = GstSlab.query.get(item.sales_gst_slab_id)

    offer_str = (
        f"Buy {item.offer_buy_qty} Get {item.offer_free_qty} Free"
        if item.offer_buy_qty and item.offer_free_qty
        else ""
    )

    return {
        # --- identity ---
        "id":         item.item_id,
        "n":          item.item_name,
        "g":          combination.combination_name if combination else "Generic",
        "c":          category.category_name if category else "General",
        # --- pricing ---
        "p":          float(item.default_selling_price or 0),
        "p_rate":     float(latest.purchase_rate) if latest else 0,
        # --- stock ---
        "s":          int(total_stock),
        "batch":      latest.batch_no if latest else "",
        "expiry":     str(latest.expiry_date) if latest else "",
        # --- packing ---
        "p_packing":  item.purchase_packing or "",
        "s_packing":  item.sales_packing or "",
        # --- tax ---
        "p_gst":      float(p_gst_slab.slab_rate_pct) if p_gst_slab else 0,
        "s_gst":      float(s_gst_slab.slab_rate_pct) if s_gst_slab else 0,
        # --- misc ---
        "disc":       float(item.default_discount_pct or 0),
        "offer":      offer_str,
        "reorder":    item.reorder_level or 0,
        "max_qty":    item.max_stock or 0,
        "shelf_id":   item.rack_number or "",
        "shelf_name": item.rack_number or "",
        "shelf_label": item.rack_number or "Unassigned",
    }


def _location_to_compat(loc: Location) -> dict:
    """Serialize a Location ORM object to the dict the frontend expects."""
    # Count items that use this location code as their rack_number
    med_count = Item.query.filter_by(rack_number=loc.location_code).count()
    return {
        "id":             loc.location_id,
        "name":           loc.location_name,
        "aisle":          "",
        "rack":           "",
        "shelf":          "",
        "bin":            "",
        "notes":          "",
        "status":         "Active" if loc.is_active else "Inactive",
        "medicine_count": med_count,
        "label":          loc.location_name,
    }


def _get_or_create_defaults():
    """Ensure minimal reference data exists so new items can be saved."""
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

    slab = GstSlab.query.first()
    if not slab:
        slab = GstSlab(
            slab_code="ZERO", slab_rate_pct=0,
            cgst_pct=0, sgst_pct=0, igst_pct=0,
            effective_from=date.today()
        )
        db.session.add(slab)
        db.session.flush()

    hsn = HsnCode.query.first()
    if not hsn:
        hsn = HsnCode(hsn_code="00000000", description="Default", gst_slab_id=slab.gst_slab_id)
        db.session.add(hsn)
        db.session.flush()

    uom = UnitOfMeasure.query.first()
    if not uom:
        uom = UnitOfMeasure(uom_code="NOS", uom_name="Numbers")
        db.session.add(uom)
        db.session.flush()

    db.session.commit()
    return mfg.manufacturer_id, cat.category_id, slab.gst_slab_id, hsn.hsn_id, uom.uom_id



@inventory_bp.route("/api/medicines", methods=["GET"])
def get_meds():
    items = Item.query.order_by(Item.item_name).all()
    return jsonify([_item_to_compat(i) for i in items])


@inventory_bp.route("/api/medicines/alerts", methods=["GET"])
def medicine_alerts():
    low_stock_threshold = int(request.args.get("low_stock", 15))
    expiry_days = int(request.args.get("expiry_days", 90))
    today = date.today()

    items = Item.query.order_by(Item.item_name).all()
    low_stock = []
    expiring_soon = []

    for item in items:
        compat = _item_to_compat(item)
        stock = compat["s"]
        threshold = item.reorder_level if item.reorder_level > 0 else low_stock_threshold
        if stock <= threshold:
            compat["threshold"] = threshold
            low_stock.append(compat)

        expiry_raw = compat.get("expiry", "")
        if expiry_raw:
            try:
                exp_date = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
                days_left = (exp_date - today).days
                if days_left <= expiry_days:
                    expiring_soon.append({
                        "id":          compat["id"],
                        "n":           compat["n"],
                        "s":           stock,
                        "expiry":      expiry_raw,
                        "days_left":   days_left,
                        "shelf_label": compat["shelf_label"],
                    })
            except ValueError:
                pass

    return jsonify({
        "low_stock":     low_stock,
        "expiring_soon": sorted(expiring_soon, key=lambda x: x["days_left"]),
        "config":        {"low_stock": low_stock_threshold, "expiry_days": expiry_days},
    })


@inventory_bp.route("/api/medicines", methods=["POST"])
def update_med():
    data = request.get_json(silent=True) or {}
    # frontend sends: id, n, g, c, p, s, batch, expiry, p_rate, ...
    if not data.get("n"):
        return _json_error("Missing required field: n (item name)", 400)

    try:
        mfg_id, cat_id, slab_id, hsn_id, uom_id = _get_or_create_defaults()

        item_id = data.get("id") or ("m_" + str(int(datetime.utcnow().timestamp() * 1000)))
        item = Item.query.get(item_id)

        if not item:
            item = Item(
                item_id=item_id,
                item_name=data["n"],
                manufacturer_id=mfg_id,
                category_id=cat_id,
                hsn_id=hsn_id,
                uom_id=uom_id,
                purchase_gst_slab_id=slab_id,
                sales_gst_slab_id=slab_id,
            )
            db.session.add(item)

        # update item fields from the flat frontend payload
        item.item_name           = data.get("n", item.item_name)
        item.default_selling_price = float(data.get("p", item.default_selling_price or 0))
        item.default_discount_pct  = float(data.get("disc", item.default_discount_pct or 0))
        item.reorder_level         = int(data.get("reorder", item.reorder_level or 0))
        item.max_stock             = int(data.get("max_qty", item.max_stock or 0))
        item.purchase_packing      = data.get("p_packing", item.purchase_packing or "")
        item.sales_packing         = data.get("s_packing", item.sales_packing or "")
        item.rack_number           = data.get("shelf_id", item.rack_number or "")

        # offer: parse "Buy X Get Y Free" back if present
        offer = data.get("offer", "")
        if offer:
            parts = offer.split()  # ["Buy","2","Get","1","Free"]
            try:
                item.offer_buy_qty  = int(parts[1])
                item.offer_free_qty = int(parts[3])
            except (IndexError, ValueError):
                pass

        db.session.flush()

        # upsert the StockBatch record (one batch per item in legacy flat mode)
        batch_no = data.get("batch", "")
        expiry_str = data.get("expiry", "")
        expiry_date = None
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        existing_batch = (
            StockBatch.query
            .filter_by(item_id=item_id, batch_no=batch_no or "__default__")
            .first()
        )
        new_qty = int(data.get("s", 0))
        location = Location.query.first()
        location_id = location.location_id if location else None

        if not location_id:
            loc = Location(location_code="MAIN", location_name="Main Store")
            db.session.add(loc)
            db.session.flush()
            location_id = loc.location_id

        if existing_batch:
            existing_batch.current_qty = new_qty
            existing_batch.total_stock = new_qty
            if expiry_date:
                existing_batch.expiry_date = expiry_date
            existing_batch.purchase_rate = float(data.get("p_rate", existing_batch.purchase_rate or 0))
            existing_batch.mrp = float(data.get("p", existing_batch.mrp or 0))
        else:
            batch = StockBatch(
                item_id=item_id,
                batch_no=batch_no or "__default__",
                expiry_date=expiry_date or date(2099, 12, 31),
                location_id=location_id,
                manufacturer_id=mfg_id,
                mrp=float(data.get("p", 0)),
                purchase_rate=float(data.get("p_rate", 0)),
                opening_qty=new_qty,
                current_qty=new_qty,
                total_stock=new_qty,
            )
            db.session.add(batch)

        db.session.commit()
        return jsonify({"status": "success"})

    except (ValueError, TypeError) as err:
        db.session.rollback()
        return _json_error("Invalid medicine payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save medicine", 500, str(err))


@inventory_bp.route("/api/medicines/<id>", methods=["DELETE"])
def delete_med(id):
    try:
        item = Item.query.get(id)
        if item:
            # delete child batches first
            StockBatch.query.filter_by(item_id=id).delete()
            db.session.delete(item)
            db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete item", 500, str(err))



@inventory_bp.route("/api/shelves", methods=["GET"])
def get_shelves():
    locations = Location.query.order_by(Location.location_name).all()
    return jsonify([_location_to_compat(loc) for loc in locations])


@inventory_bp.route("/api/shelves", methods=["POST"])
def save_shelf():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return _json_error("Missing required field: name", 400)

    try:
        loc_id = data.get("id")
        if loc_id:
            loc = Location.query.get(loc_id)
            if loc:
                loc.location_name = name
                # generate a code from name if it changed
                loc.location_code = name[:10].upper().replace(" ", "_")
                loc.is_active = (data.get("status", "Active") == "Active")
        else:
            code = name[:10].upper().replace(" ", "_")
            # ensure unique code
            existing = Location.query.filter_by(location_code=code).first()
            if existing:
                code = code[:8] + "_" + str(int(datetime.utcnow().timestamp()))[-2:]
            loc = Location(
                location_name=name,
                location_code=code,
                is_active=(data.get("status", "Active") == "Active"),
            )
            db.session.add(loc)

        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save shelf location", 500, str(err))


@inventory_bp.route("/api/shelves/<int:id>", methods=["DELETE"])
def delete_shelf(id):
    try:
        loc = Location.query.get(id)
        if loc:
            # unassign items using this location
            Item.query.filter_by(rack_number=loc.location_code).update({"rack_number": None})
            db.session.delete(loc)
            db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete shelf location", 500, str(err))
