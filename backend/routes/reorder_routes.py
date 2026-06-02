"""Routes — Reorder Requests + n8n WhatsApp Conversation Flow.

Endpoints:
  POST  /api/reorders/request           — create & trigger n8n outbound message
  POST  /api/reorders/n8n-callback      — inbound callback from n8n after supplier reply
  GET   /api/reorders/<id>/conversation — fetch full reorder + conversation detail
  GET   /api/reorders                   — list all reorder requests (optional filters)
"""

import os
import re
import logging
from datetime import datetime, timezone

import requests
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models.reorder_request import ReorderRequest, REORDER_STATUSES

logger = logging.getLogger(__name__)

reorders_bp = Blueprint("reorders", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_error(message: str, status_code: int = 400, details=None):
    payload = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def _required_fields(payload: dict, fields: list) -> list:
    missing = []
    for field in fields:
        val = payload.get(field)
        if val is None:
            missing.append(field)
        elif isinstance(val, str) and not val.strip():
            missing.append(field)
    return missing


def _build_whatsapp_message(reorder: ReorderRequest) -> str:
    """Format the menu-driven WhatsApp message sent to the supplier."""
    supplier_name = (
        reorder.supplier.supplier_name if reorder.supplier else f"Supplier #{reorder.supplier_id}"
    )
    store_name = os.getenv("PHARMACY_STORE_NAME", "Your Pharmacy")

    lines = [
        f"*Reorder Request — {store_name}*",
        f"Supplier: {supplier_name}",
        "",
        "Items:",
    ]
    for idx, item in enumerate(reorder.items, start=1):
        name = item.get("item_name", item.get("item_id", "Unknown"))
        qty = item.get("quantity", "?")
        unit = item.get("unit", "units")
        lines.append(f"  {idx}) {name} | Qty: {qty} {unit}")

    lines += [
        "",
        "Please reply with:",
        "  *1* — Confirm all",
        "  *2* — Reject",
        "  *3, 1=<qty>, 2=<qty>, ...* — Change quantities",
        "",
        f"Ref: #{reorder.reorder_id}",
    ]
    return "\n".join(lines)


def _trigger_n8n(reorder: ReorderRequest) -> bool:
    """POST the reorder details to the n8n outbound webhook. Returns True on success."""
    n8n_url = os.getenv("N8N_WEBHOOK_URL", "")
    if not n8n_url:
        logger.warning("N8N_WEBHOOK_URL not set — skipping n8n trigger")
        return False

    supplier_name = (
        reorder.supplier.supplier_name if reorder.supplier else f"Supplier #{reorder.supplier_id}"
    )
    supplier_phone = (
        reorder.supplier.phone if reorder.supplier else ""
    )

    payload = {
        "reorder_id": reorder.reorder_id,
        "store_name": os.getenv("PHARMACY_STORE_NAME", "Your Pharmacy"),
        "supplier_name": supplier_name,
        "supplier_phone": supplier_phone,
        "pharmacy_whatsapp": os.getenv("PHARMACY_WHATSAPP_NUMBER", ""),
        "items": reorder.items,
        "message": _build_whatsapp_message(reorder),
        # Let n8n know where to POST the supplier reply result
        "callback_url": f"{os.getenv('BASE_URL', '').rstrip('/')}/api/reorders/n8n-callback",
        "callback_secret": os.getenv("N8N_INBOUND_WEBHOOK_SECRET", ""),
    }

    try:
        resp = requests.post(n8n_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("n8n triggered for reorder #%s — HTTP %s", reorder.reorder_id, resp.status_code)
        return True
    except requests.RequestException as exc:
        logger.error("n8n trigger failed for reorder #%s: %s", reorder.reorder_id, exc)
        return False


def _parse_menu_reply(raw_text: str, items: list) -> tuple:
    """
    Parse the supplier's menu reply.

    Returns (status, confirmed_items, notes):
      - "1"                → CONFIRMED (all quantities as-is)
      - "2"                → REJECTED
      - "3, 1=20, 2=40"   → PARTIALLY_CONFIRMED with per-item qty overrides
      - anything else      → PROCESSING (manual review needed)
    """
    text = raw_text.strip()

    if text == "1":
        confirmed = [
            {
                "item_id": it.get("item_id"),
                "requested_qty": it.get("quantity", 0),
                "confirmed_qty": it.get("quantity", 0),
            }
            for it in items
        ]
        return "CONFIRMED", confirmed, None

    if text == "2":
        return "REJECTED", None, None

    if text.startswith("3"):
        # Format: "3, 1=20, 2=40" or "3,1=20,2=40"
        overrides: dict[int, int] = {}
        for match in re.finditer(r"(\d+)\s*=\s*(\d+)", text):
            item_idx = int(match.group(1))
            qty = int(match.group(2))
            overrides[item_idx] = qty

        confirmed = []
        all_match = True
        for idx, it in enumerate(items, start=1):
            req_qty = it.get("quantity", 0)
            conf_qty = overrides.get(idx, req_qty)
            if conf_qty != req_qty:
                all_match = False
            confirmed.append(
                {
                    "item_id": it.get("item_id"),
                    "requested_qty": req_qty,
                    "confirmed_qty": conf_qty,
                }
            )
        status = "CONFIRMED" if all_match else "PARTIALLY_CONFIRMED"
        return status, confirmed, None

    # Fallback — store raw reply for manual review
    notes = f"Could not auto-parse supplier reply: {text!r}"
    logger.warning(notes)
    return "PROCESSING", None, notes


# ---------------------------------------------------------------------------
# Endpoint: POST /api/reorders/request
# ---------------------------------------------------------------------------

@reorders_bp.route("/api/reorders/request", methods=["POST"])
def create_reorder():
    """Create a reorder request and optionally trigger the n8n outbound WhatsApp message."""
    data = request.get_json(silent=True) or {}

    missing = _required_fields(data, ["supplier_id", "location_id", "items"])
    if missing:
        return _json_error("Missing required fields", 400, missing)

    if not isinstance(data["items"], list) or not data["items"]:
        return _json_error("'items' must be a non-empty list", 400)

    try:
        reorder = ReorderRequest(
            supplier_id=int(data["supplier_id"]),
            location_id=int(data["location_id"]),
            items=data["items"],
            status="PENDING",
        )
        db.session.add(reorder)
        db.session.flush()  # get reorder_id before committing

        trigger = data.get("trigger_n8n", True)
        n8n_ok = False

        if trigger:
            n8n_ok = _trigger_n8n(reorder)
            reorder.status = "SENT" if n8n_ok else "FAILED"
            reorder.sent_at = datetime.now(timezone.utc) if n8n_ok else None
            if not n8n_ok:
                reorder.notes = "n8n trigger failed — check N8N_WEBHOOK_URL and n8n connectivity"

        db.session.commit()

        return jsonify({
            "status": "success",
            "reorder_id": reorder.reorder_id,
            "reorder_status": reorder.status,
            "n8n_triggered": n8n_ok,
        }), 201

    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to create reorder request")
        return _json_error("Failed to create reorder request", 500, str(exc))


# ---------------------------------------------------------------------------
# Endpoint: POST /api/reorders/n8n-callback
# ---------------------------------------------------------------------------

@reorders_bp.route("/api/reorders/n8n-callback", methods=["POST"])
def n8n_callback():
    """
    Inbound webhook called by n8n after it receives and parses the supplier's reply.

    Expected payload:
    {
        "reorder_id": 1,
        "status": "CONFIRMED|PARTIALLY_CONFIRMED|REJECTED|PROCESSING",
        "provider_message_id": "SM...",          // Twilio SID (optional)
        "n8n_conversation_id": "conv_123",       // optional
        "supplier_response": "raw text from supplier",
        "confirmed_items": [...],                // optional — provided when n8n parses
        "secret": "<N8N_INBOUND_WEBHOOK_SECRET>"
    }
    """
    data = request.get_json(silent=True) or {}

    # --- Authenticate ---
    expected_secret = os.getenv("N8N_INBOUND_WEBHOOK_SECRET", "")
    if not expected_secret:
        logger.warning("/api/reorders/n8n-callback: N8N_INBOUND_WEBHOOK_SECRET not configured")
        return _json_error("Callback endpoint not configured", 503)

    if data.get("secret") != expected_secret:
        return _json_error("Unauthorized", 401)

    # --- Validate required fields ---
    missing = _required_fields(data, ["reorder_id", "status"])
    if missing:
        return _json_error("Missing required fields", 400, missing)

    incoming_status = str(data["status"]).upper()
    if incoming_status not in REORDER_STATUSES:
        return _json_error(
            f"Invalid status '{incoming_status}'. Allowed: {REORDER_STATUSES}", 400
        )

    # --- Fetch & update ---
    reorder = db.session.get(ReorderRequest, int(data["reorder_id"]))
    if not reorder:
        return _json_error("Reorder not found", 404)

    raw_response = data.get("supplier_response", "")

    # If n8n sends a raw supplier reply instead of a pre-parsed status, parse it here
    if incoming_status == "PROCESSING" and raw_response:
        parsed_status, parsed_items, parse_notes = _parse_menu_reply(raw_response, reorder.items)
        reorder.status = parsed_status
        reorder.confirmed_items = parsed_items
        if parse_notes:
            reorder.notes = (reorder.notes or "") + "\n" + parse_notes
    else:
        reorder.status = incoming_status
        if data.get("confirmed_items"):
            reorder.confirmed_items = data["confirmed_items"]

    reorder.supplier_response = raw_response or reorder.supplier_response
    reorder.provider_message_id = data.get("provider_message_id") or reorder.provider_message_id
    reorder.n8n_conversation_id = data.get("n8n_conversation_id") or reorder.n8n_conversation_id
    reorder.responded_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
        logger.info("Reorder #%s updated to status=%s via n8n callback", reorder.reorder_id, reorder.status)
        return jsonify({"status": "success", "reorder_id": reorder.reorder_id, "new_status": reorder.status})
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to update reorder #%s from n8n callback", data.get("reorder_id"))
        return _json_error("Failed to update reorder", 500, str(exc))


# ---------------------------------------------------------------------------
# Endpoint: GET /api/reorders/<id>/conversation
# ---------------------------------------------------------------------------

@reorders_bp.route("/api/reorders/<int:reorder_id>/conversation", methods=["GET"])
def get_conversation(reorder_id: int):
    """Return full reorder record + conversation details for the UI."""
    reorder = db.session.get(ReorderRequest, reorder_id)
    if not reorder:
        return _json_error("Reorder not found", 404)

    supplier_name = (
        reorder.supplier.supplier_name if reorder.supplier else None
    )

    return jsonify({
        "reorder": reorder.to_dict(),
        "supplier_name": supplier_name,
        "whatsapp_message": _build_whatsapp_message(reorder),
    })


# ---------------------------------------------------------------------------
# Endpoint: GET /api/reorders
# ---------------------------------------------------------------------------

@reorders_bp.route("/api/reorders", methods=["GET"])
def list_reorders():
    """List reorder requests, optionally filtered by status or supplier_id."""
    status_filter = request.args.get("status")
    supplier_filter = request.args.get("supplier_id", type=int)
    limit = request.args.get("limit", 50, type=int)

    query = ReorderRequest.query.order_by(ReorderRequest.created_at.desc())

    if status_filter:
        query = query.filter(ReorderRequest.status == status_filter.upper())
    if supplier_filter:
        query = query.filter(ReorderRequest.supplier_id == supplier_filter)

    reorders = query.limit(min(limit, 200)).all()
    return jsonify([r.to_dict() for r in reorders])
