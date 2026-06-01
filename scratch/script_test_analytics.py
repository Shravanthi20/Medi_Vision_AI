from backend import create_app
from backend.analytics_logic import (
    get_sales_forecast, 
    get_top_moving_items, 
    get_market_basket_analysis, 
    get_churn_risk_customers,
    get_refill_reminders
)

app = create_app()
with app.app_context():
    print("Testing get_sales_forecast...")
    try: print(f"  Result: {get_sales_forecast() is not None}")
    except Exception as e: print(f"  Error: {e}")

    print("Testing get_top_moving_items...")
    try: print(f"  Result: {get_top_moving_items() is not None}")
    except Exception as e: print(f"  Error: {e}")

    print("Testing get_market_basket_analysis...")
    try: print(f"  Result: {get_market_basket_analysis() is not None}")
    except Exception as e: print(f"  Error: {e}")

    print("Testing get_churn_risk_customers...")
    try: print(f"  Result: {get_churn_risk_customers() is not None}")
    except Exception as e: print(f"  Error: {e}")

    print("Testing get_refill_reminders...")
    try: print(f"  Result: {get_refill_reminders() is not None}")
    except Exception as e: print(f"  Error: {e}")
