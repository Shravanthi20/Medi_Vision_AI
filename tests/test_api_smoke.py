from __future__ import annotations

from datetime import datetime
from uuid import uuid4


def unique_id(prefix: str, length: int = 8) -> str:
    return f"{prefix}{uuid4().hex[:length]}"


def get_json(response):
    payload = response.get_json(silent=True)
    assert payload is not None, response.data.decode("utf-8", errors="replace")
    return payload


def find_item(items, key: str, value):
    for item in items:
        if item.get(key) == value:
            return item
    return None


def test_core_endpoints(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    health_body = get_json(health)
    assert health_body["status"] == "ok"
    assert health_body["database"] == "postgres"
    assert "medicines" in health_body
    assert "bills" in health_body

    backup = client.get("/api/backup")
    assert backup.status_code == 410
    backup_body = get_json(backup)
    assert backup_body["status"] == "error"


def test_inventory_smoke(client):
    medicine_id = unique_id("m", 9)
    medicine_name = f"Smoke Medicine {medicine_id[-4:]}"
    shelf_name = f"SMK{unique_id('', 7)}"

    shelf_create = client.post(
        "/api/shelves",
        json={"name": shelf_name, "status": "Active"},
    )
    assert shelf_create.status_code == 200
    assert get_json(shelf_create)["status"] == "success"

    medicines_before = client.get("/api/medicines")
    assert medicines_before.status_code == 200
    assert isinstance(get_json(medicines_before), list)

    medicine_create = client.post(
        "/api/medicines",
        json={
            "id": medicine_id,
            "n": medicine_name,
            "g": "Paracetamol",
            "c": "Tablet",
            "p": 30,
            "s": 50,
            "batch": "B101",
            "expiry": "2027-12-31",
            "p_rate": 20,
            "p_packing": "1x10",
            "s_packing": "1x10",
            "p_gst": 5,
            "s_gst": 5,
            "disc": 0,
            "offer": "",
            "reorder": 10,
            "max_qty": 200,
            "shelf_id": shelf_name[:10].upper().replace(" ", "_"),
        },
    )
    assert medicine_create.status_code == 200
    assert get_json(medicine_create)["status"] == "success"

    medicines_after = client.get("/api/medicines")
    assert medicines_after.status_code == 200
    medicine_list = get_json(medicines_after)
    created_medicine = find_item(medicine_list, "id", medicine_id)
    assert created_medicine is not None
    assert created_medicine["n"] == medicine_name

    alerts = client.get("/api/medicines/alerts?low_stock=15&expiry_days=90")
    assert alerts.status_code == 200
    alerts_body = get_json(alerts)
    assert "low_stock" in alerts_body
    assert "expiring_soon" in alerts_body

    shelves = client.get("/api/shelves")
    assert shelves.status_code == 200
    shelf_list = get_json(shelves)
    created_shelf = find_item(shelf_list, "name", shelf_name)
    assert created_shelf is not None

    shelf_delete = client.delete(f"/api/shelves/{created_shelf['id']}")
    assert shelf_delete.status_code == 200
    assert get_json(shelf_delete)["status"] == "success"

    medicine_delete = client.delete(f"/api/medicines/{medicine_id}")
    assert medicine_delete.status_code == 200
    assert get_json(medicine_delete)["status"] == "success"


def test_bill_lifecycle(client):
    medicine_id = unique_id("m", 9)
    medicine_name = f"Bill Medicine {medicine_id[-4:]}"

    medicine_create = client.post(
        "/api/medicines",
        json={
            "id": medicine_id,
            "n": medicine_name,
            "g": "Paracetamol",
            "c": "Tablet",
            "p": 30,
            "s": 25,
            "batch": "B102",
            "expiry": "2027-12-31",
            "p_rate": 18,
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
    assert medicine_create.status_code == 200

    bill_create = client.post(
        "/api/bills",
        json={
            "cust": "Walk-in",
            "phone": "",
            "pay": "cash",
            "sub": 60,
            "disc": 0,
            "tax": 3,
            "total": 63,
            "doctor": "Self",
            "items": [
                {
                    "id": medicine_id,
                    "n": medicine_name,
                    "p": 30,
                    "qty": 2,
                }
            ],
        },
    )
    assert bill_create.status_code == 200
    bill_body = get_json(bill_create)
    assert bill_body["status"] == "success"
    bill_id = bill_body["id"]

    bill_get = client.get(f"/api/bills/{bill_id}")
    assert bill_get.status_code == 200
    bill_get_body = get_json(bill_get)
    assert bill_get_body["id"] == bill_id
    assert isinstance(bill_get_body["items"], list)

    bill_update = client.patch(
        f"/api/bills/{bill_id}",
        json={"sub": 70, "disc": 2, "tax": 3.4, "total": 71.4},
    )
    assert bill_update.status_code == 200
    updated_bill = get_json(bill_update)
    assert updated_bill["id"] == bill_id

    gst_report = client.get("/api/reports/gst")
    assert gst_report.status_code == 200
    gst_body = get_json(gst_report)
    assert "total_sales" in gst_body
    assert "net_revenue" in gst_body

    bill_delete = client.delete(f"/api/bills/{bill_id}")
    assert bill_delete.status_code == 200
    assert get_json(bill_delete)["status"] == "success"


def test_purchases_and_masters_smoke(client):
    supplier_name = f"Smoke Supplier {unique_id('', 6)}"
    customer_name = f"Smoke Customer {unique_id('', 6)}"
    doctor_name = f"Dr Smoke {unique_id('', 4)}"
    medicine_id = unique_id("m", 9)
    medicine_name = f"Purchase Medicine {medicine_id[-4:]}"

    client.post(
        "/api/medicines",
        json={
            "id": medicine_id,
            "n": medicine_name,
            "g": "Paracetamol",
            "c": "Tablet",
            "p": 30,
            "s": 20,
            "batch": "B103",
            "expiry": "2027-12-31",
            "p_rate": 18,
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

    supplier_create = client.post(
        "/api/suppliers",
        json={"name": supplier_name, "phone": "9000000001", "gst": "", "status": "Active"},
    )
    assert supplier_create.status_code == 200
    assert get_json(supplier_create)["status"] == "success"

    supplier_list = get_json(client.get("/api/suppliers"))
    supplier_row = find_item(supplier_list, "name", supplier_name)
    assert supplier_row is not None
    supplier_id = supplier_row["id"]

    customer_create = client.post(
        "/api/customers",
        json={"name": customer_name, "phone": "9000000002", "address": "Sample Address", "balance": 100},
    )
    assert customer_create.status_code == 200
    assert get_json(customer_create)["status"] == "success"

    customer_list = get_json(client.get("/api/customers"))
    customer_row = find_item(customer_list, "name", customer_name)
    assert customer_row is not None
    customer_id = customer_row["id"]

    doctor_create = client.post(
        "/api/doctors",
        json={"name": doctor_name, "specialty": "General", "hospital": "Smoke Hospital", "phone": "9000000003"},
    )
    assert doctor_create.status_code == 200
    assert get_json(doctor_create)["status"] == "success"

    doctor_list = get_json(client.get("/api/doctors"))
    doctor_row = find_item(doctor_list, "name", doctor_name)
    assert doctor_row is not None
    doctor_id = doctor_row["id"]

    purchase_create = client.post(
        "/api/purchases",
        json={
            "id": f"P-{int(uuid4().hex[:6], 16)}",
            "supplier": supplier_name,
            "items": medicine_name,
            "amount": 1000,
            "date": datetime.utcnow().strftime("%d/%m/%Y"),
            "status": "Received",
            "batch": "B103",
            "expiry": "2027-12-31",
            "photo": "",
        },
    )
    assert purchase_create.status_code == 200
    assert get_json(purchase_create)["status"] == "success"

    purchases = get_json(client.get("/api/purchases"))
    assert isinstance(purchases, list)
    assert find_item(purchases, "supplier", supplier_name) is not None

    customer_ledger = client.get(f"/api/customers/{customer_id}/ledger")
    assert customer_ledger.status_code == 200
    assert isinstance(get_json(customer_ledger), list)

    payment = client.post(
        f"/api/customers/{customer_id}/payment",
        json={"amount": 25, "description": "Smoke payment"},
    )
    assert payment.status_code == 200
    payment_body = get_json(payment)
    assert payment_body["status"] == "success"
    assert "new_balance" in payment_body

    doctor_delete = client.delete(f"/api/doctors/{doctor_id}")
    assert doctor_delete.status_code == 200


def test_communications_and_sms_smoke(client):
    comm_name = f"Comm Template {unique_id('', 6)}"
    sms_name = f"SMS Template {unique_id('', 6)}"
    message_id = unique_id("sms-", 8)

    comm_list = client.get("/api/communications/templates")
    assert comm_list.status_code == 200
    assert isinstance(get_json(comm_list), list)

    comm_create = client.post(
        "/api/communications/templates",
        json={"name": comm_name, "content": "Hello {{customer_name}}", "is_active": 1},
    )
    assert comm_create.status_code == 200
    comm_body = get_json(comm_create)
    assert comm_body["status"] == "success"
    comm_id = comm_body["id"]

    comm_update = client.put(
        f"/api/communications/templates/{comm_id}",
        json={"name": f"{comm_name} Updated", "content": "Updated content", "is_active": 1},
    )
    assert comm_update.status_code == 200
    assert get_json(comm_update)["status"] == "success"

    comm_logs = client.get("/api/communications/logs")
    assert comm_logs.status_code == 200
    assert isinstance(get_json(comm_logs), list)

    comm_delete = client.delete(f"/api/communications/templates/{comm_id}")
    assert comm_delete.status_code == 200
    assert get_json(comm_delete)["status"] == "success"

    sms_templates = client.get("/api/sms/templates")
    assert sms_templates.status_code == 200
    assert isinstance(get_json(sms_templates), list)

    sms_template_create = client.post(
        "/api/sms/templates",
        json={
            "id": sms_name,
            "name": sms_name,
            "body": "Hello {customer_name}, your bill is ready.",
            "message_type": "custom",
            "active": True,
        },
    )
    assert sms_template_create.status_code == 201
    sms_template_body = get_json(sms_template_create)
    assert sms_template_body["id"] == sms_name

    sms_template_update = client.patch(
        f"/api/sms/templates/{sms_name}",
        json={"name": f"{sms_name} Updated", "body": "Updated body", "active": True},
    )
    assert sms_template_update.status_code == 200
    assert get_json(sms_template_update)["id"] == sms_name

    sms_message_create = client.post(
        "/api/sms/messages",
        json={
            "id": message_id,
            "recipient_phone": "9000000002",
            "customer_id": "1",
            "customer_name": "Smoke Customer",
            "bill_id": "1",
            "template_id": sms_name,
            "auto_send": False,
            "body": "Test SMS body",
        },
    )
    assert sms_message_create.status_code == 201
    sms_message_body = get_json(sms_message_create)
    assert sms_message_body["id"] == message_id
    assert sms_message_body["send_status"] == "queued"

    sms_messages = client.get("/api/sms/messages")
    assert sms_messages.status_code == 200
    sms_message_list = get_json(sms_messages)
    assert find_item(sms_message_list, "id", message_id) is not None

    sms_message_update = client.patch(
        f"/api/sms/messages/{message_id}",
        json={"body": "Updated SMS body", "send_status": "queued"},
    )
    assert sms_message_update.status_code == 200
    assert get_json(sms_message_update)["id"] == message_id

    sms_message_retry = client.post(f"/api/sms/messages/{message_id}/retry")
    assert sms_message_retry.status_code == 200
    assert get_json(sms_message_retry)["id"] == message_id

    sms_message_send = client.post(f"/api/sms/messages/{message_id}/send")
    assert sms_message_send.status_code == 200
    assert get_json(sms_message_send)["id"] == message_id

    sms_by_customer = client.get("/api/sms/messages/by-customer/1")
    assert sms_by_customer.status_code == 200
    assert isinstance(get_json(sms_by_customer), list)

    sms_by_bill = client.get("/api/sms/messages/by-bill/1")
    assert sms_by_bill.status_code == 200
    assert isinstance(get_json(sms_by_bill), list)

    sms_template_delete = client.delete(f"/api/sms/templates/{sms_name}")
    assert sms_template_delete.status_code == 200
    assert get_json(sms_template_delete)["status"] == "success"
