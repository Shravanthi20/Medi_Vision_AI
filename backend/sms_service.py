import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


SMS_STORE_NAME = os.environ.get("PHARMACY_STORE_NAME", "Selvam Medicals")
SMS_PROVIDER_URL = os.environ.get("SMS_PROVIDER_URL", "").strip()
SMS_PROVIDER_KEY = os.environ.get("SMS_PROVIDER_KEY", "").strip()
SMS_PROVIDER_SENDER = os.environ.get("SMS_PROVIDER_SENDER", SMS_STORE_NAME).strip()
SMS_PROVIDER_TIMEOUT = int(os.environ.get("SMS_PROVIDER_TIMEOUT", "15") or 15)
SMS_PROVIDER_MODE = os.environ.get("SMS_PROVIDER_MODE", "auto").strip().lower()


DEFAULT_SMS_TEMPLATES = [
    {
        "id": "tpl-bill-ready",
        "name": "Bill Ready",
        "body": "Dear {customer_name}, your bill #{bill_id} for Rs. {bill_total} is ready. Thank you for visiting {store_name}.",
        "message_type": "bill_ready",
    },
    {
        "id": "tpl-pickup-reminder",
        "name": "Pickup Reminder",
        "body": "Dear {customer_name}, your medicines from bill #{bill_id} are ready for pickup at {store_name}.",
        "message_type": "reminder",
    },
    {
        "id": "tpl-follow-up",
        "name": "Follow Up",
        "body": "Hello {customer_name}, this is a follow-up from {store_name}. Please contact us for any assistance.",
        "message_type": "follow_up",
    },
    {
        "id": "tpl-low-stock",
        "name": "Low Stock Alert",
        "body": "Stock alert for {item_name}: current quantity is {stock_qty}. Please review the reorder level.",
        "message_type": "stock_alert",
    },
]


@dataclass
class ProviderResult:
    ok: bool
    status: str
    provider_name: str
    message_id: str = ""
    response: Any = None
    failure_reason: str = ""
    delivered_ts: int = 0


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def normalize_sms_template_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "body": data.get("body", ""),
        "message_type": data.get("message_type", "custom"),
        "active": int(data.get("active", 1) or 0),
        "created_ts": data.get("created_ts"),
        "updated_ts": data.get("updated_ts"),
    }


def normalize_sms_message_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    provider_response = data.get("provider_response", {})
    if isinstance(provider_response, str):
        provider_response = try_parse_json(provider_response)
    if not isinstance(provider_response, dict):
        provider_response = {"raw": provider_response}
    return {
        "id": data.get("id"),
        "created_ts": data.get("created_ts"),
        "updated_ts": data.get("updated_ts"),
        "recipient_phone": data.get("recipient_phone", ""),
        "customer_id": data.get("customer_id", ""),
        "customer_name": data.get("customer_name", ""),
        "bill_id": data.get("bill_id", ""),
        "template_id": data.get("template_id", ""),
        "message_type": data.get("message_type", "custom"),
        "body": data.get("body", ""),
        "send_status": data.get("send_status", "queued"),
        "provider_name": data.get("provider_name", ""),
        "provider_message_id": data.get("provider_message_id", ""),
        "failure_reason": data.get("failure_reason", ""),
        "retry_count": int(data.get("retry_count", 0) or 0),
        "last_attempt_ts": int(data.get("last_attempt_ts", 0) or 0),
        "sent_ts": int(data.get("sent_ts", 0) or 0),
        "delivered_ts": int(data.get("delivered_ts", 0) or 0),
        "source": data.get("source", "manual"),
        "provider_response": provider_response,
    }


def now_ts() -> int:
    return int(time.time() * 1000)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def format_sms_body(body: str, context: dict[str, Any]) -> str:
    safe_context = _SafeFormatDict({k: safe_text(v) for k, v in context.items()})
    try:
        return body.format_map(safe_context)
    except Exception:
        return body


