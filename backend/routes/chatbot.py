import os
import json
import urllib.request
import urllib.error
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.core import Item, Customer, Supplier
from ..models.inventory import StockBatch
from ..models.sales import SalesBill
from ..models.purchase import PurchaseInvoice

chatbot_bp = Blueprint("chatbot", __name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_PROMPT = """You are a smart internal staff assistant for Selvam Medicals pharmacy running on Medi Vision AI ERP.

You have access to LIVE data from the pharmacy database injected into each message as context.

Help with:
- Stock levels, expiry dates, low stock alerts, reorder levels
- Billing: how to create/find/update bills in the ERP
- Customer info, balances, payments
- Purchase records and supplier info
- ERP navigation: sidebar menus are Sales, Purchase, Item, Masters, System, Utilities, SMS

Response rules:
- Be concise and practical
- Use bullet points for multi-step instructions
- Tell staff EXACTLY which screen/menu to use for ERP actions
- Reference live data when answering data questions
- If data not available, say so clearly
"""


def _get_live_context():
    ctx = {}
    try:
        ctx["total_medicines"] = db.session.query(func.count(Item.item_id)).scalar() or 0
        ctx["total_customers"] = db.session.query(func.count(Customer.customer_id)).scalar() or 0
        ctx["total_suppliers"] = db.session.query(func.count(Supplier.supplier_id)).scalar() or 0

        bill_stats = db.session.query(
            func.count(SalesBill.bill_id),
            func.coalesce(func.sum(SalesBill.net_amount), 0)
        ).filter(SalesBill.is_cancelled == False).first()
        ctx["total_bills"] = int(bill_stats[0]) if bill_stats else 0
        ctx["total_revenue"] = float(bill_stats[1]) if bill_stats else 0.0

        low_stock = (
            db.session.query(Item.item_name, func.coalesce(func.sum(StockBatch.current_qty), 0).label("qty"))
            .outerjoin(StockBatch, StockBatch.item_id == Item.item_id)
            .filter(Item.is_active == True)
            .group_by(Item.item_id, Item.item_name, Item.reorder_level)
            .having(func.coalesce(func.sum(StockBatch.current_qty), 0) <= Item.reorder_level)
            .limit(10).all()
        )
        ctx["low_stock_items"] = [{"name": r[0], "qty": int(r[1])} for r in low_stock]

        recent_bills = (
            db.session.query(SalesBill.bill_id, SalesBill.net_amount, SalesBill.bill_date)
            .filter(SalesBill.is_cancelled == False)
            .order_by(SalesBill.bill_id.desc()).limit(5).all()
        )
        ctx["recent_bills"] = [{"id": f"B-{r[0]}", "amount": float(r[1]), "date": str(r[2])} for r in recent_bills]

    except Exception as e:
        ctx["db_error"] = str(e)
    return ctx


def _call_gemini(user_message: str, history: list, live_ctx: dict) -> str:
    if not GEMINI_API_KEY:
        return "GEMINI_API_KEY not configured. Add it to .env and restart server."

    ctx_text = f"""
LIVE PHARMACY DATA (real-time):
- Medicines in inventory: {live_ctx.get('total_medicines', 'N/A')}
- Customers: {live_ctx.get('total_customers', 'N/A')}
- Suppliers: {live_ctx.get('total_suppliers', 'N/A')}
- Total bills: {live_ctx.get('total_bills', 'N/A')}
- Total revenue: Rs. {live_ctx.get('total_revenue', 0):.2f}
- Low stock items: {json.dumps(live_ctx.get('low_stock_items', []))}
- Recent bills: {json.dumps(live_ctx.get('recent_bills', []))}
"""

    contents = [
        {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + ctx_text}]},
        {"role": "model", "parts": [{"text": "Understood. Ready to assist Selvam Medicals staff with live data."}]}
    ]

    for msg in history[-10:]:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = json.dumps({
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 800, "topP": 0.9}
    }).encode("utf-8")

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode("utf-8", errors="replace"))
        return f"Gemini error: {err.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return f"Request failed: {str(e)}"


@chatbot_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Message required"}), 400
    if len(user_message) > 1000:
        return jsonify({"error": "Message too long"}), 400

    live_ctx = _get_live_context()
    reply = _call_gemini(user_message, history, live_ctx)

    return jsonify({
        "reply": reply,
        "live_data_snapshot": {
            "medicines": live_ctx.get("total_medicines"),
            "low_stock_count": len(live_ctx.get("low_stock_items", [])),
            "total_bills": live_ctx.get("total_bills"),
            "total_revenue": live_ctx.get("total_revenue"),
        }
    })


@chatbot_bp.route("/api/chat/context", methods=["GET"])
def chat_context():
    return jsonify(_get_live_context())
