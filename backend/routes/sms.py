import json
import time
import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.system import SmsLog, SystemSetting
from ..sms_service import DEFAULT_SMS_TEMPLATES, format_sms_body, send_sms_via_provider


sms_bp = Blueprint("sms", __name__)


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


def now_ts() -> int:
    return int(time.time() * 1000)


def safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tpl_key(template_id: str) -> str:
    return f"SMS_TEMPLATE_{template_id}"


def _msg_key(message_id: str) -> str:
    return f"SMS_MESSAGE_{message_id}"


def _template_to_row(setting: SystemSetting) -> dict:
    template_id = setting.setting_key.replace("SMS_TEMPLATE_", "")
    try:
        payload = json.loads(setting.setting_value)
    except Exception:
        payload = {}
    return {
        "id": template_id,
        "name": safe_text(payload.get("name")),
        "body": safe_text(payload.get("body")),
        "message_type": safe_text(payload.get("message_type") or "custom"),
        "active": 1 if bool(payload.get("active", True)) else 0,
        "created_ts": int(payload.get("created_ts") or now_ts()),
        "updated_ts": int(payload.get("updated_ts") or now_ts()),
    }


def _message_to_row(setting: SystemSetting) -> dict:
    message_id = setting.setting_key.replace("SMS_MESSAGE_", "")
    try:
        payload = json.loads(setting.setting_value)
    except Exception:
        payload = {}

    provider_response = payload.get("provider_response", {})
    if not isinstance(provider_response, dict):
        provider_response = {"raw": provider_response}

    return {
        "id": message_id,
        "created_ts": int(payload.get("created_ts") or now_ts()),
        "updated_ts": int(payload.get("updated_ts") or now_ts()),
        "recipient_phone": safe_text(payload.get("recipient_phone")),
        "customer_id": safe_text(payload.get("customer_id")),
        "customer_name": safe_text(payload.get("customer_name")),
        "bill_id": safe_text(payload.get("bill_id")),
        "template_id": safe_text(payload.get("template_id")),
        "message_type": safe_text(payload.get("message_type") or "custom"),
        "body": safe_text(payload.get("body")),
        "send_status": safe_text(payload.get("send_status") or "queued"),
        "provider_name": safe_text(payload.get("provider_name")),
        "provider_message_id": safe_text(payload.get("provider_message_id")),
        "failure_reason": safe_text(payload.get("failure_reason")),
        "retry_count": int(payload.get("retry_count") or 0),
        "last_attempt_ts": int(payload.get("last_attempt_ts") or 0),
        "sent_ts": int(payload.get("sent_ts") or 0),
        "delivered_ts": int(payload.get("delivered_ts") or 0),
        "source": safe_text(payload.get("source") or "manual"),
        "provider_response": provider_response,
    }


def _load_template(template_id: str) -> dict | None:
    setting = SystemSetting.query.get(_tpl_key(template_id))
    return _template_to_row(setting) if setting else None


def _load_message(message_id: str) -> dict | None:
    setting = SystemSetting.query.get(_msg_key(message_id))
    return _message_to_row(setting) if setting else None


def _save_template(payload: dict) -> dict:
    template_id = safe_text(payload.get("id")) or f"tpl-{now_ts()}"
    ts = now_ts()
    current = _load_template(template_id)
    merged = {
        "id": template_id,
        "name": safe_text(payload.get("name") or (current or {}).get("name")),
        "body": safe_text(payload.get("body") or (current or {}).get("body")),
        "message_type": safe_text(payload.get("message_type") or (current or {}).get("message_type") or "custom"),
        "active": bool(payload.get("active", (current or {}).get("active", 1))),
        "created_ts": int((current or {}).get("created_ts") or ts),
        "updated_ts": ts,
    }

    setting = SystemSetting.query.get(_tpl_key(template_id))
    if not setting:
        setting = SystemSetting(setting_key=_tpl_key(template_id), description="SMS template")
        db.session.add(setting)
    setting.setting_value = json.dumps(merged)
    db.session.flush()

    return _template_to_row(setting)


def _save_message(payload: dict) -> dict:
    message_id = safe_text(payload.get("id")) or f"sms-{uuid.uuid4().hex[:12]}"
    ts = now_ts()
    current = _load_message(message_id)
    merged = dict(current or {})
    merged.update(payload)
    merged["id"] = message_id
    merged["updated_ts"] = ts
    merged["created_ts"] = int((current or {}).get("created_ts") or payload.get("created_ts") or ts)

    setting = SystemSetting.query.get(_msg_key(message_id))
    if not setting:
        setting = SystemSetting(setting_key=_msg_key(message_id), description="SMS message")
        db.session.add(setting)
    setting.setting_value = json.dumps(merged)
    db.session.flush()

    return _message_to_row(setting)


