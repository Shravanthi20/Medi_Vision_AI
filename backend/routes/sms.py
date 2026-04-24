from flask import Blueprint, jsonify, request

from ..db import get_conn, json_error, required_fields
from ..sms_service import (
    create_sms_message,
    dispatch_sms_message,
    list_sms_messages,
    list_sms_templates,
    now_ts,
    retry_sms_message,
    seed_sms_templates,
    safe_text,
)


sms_bp = Blueprint("sms", __name__)


def _boolish(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


@sms_bp.route("/api/sms/messages", methods=["GET"])
def get_sms_messages():
    filters = {
        "customer_id": request.args.get("customer_id", ""),
        "bill_id": request.args.get("bill_id", ""),
        "phone": request.args.get("phone", ""),
    }
    with get_conn() as conn:
        messages = list_sms_messages(conn, filters)
    return jsonify(messages)


@sms_bp.route("/api/sms/messages/by-customer/<customer_id>", methods=["GET"])
def get_sms_messages_by_customer(customer_id):
    with get_conn() as conn:
        messages = list_sms_messages(conn, {"customer_id": customer_id})
    return jsonify(messages)


@sms_bp.route("/api/sms/messages/by-bill/<bill_id>", methods=["GET"])
def get_sms_messages_by_bill(bill_id):
    with get_conn() as conn:
        messages = list_sms_messages(conn, {"bill_id": bill_id})
    return jsonify(messages)


@sms_bp.route("/api/sms/messages", methods=["POST"])
def create_sms():
    data = request.get_json(silent=True) or {}
    phone = safe_text(data.get("recipient_phone") or data.get("phone"))
    if not phone:
        return json_error("Recipient phone is required", 400)
    if not safe_text(data.get("body")) and not safe_text(data.get("template_id")):
        return json_error("Message body or template is required", 400)
    try:
        with get_conn() as conn:
            seed_sms_templates(conn)
            created = create_sms_message(conn, data, auto_send=_boolish(data.get("auto_send"), True))
        return jsonify(created), 201
    except ValueError as err:
        return json_error("Failed to create SMS message", 400, str(err))
    except Exception as err:
        return json_error("Failed to create SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>", methods=["PATCH"])
def update_sms_message(message_id):
    data = request.get_json(silent=True) or {}
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
            if not row:
                return json_error("SMS message not found", 404)
            updates = []
            values = []
            allowed = [
                "recipient_phone",
                "customer_id",
                "customer_name",
                "bill_id",
                "template_id",
                "message_type",
                "body",
                "send_status",
                "provider_name",
                "provider_message_id",
                "provider_response",
                "failure_reason",
                "retry_count",
                "last_attempt_ts",
                "sent_ts",
                "delivered_ts",
                "source",
            ]
            for field in allowed:
                if field not in data:
                    continue
                value = data[field]
                if field == "provider_response" and not isinstance(value, str):
                    import json

                    value = json.dumps(value, ensure_ascii=False)
                updates.append(f"{field} = ?")
                values.append(value)
            if not updates:
                return jsonify(dict(row))
            updates.append("updated_ts = ?")
            values.append(now_ts())
            values.append(message_id)
            conn.execute(f"UPDATE sms_messages SET {', '.join(updates)} WHERE id = ?", tuple(values))
            updated = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
        return jsonify(dict(updated)), 200
    except Exception as err:
        return json_error("Failed to update SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>/retry", methods=["POST"])
def retry_sms(message_id):
    try:
        with get_conn() as conn:
            retried = retry_sms_message(conn, message_id)
        return jsonify(retried)
    except ValueError as err:
        return json_error("Failed to retry SMS message", 404, str(err))
    except Exception as err:
        return json_error("Failed to retry SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>/send", methods=["POST"])
def send_sms(message_id):
    try:
        with get_conn() as conn:
            sent = dispatch_sms_message(conn, message_id)
        return jsonify(sent)
    except ValueError as err:
        return json_error("Failed to send SMS message", 404, str(err))
    except Exception as err:
        return json_error("Failed to send SMS message", 500, str(err))


@sms_bp.route("/api/sms/templates", methods=["GET"])
def get_sms_templates():
    with get_conn() as conn:
        seed_sms_templates(conn)
        templates = list_sms_templates(conn)
    return jsonify(templates)


@sms_bp.route("/api/sms/templates", methods=["POST"])
def create_sms_template():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "body"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    try:
        with get_conn() as conn:
            seed_sms_templates(conn)
            template_id = safe_text(data.get("id")) or f"tpl-{now_ts()}"
            ts = now_ts()
            conn.execute(
                """
                INSERT OR REPLACE INTO sms_templates
                (id, name, body, message_type, active, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template_id,
                    data["name"],
                    data["body"],
                    data.get("message_type", "custom"),
                    1 if _boolish(data.get("active"), True) else 0,
                    int(data.get("created_ts") or ts),
                    ts,
                ),
            )
            row = conn.execute("SELECT * FROM sms_templates WHERE id = ?", (template_id,)).fetchone()
        return jsonify(dict(row)), 201
    except Exception as err:
        return json_error("Failed to create SMS template", 500, str(err))


@sms_bp.route("/api/sms/templates/<template_id>", methods=["PATCH"])
def update_sms_template(template_id):
    data = request.get_json(silent=True) or {}
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM sms_templates WHERE id = ?", (template_id,)).fetchone()
            if not row:
                return json_error("SMS template not found", 404)
            updates = []
            values = []
            allowed = ["name", "body", "message_type", "active"]
            for field in allowed:
                if field not in data:
                    continue
                value = data[field]
                if field == "active":
                    value = 1 if _boolish(value, True) else 0
                updates.append(f"{field} = ?")
                values.append(value)
            if not updates:
                return jsonify(dict(row))
            updates.append("updated_ts = ?")
            values.append(now_ts())
            values.append(template_id)
            conn.execute(f"UPDATE sms_templates SET {', '.join(updates)} WHERE id = ?", tuple(values))
            updated = conn.execute("SELECT * FROM sms_templates WHERE id = ?", (template_id,)).fetchone()
        return jsonify(dict(updated))
    except Exception as err:
        return json_error("Failed to update SMS template", 500, str(err))


@sms_bp.route("/api/sms/templates/<template_id>", methods=["DELETE"])
def delete_sms_template(template_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM sms_templates WHERE id = ?", (template_id,))
    return jsonify({"status": "success"})
