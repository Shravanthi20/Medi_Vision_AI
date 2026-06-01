from backend.app_factory import create_app

app = create_app()
with app.test_client() as client:
    cust_resp = client.post('/api/customers', json={"name": "DBG Cust", "phone": "9000000600", "address": "DBG"})
    print('create customer', cust_resp.status_code, cust_resp.get_json())
    all_customers = client.get('/api/customers')
    print('customers list', all_customers.status_code, all_customers.get_json())
    customers = all_customers.get_json()
    cust = None
    for c in customers:
        if c.get('name') == 'DBG Cust':
            cust = c
            break
    if not cust:
        print('customer not found')
        raise SystemExit(1)
    customer_id = cust['id']

    med_id = 'dbgmed123'
    med_resp = client.post('/api/medicines', json={
        'id': med_id,
        'n': 'DBG Med',
        'g': 'Paracetamol',
        'c': 'Tablet',
        'p': 10,
        's': 100,
        'batch': 'DBG',
        'expiry': '2027-12-31',
        'p_rate': 5,
        'p_packing': '1x10',
        's_packing': '1x10',
        'p_gst': 5,
        's_gst': 5,
        'disc': 0,
        'offer': '',
        'reorder': 10,
        'max_qty': 200,
        'shelf_id': 'MAIN',
    })
    print('create med', med_resp.status_code, med_resp.get_json())

    create_wanted = client.post('/api/wanted-list', json={
        'customer_id': customer_id,
        'item_id': med_id,
        'required_qty': 4,
    })
    print('create wanted status', create_wanted.status_code)
    try:
        print('create wanted json', create_wanted.get_json())
    except Exception as e:
        print('failed to decode json, raw:', create_wanted.get_data(as_text=True))
    
    # cleanup
    client.delete(f"/api/medicines/{med_id}")
    print('done')