def _seed_templates() -> None:
    existing = SystemSetting.query.filter(SystemSetting.setting_key.like("SMS_TEMPLATE_%")).count()
    if existing:
        return
    for tpl in DEFAULT_SMS_TEMPLATES:
        _save_template(
            {
                "id": tpl["id"],
                "name": tpl["name"],
                "body": tpl["body"],
                "message_type": tpl.get("message_type", "custom"),
                "active": True,
            }
        )
    db.session.commit()


def _dispatch(message: dict) -> dict:
    result = send_sms_via_provider(message)
    sent_status = "sent" if result.ok else ("queued" if result.status == "queued" else "failed")
    delivered_ts = int(result.delivered_ts or 0)
    updated = _save_message(
        {
            "id": message["id"],
            "send_status": sent_status,
            "provider_name": safe_text(result.provider_name),
            "provider_message_id": safe_text(result.message_id),
            "provider_response": result.response if isinstance(result.response, dict) else {"raw": str(result.response)},
            "failure_reason": safe_text(result.failure_reason),
            "last_attempt_ts": now_ts(),
            "sent_ts": delivered_ts if result.ok else int(message.get("sent_ts") or 0),
            "delivered_ts": delivered_ts if result.ok else int(message.get("delivered_ts") or 0),
        }
    )

    db_status = "SENT" if result.ok else ("PENDING" if sent_status == "queued" else "FAILED")
    log = SmsLog(
        recipient_phone=updated["recipient_phone"],
        message=updated["body"],
        sent_at=None if not result.ok else datetime.utcnow(),
        status=db_status,
        ref_type="bill" if updated.get("bill_id") else "manual",
        ref_id=int(updated["bill_id"]) if safe_text(updated.get("bill_id")).isdigit() else None,
        retry_count=int(updated.get("retry_count") or 0),
    )
    db.session.add(log)
    db.session.commit()
    return updated


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
    rows = SystemSetting.query.filter(SystemSetting.setting_key.like("SMS_MESSAGE_%")).all()
    messages = [_message_to_row(row) for row in rows]
    if filters["customer_id"]:
        messages = [m for m in messages if safe_text(m.get("customer_id")) == safe_text(filters["customer_id"])]
    if filters["bill_id"]:
        messages = [m for m in messages if safe_text(m.get("bill_id")) == safe_text(filters["bill_id"])]
    if filters["phone"]:
        messages = [m for m in messages if safe_text(m.get("recipient_phone")) == safe_text(filters["phone"])]
    messages.sort(key=lambda m: (m.get("updated_ts", 0), m.get("created_ts", 0)), reverse=True)
    return jsonify(messages)


@sms_bp.route("/api/sms/messages/by-customer/<customer_id>", methods=["GET"])
def get_sms_messages_by_customer(customer_id):
    rows = SystemSetting.query.filter(SystemSetting.setting_key.like("SMS_MESSAGE_%")).all()
    messages = [
        _message_to_row(row)
        for row in rows
        if safe_text(_message_to_row(row).get("customer_id")) == safe_text(customer_id)
    ]
    messages.sort(key=lambda m: (m.get("updated_ts", 0), m.get("created_ts", 0)), reverse=True)
    return jsonify(messages)


@sms_bp.route("/api/sms/messages/by-bill/<bill_id>", methods=["GET"])
def get_sms_messages_by_bill(bill_id):
    rows = SystemSetting.query.filter(SystemSetting.setting_key.like("SMS_MESSAGE_%")).all()
    messages = [
        _message_to_row(row)
        for row in rows
        if safe_text(_message_to_row(row).get("bill_id")) == safe_text(bill_id)
    ]
    messages.sort(key=lambda m: (m.get("updated_ts", 0), m.get("created_ts", 0)), reverse=True)
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
        _seed_templates()
        template = _load_template(safe_text(data.get("template_id"))) if data.get("template_id") else None
        body = safe_text(data.get("body")) or safe_text((template or {}).get("body"))
        context = {
            "customer_name": safe_text(data.get("customer_name")),
            "bill_id": safe_text(data.get("bill_id")),
            "bill_total": safe_text(data.get("bill_total")),
            "store_name": "Selvam Medicals",
        }
        rendered_body = format_sms_body(body, context).strip()
        if not rendered_body:
            return json_error("Message body is required", 400)

        created = _save_message(
            {
                "id": safe_text(data.get("id")),
                "recipient_phone": phone,
                "customer_id": safe_text(data.get("customer_id")),
                "customer_name": safe_text(data.get("customer_name")),
                "bill_id": safe_text(data.get("bill_id")),
                "template_id": safe_text(data.get("template_id")),
                "message_type": safe_text(data.get("message_type") or (template or {}).get("message_type") or "custom"),
                "body": rendered_body,
                "send_status": "queued",
                "provider_name": "",
                "provider_message_id": "",
                "provider_response": {},
                "failure_reason": "",
                "retry_count": int(data.get("retry_count") or 0),
                "last_attempt_ts": now_ts(),
                "sent_ts": 0,
                "delivered_ts": 0,
                "source": safe_text(data.get("source") or "manual"),
            }
        )
        db.session.commit()
        if _boolish(data.get("auto_send"), True):
            created = _dispatch(created)
        return jsonify(created), 201
    except ValueError as err:
        return json_error("Failed to create SMS message", 400, str(err))
    except Exception as err:
        return json_error("Failed to create SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>", methods=["PATCH"])
