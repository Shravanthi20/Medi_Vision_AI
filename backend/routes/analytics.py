from flask import Blueprint, jsonify, request
from .auth import role_required
from ..analytics_logic import (
    get_sales_forecast, 
    get_top_moving_items, 
    get_market_basket_analysis, 
    get_churn_risk_customers,
    get_refill_reminders
)

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/api/analytics/summary", methods=["GET"])
@role_required("admin", "manager")
def analytics_summary():
    try:
        # Get various insights
        forecast = get_sales_forecast()
        top_items = get_top_moving_items()
        basket = get_market_basket_analysis()
        churn = get_churn_risk_customers()
        refills = get_refill_reminders()
        
        return jsonify({
            "status": "success",
            "forecast": forecast,
            "top_moving_items": top_items,
            "market_basket": basket,
            "churn_risk": churn,
            "refill_reminders": refills
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/forecast", methods=["GET"])
@role_required("admin", "manager")
def sales_forecast():
    try:
        data = get_sales_forecast(days_back=60, forecast_days=14)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/refill-reminders", methods=["GET"])
@role_required("admin", "manager", "staff")
def refill_reminders():
    try:
        days = int(request.args.get("days", 5))
        data = get_refill_reminders(days_buffer=days)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
