from backend import create_app
from backend.models.core import Customer
from backend.models.sales import SalesBill
from backend.extensions import db
from flask import request
import json

app = create_app()
with app.app_context():
    # Simulate a request payload
    data = {
        "cust": "Lily",
        "phone": "9876543210",
        "pay": "cash",
        "sub": 100,
        "disc": 0,
        "tax": 5,
        "total": 105,
        "items": [], # Empty for test
        "is_chronic": True
    }
    
    customer_name = data.get("cust", "").strip()
    customer = Customer.query.filter(Customer.customer_name.ilike(customer_name)).first()
    print(f"Before: {customer.customer_name}, Chronic: {customer.is_chronic_patient}")
    
    if "is_chronic" in data:
        customer.is_chronic_patient = bool(data["is_chronic"])
        print(f"Updated in session: {customer.is_chronic_patient}")
    
    db.session.commit()
    
    # Reload from DB
    db.session.expire_all()
    c2 = Customer.query.get(customer.customer_id)
    print(f"After Commit: {c2.customer_name}, Chronic: {c2.is_chronic_patient}")
