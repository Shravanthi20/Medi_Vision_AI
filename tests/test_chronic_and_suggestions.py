# tests/test_chronic_and_suggestions.py
"""Tests for chronic‑medicine handling and personalised suggestions.

- Verify that the `is_chronic` flag on a bill item propagates to the
  `CustomerPurchasePattern.is_chronic_patient` field.
- Verify that the `/api/customers/<id>/suggestions` endpoint returns sensible
  recommendations based on market‑basket analysis and respects request parameters.
"""
import json
import random
import pytest
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.ai import CustomerPurchasePattern
from backend.models.core import Customer


def random_face_vector():
    random.seed(1)
    return [float(random.random()) for _ in range(128)]

def test_chronic_flag_updates_pattern(client):
    # Create a customer
    cust_name = f"Chronic Customer {random.randint(1000,9999)}"
    resp = client.post(
        "/api/customers",
        json={"name": cust_name, "phone": "9000000555", "address": "Test"},
    )
    assert resp.status_code == 200

    # Create a medicine
    med_id = f"cmed{random.randint(1000,9999)}"
    med_name = f"Chronic Med {med_id}"
    med_create = client.post(
        "/api/medicines",
        json={
            "id": med_id,
            "n": med_name,
            "g": "Paracetamol",
            "c": "Tablet",
            "p": 50,
            "s": 100,
            "batch": "CHRONIC",
            "expiry": "2027-12-31",
            "p_rate": 30,
            "p_packing": "1x10",
            "s_packing": "1x10",
            "p_gst": 5,
            "s_gst": 5,
            "disc": 0,
            "offer": "",
            "reorder": 10,
            "max_qty": 200,
            "shelf_id": "MAIN",
        },
    )
    assert med_create.status_code == 200

    # Create a bill with the chronic flag on the item
    bill_resp = client.post(
        "/api/bills",
        json={
            "cust": cust_name,
            "phone": "9000000555",
            "pay": "cash",
            "sub": 50,
            "disc": 0,
            "tax": 5,
            "total": 55,
            "doctor": "Self",
            "items": [
                {"id": med_id, "n": med_name, "p": 50, "qty": 1, "is_chronic": True}
            ],
        },
    )
    assert bill_resp.status_code == 200

    # Verify the CustomerPurchasePattern record has chronic flag set
    with client.application.app_context():
        cust = Customer.query.filter_by(customer_name=cust_name).first()
        pattern = CustomerPurchasePattern.query.filter_by(customer_id=cust.customer_id, item_id=med_id).first()
        assert pattern is not None, "Purchase pattern should exist"
        assert pattern.is_chronic is True, "Chronic flag should be persisted"


def test_personalized_suggestions_endpoint(client):
    # Create two customers
    cust_a = f"SuggestA {random.randint(1000,9999)}"
    cust_b = f"SuggestB {random.randint(1000,9999)}"
    for name in (cust_a, cust_b):
        resp = client.post(
            "/api/customers",
            json={"name": name, "phone": "9000000666", "address": "Test"},
        )
        assert resp.status_code == 200

    # Create two medicines with huge max_qty and stock to ensure they are suggested
    med1_id = f"smed{random.randint(1000,9999)}"
    med2_id = f"smed{random.randint(1000,9999)}"
    for mid, mname in ((med1_id, "MedOne"), (med2_id, "MedTwo")):
        med_create = client.post(
            "/api/medicines",
            json={
                "id": mid,
                "n": mname,
                "g": "Paracetamol",
                "c": "Tablet",
                "p": 50,
                "s": 100000,  # Huge stock to bump it to the top
                "batch": "SUGG",
                "expiry": "2027-12-31",
                "p_rate": 30,
                "p_packing": "1x10",
                "s_packing": "1x10",
                "p_gst": 5,
                "s_gst": 5,
                "disc": 0,
                "offer": "",
                "reorder": 10,
                "max_qty": 200000,
                "shelf_id": "MAIN",
            },
        )
        assert med_create.status_code == 200

    # Customer A buys both meds (creates market‑basket association)
    resp_a = client.post(
        "/api/bills",
        json={
            "cust": cust_a,
            "phone": "9000000666",
            "pay": "cash",
            "sub": 100,
            "disc": 0,
            "tax": 5,
            "total": 105,
            "doctor": "Self",
            "items": [
                {"id": med1_id, "n": "MedOne", "p": 50, "qty": 1},
                {"id": med2_id, "n": "MedTwo", "p": 50, "qty": 1},
            ],
        },
    )
    assert resp_a.status_code == 200

    # Customer B buys only med2
    resp_b = client.post(
        "/api/bills",
        json={
            "cust": cust_b,
            "phone": "9000000666",
            "pay": "cash",
            "sub": 50,
            "disc": 0,
            "tax": 5,
            "total": 55,
            "doctor": "Self",
            "items": [{"id": med2_id, "n": "MedTwo", "p": 50, "qty": 1}],
        },
    )
    assert resp_b.status_code == 200

    # Retrieve Customer B ID
    customers = client.get("/api/customers").get_json()
    cust_b_obj = next(c for c in customers if c["name"] == cust_b)
    cust_b_id = cust_b_obj["id"]

    # Call suggestions endpoint – expect med1 to appear (market basket) and med2 excluded (recent purchase)
    sugg_resp = client.get(
        f"/api/customers/{cust_b_id}/suggestions?limit=50&days_back=90&exclude_recent_days=30"
    )
    assert sugg_resp.status_code == 200
    data = sugg_resp.get_json()
    suggestions = data["suggestions"]
    # Ensure med1 is included while med2 is not
    assert isinstance(suggestions, list)
    med_ids = [s["item_id"] for s in suggestions]
    assert med1_id in med_ids, f"Expected {med1_id} in {med_ids}"
    assert med2_id not in med_ids, "Recently purchased medicine should be excluded"
