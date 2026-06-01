import requests
import json
import random
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:5001/api"

MEDS_DATA = [
    {"n": "Paracetamol 500mg", "g": "Paracetamol", "c": "Tablet", "p": 12.50, "p_rate": 8.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 50, "max_qty": 500},
    {"n": "Amoxicillin 250mg", "g": "Amoxicillin", "c": "Capsule", "p": 45.00, "p_rate": 32.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 20, "max_qty": 200},
    {"n": "Ibuprofen 400mg", "g": "Ibuprofen", "c": "Tablet", "p": 18.00, "p_rate": 10.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 30, "max_qty": 300},
    {"n": "Cetirizine 10mg", "g": "Cetirizine", "c": "Tablet", "p": 15.00, "p_rate": 7.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 40, "max_qty": 400},
    {"n": "Pantoprazole 40mg", "g": "Pantoprazole", "c": "Tablet", "p": 65.00, "p_rate": 45.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 5, "offer": "Buy 5 Get 1 Free", "reorder": 25, "max_qty": 250},
    {"n": "Azithromycin 500mg", "g": "Azithromycin", "c": "Tablet", "p": 75.00, "p_rate": 55.0, "p_packing": "1x3", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 15, "max_qty": 150},
    {"n": "Metformin 500mg", "g": "Metformin", "c": "Tablet", "p": 22.00, "p_rate": 14.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 50, "max_qty": 1000},
    {"n": "Amlodipine 5mg", "g": "Amlodipine", "c": "Tablet", "p": 14.00, "p_rate": 9.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 30, "max_qty": 300},
    {"n": "Omeprazole 20mg", "g": "Omeprazole", "c": "Capsule", "p": 35.00, "p_rate": 22.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 40, "max_qty": 400},
    {"n": "Losartan 50mg", "g": "Losartan", "c": "Tablet", "p": 48.00, "p_rate": 30.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 20, "max_qty": 200},
    {"n": "Atorvastatin 10mg", "g": "Atorvastatin", "c": "Tablet", "p": 85.00, "p_rate": 60.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 5, "offer": "None", "reorder": 20, "max_qty": 200},
    {"n": "Ciprofloxacin 500mg", "g": "Ciprofloxacin", "c": "Tablet", "p": 55.00, "p_rate": 38.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 30, "max_qty": 300},
    {"n": "Levocetirizine 5mg", "g": "Levocetirizine", "c": "Tablet", "p": 12.00, "p_rate": 8.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 50, "max_qty": 500},
    {"n": "Diclofenac Gel", "g": "Diclofenac", "c": "Ointment", "p": 95.00, "p_rate": 65.0, "p_packing": "30g", "s_packing": "1 Tube", "p_gst": 12, "s_gst": 12, "disc": 10, "offer": "None", "reorder": 10, "max_qty": 100},
    {"n": "Cough Syrup", "g": "Dextromethorphan", "c": "Syrup", "p": 110.00, "p_rate": 78.0, "p_packing": "100ml", "s_packing": "1 Bottle", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 20, "max_qty": 200},
    {"n": "Vitamin C 500mg", "g": "Ascorbic Acid", "c": "Tablet", "p": 40.00, "p_rate": 25.0, "p_packing": "1x15", "s_packing": "1 Strip", "p_gst": 18, "s_gst": 18, "disc": 0, "offer": "Buy 2 Get 1 Free", "reorder": 30, "max_qty": 200},
    {"n": "B-Complex", "g": "Multivitamin", "c": "Capsule", "p": 50.00, "p_rate": 35.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 50, "max_qty": 500},
    {"n": "Ondansetron 4mg", "g": "Ondansetron", "c": "Tablet", "p": 38.00, "p_rate": 24.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 20, "max_qty": 200},
    {"n": "Domperidone 10mg", "g": "Domperidone", "c": "Tablet", "p": 20.00, "p_rate": 12.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 20, "max_qty": 150},
    {"n": "Alprazolam 0.25mg", "g": "Alprazolam", "c": "Tablet", "p": 15.00, "p_rate": 10.0, "p_packing": "1x10", "s_packing": "1 Strip", "p_gst": 12, "s_gst": 12, "disc": 0, "offer": "None", "reorder": 10, "max_qty": 50}
]

def seed_meds():
    for i, payload in enumerate(MEDS_DATA):
        payload["id"] = f"m_{i:04d}"
        payload["s"] = 30
        payload["batch"] = f"B20{i:02d}"
        payload["expiry"] = "2026-12-31"
        payload["shelf_id"] = "1"
        
        try:
            r = requests.post(f"{BASE_URL}/medicines", json=payload)
            if r.status_code == 200:
                print(f"Added: {payload['n']}")
            else:
                print(f"Failed {payload['n']}: {r.text}")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            break

if __name__ == "__main__":
    seed_meds()