def update_sms_message(message_id):
    data = request.get_json(silent=True) or {}
    try:
        current = _load_message(message_id)
        if not current:
            return json_error("SMS message not found", 404)

        allowed = {
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
        }
        updates = {k: data[k] for k in allowed if k in data}
        if not updates:
            return jsonify(current), 200
        if "provider_response" in updates and not isinstance(updates["provider_response"], dict):
            updates["provider_response"] = {"raw": str(updates["provider_response"])}

        updated = _save_message({"id": message_id, **updates})
        db.session.commit()
        return jsonify(updated), 200
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to update SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>/retry", methods=["POST"])
def retry_sms(message_id):
    try:
        current = _load_message(message_id)
        if not current:
            raise ValueError("SMS message not found")
        queued = _save_message(
            {
                "id": message_id,
                "retry_count": int(current.get("retry_count") or 0) + 1,
                "send_status": "queued",
                "last_attempt_ts": now_ts(),
            }
        )
        db.session.commit()
        retried = _dispatch(queued)
        return jsonify(retried)
    except ValueError as err:
        return json_error("Failed to retry SMS message", 404, str(err))
    except Exception as err:
        return json_error("Failed to retry SMS message", 500, str(err))


@sms_bp.route("/api/sms/messages/<message_id>/send", methods=["POST"])
def send_sms(message_id):
    try:
        current = _load_message(message_id)
        if not current:
            raise ValueError("SMS message not found")
        sent = _dispatch(current)
        return jsonify(sent)
    except ValueError as err:
        return json_error("Failed to send SMS message", 404, str(err))
    except Exception as err:
        return json_error("Failed to send SMS message", 500, str(err))


@sms_bp.route("/api/sms/templates", methods=["GET"])
def get_sms_templates():
    _seed_templates()
    rows = SystemSetting.query.filter(SystemSetting.setting_key.like("SMS_TEMPLATE_%")).all()
    templates = [_template_to_row(row) for row in rows]
    templates.sort(key=lambda t: (t.get("created_ts", 0), t.get("name", "").lower()))
    return jsonify(templates)


@sms_bp.route("/api/sms/templates", methods=["POST"])
def create_sms_template():
    data = request.get_json(silent=True) or {}
    missing = required_fields(data, ["name", "body"])
    if missing:
        return json_error("Missing required template fields", 400, missing)
    try:
        _seed_templates()
        row = _save_template(
            {
                "id": safe_text(data.get("id")) or f"tpl-{now_ts()}",
                "name": data["name"],
                "body": data["body"],
                "message_type": data.get("message_type", "custom"),
                "active": _boolish(data.get("active"), True),
                "created_ts": int(data.get("created_ts") or now_ts()),
            }
        )
        db.session.commit()
        return jsonify(row), 201
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to create SMS template", 500, str(err))


@sms_bp.route("/api/sms/templates/<template_id>", methods=["PATCH"])
def update_sms_template(template_id):
    data = request.get_json(silent=True) or {}
    try:
        row = _load_template(template_id)
        if not row:
            return json_error("SMS template not found", 404)

        updates = {k: data[k] for k in ["name", "body", "message_type", "active"] if k in data}
        if "active" in updates:
            updates["active"] = _boolish(updates["active"], True)
        updated = _save_template({"id": template_id, **updates})
        db.session.commit()
        return jsonify(updated)
    except Exception as err:
        db.session.rollback()
        return json_error("Failed to update SMS template", 500, str(err))


@sms_bp.route("/api/sms/templates/<template_id>", methods=["DELETE"])
def delete_sms_template(template_id):
    setting = SystemSetting.query.get(_tpl_key(template_id))
    if setting:
        db.session.delete(setting)
        db.session.commit()
    return jsonify({"status": "success"})