def get_provider_config() -> dict[str, Any]:
    enabled = bool(SMS_PROVIDER_URL) and SMS_PROVIDER_MODE != "off"
    return {
        "enabled": enabled,
        "url": SMS_PROVIDER_URL,
        "key": SMS_PROVIDER_KEY,
        "sender": SMS_PROVIDER_SENDER,
        "timeout": SMS_PROVIDER_TIMEOUT,
        "name": SMS_PROVIDER_MODE if enabled else "local",
    }


def try_parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return raw


def send_sms_via_provider(payload: dict[str, Any]) -> ProviderResult:
    config = get_provider_config()
    if not config["enabled"]:
        return ProviderResult(
            ok=False,
            status="queued",
            provider_name="local",
            response={"message": "SMS provider not configured"},
            failure_reason="SMS provider not configured",
        )

    request_payload = {
        "to": payload.get("recipient_phone", ""),
        "message": payload.get("body", ""),
        "sender": config["sender"],
        "template_id": payload.get("template_id", ""),
        "bill_id": payload.get("bill_id", ""),
        "customer_id": payload.get("customer_id", ""),
        "message_type": payload.get("message_type", "custom"),
    }
    data = json.dumps(request_payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    if config["key"]:
        headers["Authorization"] = f"Bearer {config['key']}"

    req = urlrequest.Request(config["url"], data=data, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=config["timeout"]) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
            parsed = try_parse_json(raw_body)
            ok = False
            message_id = ""
            delivered_ts = now_ts()
            if isinstance(parsed, dict):
                ok = bool(
                    parsed.get("success")
                    or parsed.get("ok")
                    or parsed.get("status") in {"sent", "success", "delivered", "queued"}
                )
                message_id = safe_text(
                    parsed.get("message_id")
                    or parsed.get("id")
                    or parsed.get("provider_message_id")
                )
                delivered_ts = int(parsed.get("delivered_ts") or delivered_ts)
            else:
                ok = 200 <= getattr(resp, "status", 200) < 300
            return ProviderResult(
                ok=ok,
                status="sent" if ok else "failed",
                provider_name=config["name"],
                message_id=message_id,
                response=parsed,
                failure_reason="" if ok else f"Provider returned HTTP {getattr(resp, 'status', 200)}",
                delivered_ts=delivered_ts if ok else 0,
            )
    except Exception as err:
        return ProviderResult(
            ok=False,
            status="failed",
            provider_name=config["name"],
            response={"error": str(err)},
            failure_reason=str(err),
        )


def resolve_customer_row(conn, customer_ref: Any = None, phone: str = "", name: str = "") -> dict[str, Any] | None:
    row = None
    customer_ref = safe_text(customer_ref)
    phone = safe_text(phone)
    name = safe_text(name)
    if customer_ref:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_ref,)).fetchone()
        if row:
            return dict(row)
    if phone:
        row = conn.execute("SELECT * FROM customers WHERE phone = ? ORDER BY id DESC LIMIT 1", (phone,)).fetchone()
        if row:
            return dict(row)
    if name:
        row = conn.execute(
            "SELECT * FROM customers WHERE LOWER(name) = LOWER(?) ORDER BY id DESC LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            return dict(row)
    return None


def resolve_template_row(conn, template_id: str | None) -> dict[str, Any] | None:
    if not template_id:
        return None
    row = conn.execute("SELECT * FROM sms_templates WHERE id = ?", (template_id,)).fetchone()
    return dict(row) if row else None


def build_sms_context(conn, payload: dict[str, Any]) -> dict[str, Any]:
    customer_row = resolve_customer_row(
        conn,
        payload.get("customer_id"),
        payload.get("recipient_phone", ""),
        payload.get("customer_name", ""),
    )
    bill_total = payload.get("bill_total")
    if bill_total is None and payload.get("bill_id"):
        bill = conn.execute("SELECT * FROM bills WHERE id = ?", (payload["bill_id"],)).fetchone()
        if bill:
            bill_total = bill["total"]

    template = resolve_template_row(conn, payload.get("template_id"))
    context = {
        "store_name": SMS_STORE_NAME,
        "recipient_phone": payload.get("recipient_phone", ""),
        "customer_id": payload.get("customer_id", ""),
        "customer_name": payload.get("customer_name", ""),
        "bill_id": payload.get("bill_id", ""),
        "bill_total": bill_total if bill_total is not None else "",
        "bill_date": payload.get("bill_date", ""),
        "item_name": payload.get("item_name", ""),
        "stock_qty": payload.get("stock_qty", ""),
        "due_amount": payload.get("due_amount", ""),
        "template_name": template["name"] if template else "",
    }
    if customer_row:
        context["customer_id"] = customer_row.get("id", context["customer_id"])
        context["customer_name"] = customer_row.get("name", context["customer_name"])
        if not context["recipient_phone"]:
            context["recipient_phone"] = customer_row.get("phone", "")
    return context


def build_sms_body(conn, payload: dict[str, Any]) -> tuple[str, str]:
    template = resolve_template_row(conn, payload.get("template_id"))
    message_type = safe_text(payload.get("message_type"))
    body = safe_text(payload.get("body"))
    if template:
        message_type = message_type or template.get("message_type", "custom")
        if not body:
            body = template.get("body", "")
    if payload.get("bill_id") and not message_type:
        message_type = "bill_ready"
    if not body:
        body = payload.get("body", "")
    context = build_sms_context(conn, payload)
    rendered = format_sms_body(body, context)
    return rendered.strip(), message_type or "custom"


def _store_message(conn, payload: dict[str, Any], send_status: str, provider_result: ProviderResult | None = None) -> dict[str, Any]:
    message_id = safe_text(payload.get("id")) or f"sms-{uuid.uuid4().hex[:12]}"
    ts = now_ts()
    provider_response = provider_result.response if provider_result else payload.get("provider_response", {})
    failure_reason = provider_result.failure_reason if provider_result else safe_text(payload.get("failure_reason"))
    provider_name = provider_result.provider_name if provider_result else safe_text(payload.get("provider_name"))
    provider_message_id = provider_result.message_id if provider_result else safe_text(payload.get("provider_message_id"))
    sent_ts = provider_result.delivered_ts if provider_result and provider_result.ok else int(payload.get("sent_ts") or 0)
    delivered_ts = provider_result.delivered_ts if provider_result and provider_result.ok else int(payload.get("delivered_ts") or 0)
    conn.execute(
        """
        INSERT OR REPLACE INTO sms_messages
        (id, created_ts, updated_ts, recipient_phone, customer_id, customer_name, bill_id, template_id, message_type,
         body, send_status, provider_name, provider_message_id, provider_response, failure_reason, retry_count,
         last_attempt_ts, sent_ts, delivered_ts, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            int(payload.get("created_ts") or ts),
            ts,
            safe_text(payload.get("recipient_phone")),
            safe_text(payload.get("customer_id")),
            safe_text(payload.get("customer_name")),
            safe_text(payload.get("bill_id")),
            safe_text(payload.get("template_id")),
            safe_text(payload.get("message_type") or "custom"),
            safe_text(payload.get("body")),
            send_status,
            provider_name,
            provider_message_id,
            json.dumps(provider_response, ensure_ascii=False) if not isinstance(provider_response, str) else provider_response,
            failure_reason,
            int(payload.get("retry_count") or 0),
            int(payload.get("last_attempt_ts") or ts),
            sent_ts,
            delivered_ts,
            safe_text(payload.get("source") or "manual"),
        ),
    )
    row = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
    return normalize_sms_message_row(row)


def create_sms_message(conn, payload: dict[str, Any], auto_send: bool = True) -> dict[str, Any]:
    body, message_type = build_sms_body(conn, payload)
    recipient_phone = safe_text(payload.get("recipient_phone") or payload.get("phone"))
    if not recipient_phone:
        raise ValueError("Recipient phone is required")
    if not body:
        raise ValueError("Message body is required")
    normalized = {
        "id": safe_text(payload.get("id")),
        "recipient_phone": recipient_phone,
        "customer_id": safe_text(payload.get("customer_id")),
        "customer_name": safe_text(payload.get("customer_name")),
        "bill_id": safe_text(payload.get("bill_id")),
        "template_id": safe_text(payload.get("template_id")),
        "message_type": message_type,
        "body": body,
        "send_status": "queued",
        "provider_response": {},
        "failure_reason": "",
        "retry_count": int(payload.get("retry_count") or 0),
        "last_attempt_ts": now_ts(),
        "source": safe_text(payload.get("source") or "manual"),
    }
    queued = _store_message(conn, normalized, "queued")
    if not auto_send:
        return queued
    return dispatch_sms_message(conn, queued["id"])


def dispatch_sms_message(conn, message_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
    if not row:
        raise ValueError("SMS message not found")
    payload = dict(row)
    payload["last_attempt_ts"] = now_ts()
    result = send_sms_via_provider(payload)
    send_status = result.status
    if not result.ok and result.status == "queued":
        send_status = "queued"
    updated = _store_message(
        conn,
        payload,
        send_status,
        result,
    )
    return updated


def retry_sms_message(conn, message_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM sms_messages WHERE id = ?", (message_id,)).fetchone()
    if not row:
        raise ValueError("SMS message not found")
    payload = dict(row)
    payload["retry_count"] = int(payload.get("retry_count") or 0) + 1
    payload["send_status"] = "queued"
    payload["last_attempt_ts"] = now_ts()
    queued = _store_message(conn, payload, "queued")
    return dispatch_sms_message(conn, queued["id"])


def create_bill_sms_payload(conn, bill_data: dict[str, Any], customer_row: dict[str, Any] | None = None) -> dict[str, Any] | None:
    phone = safe_text(bill_data.get("phone") or (customer_row or {}).get("phone"))
    if not phone:
        return None
    customer_name = safe_text(bill_data.get("cust") or (customer_row or {}).get("name"))
    bill_total = bill_data.get("total")
    message_type = "bill_ready"
    body = (
        "Dear {customer_name}, your bill #{bill_id} for Rs. {bill_total} is ready. "
        "Thank you for visiting {store_name}."
    )
    template = conn.execute(
        "SELECT * FROM sms_templates WHERE message_type = ? AND active = 1 ORDER BY created_ts ASC LIMIT 1",
        ("bill_ready",),
    ).fetchone()
    template_id = ""
    if template:
        template_id = template["id"]
        body = template["body"]
        message_type = template["message_type"] or message_type
    return {
        "recipient_phone": phone,
        "customer_id": safe_text((customer_row or {}).get("id")),
        "customer_name": customer_name,
        "bill_id": safe_text(bill_data.get("id")),
        "bill_total": bill_total,
        "bill_date": bill_data.get("date", ""),
        "template_id": template_id,
        "message_type": message_type,
        "body": body,
        "source": "bill",
        "auto_send": True,
    }


def seed_sms_templates(conn) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM sms_templates").fetchone()["c"]
    if count:
        return
    ts = now_ts()
    conn.executemany(
        """
        INSERT INTO sms_templates (id, name, body, message_type, active, created_ts, updated_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                tpl["id"],
                tpl["name"],
                tpl["body"],
                tpl["message_type"],
                1,
                ts,
                ts,
            )
            for tpl in DEFAULT_SMS_TEMPLATES
        ],
    )


def list_sms_messages(conn, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    clauses: list[str] = []
    values: list[Any] = []
    if filters.get("customer_id"):
        clauses.append("customer_id = ?")
        values.append(safe_text(filters["customer_id"]))
    if filters.get("bill_id"):
        clauses.append("bill_id = ?")
        values.append(safe_text(filters["bill_id"]))
    if filters.get("phone"):
        clauses.append("recipient_phone = ?")
        values.append(safe_text(filters["phone"]))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM sms_messages {where} ORDER BY updated_ts DESC, created_ts DESC",
        tuple(values),
    ).fetchall()
    return [normalize_sms_message_row(row) for row in rows]


def list_sms_templates(conn) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM sms_templates ORDER BY created_ts ASC, name COLLATE NOCASE ASC").fetchall()
    return [normalize_sms_template_row(row) for row in rows]

