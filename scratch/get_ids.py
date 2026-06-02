from datetime import date
from decimal import Decimal
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.app_factory import create_app
from backend.extensions import db
from backend.models.core import Location, Item, Customer
from backend.models.inventory import StockBatch
from backend.models.ai import CustomerPurchasePattern

app = create_app()
with app.app_context():
    print("--- BRUNO TEST IDs ---")
    
    # 1. Existing Customer (seeded)
    cust = Customer.query.first()
    if cust:
        print(f"Customer ID (Existing): {cust.customer_id} ({cust.customer_name})")
    
    # 2. Chronic Customer
    chronic = CustomerPurchasePattern.query.filter_by(is_chronic=True).first()
    if chronic:
        print(f"Customer ID (Chronic): {chronic.customer_id}")

    # 3. New Customer
    new_cust = Customer.query.order_by(Customer.customer_id.desc()).first()
    if new_cust:
        print(f"Customer ID (New): {new_cust.customer_id} ({new_cust.customer_name})")

    # 4. Item and Batch
    batch = StockBatch.query.filter(StockBatch.current_qty > 0).first()
    if batch:
        item = Item.query.get(batch.item_id)
        print(f"Item ID: {batch.item_id} ({item.item_name if item else ''})")
        print(f"Stock Batch ID: {batch.stock_batch_id}")

    # 5. Location
    loc = Location.query.filter_by(location_code='MAIN').first()
    if loc:
        print(f"Location ID: {loc.location_id}")

