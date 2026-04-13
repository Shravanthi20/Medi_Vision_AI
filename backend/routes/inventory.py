from datetime import datetime

from flask import Blueprint, jsonify, request

from ..db import (
    get_conn,
    json_error,
    normalize_medicine_row,
    required_fields,
    shelf_location_label,
)


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/api/medicines", methods=["GET"])
def get_meds():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                m.*,
                sh.name AS shelf_name,
                sh.aisle AS shelf_aisle,
                sh.rack AS shelf_rack,
                sh.shelf AS shelf_slot,
                sh.bin AS shelf_bin,
                sh.notes AS shelf_notes,
                sh.status AS shelf_status
            FROM medicines m
            LEFT JOIN shelf_locations sh
                ON sh.id = CASE
                    WHEN m.shelf_id IS NULL OR m.shelf_id = '' THEN NULL
                    ELSE CAST(m.shelf_id AS INTEGER)
                END
            ORDER BY m.n COLLATE NOCASE ASC
            """
        ).fetchall()
    return jsonify([normalize_medicine_row(row) for row in rows])


@inventory_bp.route("/api/medicines/alerts", methods=["GET"])
def medicine_alerts():
    low_stock_threshold = int(request.args.get("low_stock", 15))
    expiry_days = int(request.args.get("expiry_days", 90))
    now = datetime.now().date()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.n,
                m.s,
                m.expiry,
                m.reorder,
                m.shelf_id,
                sh.name AS shelf_name,
                sh.aisle AS shelf_aisle,
                sh.rack AS shelf_rack,
                sh.shelf AS shelf_slot,
                sh.bin AS shelf_bin
            FROM medicines m
            LEFT JOIN shelf_locations sh
                ON sh.id = CASE
                    WHEN m.shelf_id IS NULL OR m.shelf_id = '' THEN NULL
                    ELSE CAST(m.shelf_id AS INTEGER)
                END
            ORDER BY m.n COLLATE NOCASE ASC
            """
        ).fetchall()

    low_stock: list[dict] = []
    expiring_soon: list[dict] = []
    for row in rows:
        med = dict(row)
        stock = int(med.get("s") or 0)
        reorder_level = int(med.get("reorder") or 0)
        threshold = reorder_level if reorder_level > 0 else low_stock_threshold
        if stock <= threshold:
            med["threshold"] = threshold
            med["shelf_label"] = shelf_location_label(
                {
                    "name": med.get("shelf_name", ""),
                    "aisle": med.get("shelf_aisle", ""),
                    "rack": med.get("shelf_rack", ""),
                    "shelf": med.get("shelf_slot", ""),
                    "bin": med.get("shelf_bin", ""),
                }
            )
            low_stock.append(med)

        expiry_raw = (med.get("expiry") or "").strip()
        if expiry_raw:
            try:
                exp_date = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
                days_left = (exp_date - now).days
                if days_left <= expiry_days:
                    expiring_soon.append(
                        {
                            "id": med.get("id"),
                            "n": med.get("n"),
                            "s": stock,
                            "expiry": expiry_raw,
                            "days_left": days_left,
                            "shelf_label": shelf_location_label(
                                {
                                    "name": med.get("shelf_name", ""),
                                    "aisle": med.get("shelf_aisle", ""),
                                    "rack": med.get("shelf_rack", ""),
                                    "shelf": med.get("shelf_slot", ""),
                                    "bin": med.get("shelf_bin", ""),
                                }
                            ),
                        }
                    )
            except ValueError:
                pass

    return jsonify(
        {
            "low_stock": low_stock,
            "expiring_soon": sorted(expiring_soon, key=lambda x: x["days_left"]),
            "config": {"low_stock": low_stock_threshold, "expiry_days": expiry_days},
        }
    )


@inventory_bp.route("/api/medicines", methods=["POST"])
def update_med():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["id", "n", "p", "s"])
    if missing:
        return json_error("Missing required medicine fields", 400, missing)

    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO medicines
                (id, n, g, c, p, s, batch, expiry, p_rate, p_packing, s_packing, p_gst, s_gst, disc, offer, reorder, max_qty, shelf_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["id"],
                    data["n"],
                    data.get("g", "Generic"),
                    data.get("c", "Tablet"),
                    float(data["p"]),
                    int(data["s"]),
                    data.get("batch", ""),
                    data.get("expiry", ""),
                    float(data.get("p_rate", 0) or 0),
                    data.get("p_packing", ""),
                    data.get("s_packing", ""),
                    float(data.get("p_gst", 0) or 0),
                    float(data.get("s_gst", 0) or 0),
                    float(data.get("disc", 0) or 0),
                    data.get("offer", ""),
                    int(data.get("reorder", 0) or 0),
                    int(data.get("max_qty", 0) or 0),
                    str(data.get("shelf_id", "") or ""),
                ),
            )
        return jsonify({"status": "success"})
    except (ValueError, TypeError) as err:
        return json_error("Invalid medicine payload", 400, str(err))
    except Exception as err:
        return json_error("Failed to save medicine", 500, str(err))


@inventory_bp.route("/api/medicines/<id>", methods=["DELETE"])
def delete_med(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM medicines WHERE id = ?", (id,))
    return jsonify({"status": "success"})


@inventory_bp.route("/api/shelves", methods=["GET"])
def get_shelves():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                sh.*,
                COUNT(m.id) AS medicine_count
            FROM shelf_locations sh
            LEFT JOIN medicines m
                ON CAST(m.shelf_id AS INTEGER) = sh.id
            GROUP BY sh.id
            ORDER BY sh.name COLLATE NOCASE ASC, sh.id ASC
            """
        ).fetchall()
    return jsonify(
        [
            {
                "id": data["id"],
                "name": data["name"],
                "aisle": data["aisle"],
                "rack": data["rack"],
                "shelf": data["shelf"],
                "bin": data["bin"],
                "notes": data["notes"],
                "status": data["status"],
                "medicine_count": data["medicine_count"],
                "label": shelf_location_label(data),
            }
            for data in (dict(row) for row in rows)
        ]
    )


@inventory_bp.route("/api/shelves", methods=["POST"])
def save_shelf():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name"])
    if missing:
        return json_error("Missing required shelf fields", 400, missing)

    try:
        with get_conn() as conn:
            shelf_id = data.get("id")
            if shelf_id:
                conn.execute(
                    """
                    UPDATE shelf_locations
                    SET name = ?, aisle = ?, rack = ?, shelf = ?, bin = ?, notes = ?, status = ?
                    WHERE id = ?
                    """,
                    (
                        data["name"],
                        data.get("aisle", ""),
                        data.get("rack", ""),
                        data.get("shelf", ""),
                        data.get("bin", ""),
                        data.get("notes", ""),
                        data.get("status", "Active"),
                        shelf_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO shelf_locations (name, aisle, rack, shelf, bin, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["name"],
                        data.get("aisle", ""),
                        data.get("rack", ""),
                        data.get("shelf", ""),
                        data.get("bin", ""),
                        data.get("notes", ""),
                        data.get("status", "Active"),
                    ),
                )
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to save shelf location", 500, str(err))


@inventory_bp.route("/api/shelves/<id>", methods=["DELETE"])
def delete_shelf(id):
    try:
        with get_conn() as conn:
            conn.execute("UPDATE medicines SET shelf_id = '' WHERE shelf_id = ?", (str(id),))
            conn.execute("DELETE FROM shelf_locations WHERE id = ?", (id,))
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to delete shelf location", 500, str(err))
