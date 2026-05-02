import json
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.system import SmsLog, SystemSetting

communications_bp = Blueprint("communications", __name__)


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


def _template_key(template_id: int) -> str:
    return f"COMM_TEMPLATE_{template_id}"


def _template_id_from_key(key: str) -> int:
    return int(key.replace("COMM_TEMPLATE_", ""))


def _template_row(setting: SystemSetting) -> dict:
    content = ""
    name = ""
    is_active = 1
    if setting.setting_value:
        try:
            payload = json.loads(setting.setting_value)
            if isinstance(payload, dict):
                content = str(payload.get("content", ""))
                name = str(payload.get("name", ""))
                is_active = int(payload.get("is_active", 1) or 0)
            else:
                content = setting.setting_value
        except Exception:
            content = setting.setting_value

    template_id = _template_id_from_key(setting.setting_key)
    return {
        "id": template_id,
        "name": name,
        "content": content,
        "is_active": is_active,
    }


@communications_bp.route("/api/communications/templates", methods=["GET"])
def get_templates():
    rows = SystemSetting.query.filter(SystemSetting.setting_key.like("COMM_TEMPLATE_%")).all()
    templates = [_template_row(row) for row in rows]
    templates.sort(key=lambda t: t["id"], reverse=True)
    return jsonify(templates)

@communications_bp.route("/api/communications/templates", methods=["POST"])
def add_template():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "content"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    
    try:
        existing_ids = []
        for row in SystemSetting.query.filter(SystemSetting.setting_key.like("COMM_TEMPLATE_%")).all():
            try:
                existing_ids.append(_template_id_from_key(row.setting_key))
            except Exception:
                continue
        template_id = (max(existing_ids) + 1) if existing_ids else 1

        setting = SystemSetting(
            setting_key=_template_key(template_id),
            setting_value=json.dumps(
                {
                    "name": data["name"],
                    "content": data["content"],
                    "is_active": int(data.get("is_active", 1)),
                }
            ),
            description="Communication template",
        )
        db.session.add(setting)
        db.session.commit()

        return jsonify({"status": "success", "id": template_id})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to save template", 500, str(err))

@communications_bp.route("/api/communications/templates/<int:id>", methods=["PUT"])
def update_template(id):
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "content"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    
    try:
        setting = SystemSetting.query.get(_template_key(id))
        if not setting:
            return json_error("Template not found", 404)
        setting.setting_value = json.dumps(
            {
                "name": data["name"],
                "content": data["content"],
                "is_active": int(data.get("is_active", 1)),
            }
        )
        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to update template", 500, str(err))

@communications_bp.route("/api/communications/templates/<int:id>", methods=["DELETE"])
def delete_template(id):
    try:
        setting = SystemSetting.query.get(_template_key(id))
        if setting:
            db.session.delete(setting)
            db.session.commit()
        return jsonify({"status": "success"})
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to delete template", 500, str(err))


@communications_bp.route("/api/communications/logs", methods=["GET"])
def get_logs():
    bill_id = request.args.get("bill_id")
    status = request.args.get("status")

    try:
        query = SmsLog.query
        if bill_id:
            query = query.filter(SmsLog.ref_type == "bill", SmsLog.ref_id == int(bill_id))
        if status:
            query = query.filter(func.lower(SmsLog.status) == status.lower())

        rows = query.order_by(SmsLog.sms_id.desc()).all()
        return jsonify(
            [
                {
                    "id": row.sms_id,
                    "bill_id": str(row.ref_id or ""),
                    "customer_phone": row.recipient_phone,
                    "status": row.status,
                    "message": row.message,
                    "timestamp": row.created_at.isoformat() + "Z",
                    "provider_message_id": "",
                }
                for row in rows
            ]
        )
    except Exception as err:
        return json_error("Failed to retrieve communication logs", 500, str(err))
