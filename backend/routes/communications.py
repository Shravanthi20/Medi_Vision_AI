import sqlite3
from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, required_fields

communications_bp = Blueprint("communications", __name__)

# --- TEMPLATES CRUD ---

@communications_bp.route("/api/communications/templates", methods=["GET"])
def get_templates():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM message_templates ORDER BY id DESC").fetchall()
    return jsonify([dict(row) for row in rows])

@communications_bp.route("/api/communications/templates", methods=["POST"])
def add_template():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "content"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    
    try:
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO message_templates (name, content, is_active)
                VALUES (?, ?, ?)
                """,
                (data["name"], data["content"], int(data.get("is_active", 1)))
            )
            template_id = cursor.lastrowid
            
        return jsonify({"status": "success", "id": template_id})
    except Exception as err:
        return json_error("Failed to save template", 500, str(err))

@communications_bp.route("/api/communications/templates/<int:id>", methods=["PUT"])
def update_template(id):
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "content"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    
    try:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE message_templates
                SET name = ?, content = ?, is_active = ?
                WHERE id = ?
                """,
                (data["name"], data["content"], int(data.get("is_active", 1)), id)
            )
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to update template", 500, str(err))

@communications_bp.route("/api/communications/templates/<int:id>", methods=["DELETE"])
def delete_template(id):
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM message_templates WHERE id = ?", (id,))
        return jsonify({"status": "success"})
    except Exception as err:
        return json_error("Failed to delete template", 500, str(err))

# --- LOGS CRUD ---

@communications_bp.route("/api/communications/logs", methods=["GET"])
def get_logs():
    bill_id = request.args.get("bill_id")
    status = request.args.get("status")
    
    query = "SELECT * FROM communication_logs"
    params = []
    conditions = []
    
    if bill_id:
        conditions.append("bill_id = ?")
        params.append(bill_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY id DESC"
    
    try:
        with get_conn() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as err:
        return json_error("Failed to retrieve communication logs", 500, str(err))
