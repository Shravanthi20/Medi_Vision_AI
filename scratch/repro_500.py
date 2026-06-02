import requests
import json

URL = "http://127.0.0.1:5001/api/bills"
payload = {
    "sub": 50.0,
    "tax": 2.5,
    "total": 52.5,
    "cust": "Lily",
    "phone": "9999999999",
    "pay": "credit",
    "paid_amount": 0.0,
    "items": [{"id": "Item-1", "n": "Test Med", "p": 50.0, "qty": 1}],
}

try:
    r = requests.post(URL, json=payload)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
