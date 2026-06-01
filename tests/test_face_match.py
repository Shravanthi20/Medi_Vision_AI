# tests/test_face_match.py
"""Tests for the face‑match API endpoint.

The endpoint validates a 128‑dim face vector, finds the closest stored customer
embedding, and returns a match (or no‑match).  It also cross‑references the
WantedList to flag fraudulent customers.
"""
import random
import json
import pytest

from backend.extensions import db
from backend.models.ai import WantedList
from backend.models.core import Customer


def random_face_vector(seed=0):
    """Return a deterministic 128‑float vector for reproducible tests."""
    random.seed(seed)
    return [float(random.random()) for _ in range(128)]


def test_face_match_success(client):
    import uuid
    import random
    uid = uuid.uuid4().hex[:6]
    test_name = f"Face Match Test {uid}"
    
    # Create a customer with a known face embedding
    test_seed = random.randint(1000, 99999)
    vector = random_face_vector(seed=test_seed)
    cust_resp = client.post(
        "/api/customers",
        json={"name": test_name, "phone": "9000000111", "address": "Test", "face_vector": vector},
    )
    assert cust_resp.status_code == 200

    # Pull the created customer to get its ID
    customers = client.get("/api/customers").get_json()
    cust = next(c for c in customers if c["name"] == test_name)
    cust_id = cust["id"]

    # Attempt a match with the exact same vector – should succeed
    match_resp = client.post(
        "/api/customers/face-match",
        json={"face_vector": vector},
    )
    assert match_resp.status_code == 200
    payload = match_resp.get_json()
    assert payload["status"] == "match"
    assert payload["customer"]["id"] == cust_id
    assert payload["customer"]["name"] == test_name


def test_face_match_invalid_length(client):
    # Send a vector of wrong length – expect 400 error
    bad_vector = [0.0, 1.0]  # too short
    resp = client.post("/api/customers/face-match", json={"face_vector": bad_vector})
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["status"] == "error"


def test_face_match_fraud_flag(client):
    # Create a customer with embedding
    vector = random_face_vector(seed=20)
    cust_resp = client.post(
        "/api/customers",
        json={"name": "Fraud Customer", "phone": "9000000222", "address": "Test", "face_vector": vector},
    )
    # Retrieve Customer ID via GET endpoint
    customers = client.get("/api/customers").get_json()
    cust_id = next(c["id"] for c in customers if c["name"] == "Fraud Customer")


    # Create a medicine to use in WantedList
    med_id = f"wmed{random.randint(1000,9999)}"
    client.post(
        "/api/medicines",
        json={
            "id": med_id,
            "n": "Wanted Med",
            "p": 50, "s": 100, "batch": "WANT", "expiry": "2027-12-31"
        }
    )

    # Insert a WantedList entry via API
    client.post(
        "/api/wanted-list",
        json={
            "customer_id": cust_id,
            "item_id": med_id,
            "required_qty": 5
        }
    )

    # Hack to set the reason
    with client.application.app_context():
        wanted = WantedList.query.filter_by(customer_id=cust_id).first()
        wanted.reason = "Test fraud"
        db.session.commit()

    # Perform face‑match – should return fraud flag true
    resp = client.post("/api/customers/face-match", json={"face_vector": vector})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "match"
    assert payload["wanted"] is True
    assert payload["wanted_reason"] == "Test fraud"
