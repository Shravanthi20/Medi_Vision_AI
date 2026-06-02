from flask import Blueprint, jsonify, request
from .auth import role_required
from ..analytics_logic import (
    get_sales_forecast, 
    get_top_moving_items, 
    get_market_basket_analysis, 
    get_churn_risk_customers,
    get_customer_lifetime_value,
    get_dynamic_stockout_risk,
    get_refill_reminders,
    get_staff_performance_summary,
    get_staff_detailed_performance
)

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    try:
        # Get various insights
        forecast = get_sales_forecast()
        top_items = get_top_moving_items()
        basket = get_market_basket_analysis()
        churn = get_churn_risk_customers()
        clv_rfm = get_customer_lifetime_value()
        stockout_risk = get_dynamic_stockout_risk()
        refills = get_refill_reminders()
        
        return jsonify({
            "status": "success",
            "forecast": forecast,
            "top_moving_items": top_items,
            "market_basket": basket,
            "churn_risk": churn,
            "clv_rfm": clv_rfm,
            "stockout_risk": stockout_risk,
            "refill_reminders": refills
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/forecast", methods=["GET"])
def sales_forecast():
    try:
        data = get_sales_forecast(days_back=60, forecast_days=14)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/refill-reminders", methods=["GET"])
def refill_reminders():
    try:
        days = int(request.args.get("days", 5))
        data = get_refill_reminders(days_buffer=days)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/staff-summary", methods=["GET"])
def staff_summary():
    try:
        data = get_staff_performance_summary()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@analytics_bp.route("/api/analytics/staff/<int:staff_id>", methods=["GET"])
def staff_details(staff_id):
    try:
        data = get_staff_detailed_performance(staff_id)
        if not data:
            return jsonify({"status": "error", "message": "Staff not found"}), 404
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
