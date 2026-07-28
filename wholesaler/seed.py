"""
Seed the wholesaler DB with realistic sample data so screens don't look
empty on first open. Idempotent — safe to run twice.

Run on the VPS:  cd /var/www/wholesaler && ./venv/bin/python seed.py
"""
import os
import random
import sqlite3
from datetime import date, timedelta

DB = os.environ.get("WS_DB_PATH", os.path.join(os.path.dirname(__file__), "wholesaler.db"))

SHOPS = [
    ("SEL001", "Selvam Medicals",       "Rishiikesh",  "9843012345", "Coimbatore", "33ABCDE1234F1Z5", 100000, 30, "A"),
    ("KMR002", "Kumar Pharmacy",        "Kumar S",     "9942512345", "Coimbatore", "33FGHIJ5678K2Z6", 80000,  30, "A"),
    ("RJK003", "Rajkumar Medicals",     "Rajkumar",    "9865512345", "Pollachi",   "33LMNOP9012L3Z7", 60000,  45, "B"),
    ("SHR004", "Sri Ram Medical Hall",  "Ram T",       "9789012345", "Tirupur",    "33QRSTU3456M4Z8", 50000,  30, "B"),
    ("VNK005", "Venkateshwara Pharmacy","Venkat",      "9500012345", "Mettupalayam","33VWXYZ7890N5Z9", 40000,  30, "B"),
    ("ANU006", "Anugraha Medicals",     "Devi",        "9600012345", "Coimbatore", "33ABCDE1122G6Z1", 35000,  30, "C"),
    ("PRK007", "Prakash Pharma",        "Prakash",     "9944412345", "Erode",      "33FGHIJ3344H7Z2", 30000,  45, "B"),
    ("BLA008", "Balaji Medicals",       "Bala",        "9787512345", "Salem",      "33LMNOP5566I8Z3", 25000,  30, "C"),
    ("SIV009", "Siva Pharmacy",         "Sivakumar",   "9944512345", "Coimbatore", "33QRSTU7788J9Z4", 45000,  30, "A"),
    ("MNU010", "Manu Medicals",         "Manuel",      "9500512345", "Ooty",       "33VWXYZ9900K0Z5", 20000,  30, "C"),
]

ITEMS = [
    # (code, name, generic, manufacturer, pack, mrp, ptr, ptr_b, ptr_c, gst, scheme, stock, cat)
    ("I0001", "Dolo 650",             "Paracetamol",         "Micro Labs",   "15 tab", 32.00, 25.60, 25.20, 24.80, 12, "10+1", 500, "painkillers"),
    ("I0002", "Crocin Advance",       "Paracetamol",         "GSK",          "15 tab", 35.00, 28.00, 27.60, 27.20, 12, "10+1", 400, "painkillers"),
    ("I0003", "Zerodol SP",           "Aceclofenac+Serratio","IPCA",         "10 tab", 145.00,120.00,118.00,116.00, 12, "10+1", 220, "painkillers"),
    ("I0004", "Combiflam",            "Ibuprofen+Paracetamol","Sanofi",      "20 tab",  55.00, 44.00, 43.50, 43.00, 12, "",    300, "painkillers"),
    ("I0005", "Azithral 500",         "Azithromycin",        "Alembic",      "5 tab",  126.00,105.00,103.00,101.00, 12, "5+1",  180, "antibiotics"),
    ("I0006", "Augmentin 625",        "Amoxi+Clavulanate",   "GSK",          "6 tab",  242.00,205.00,202.00,199.00, 12, "",    150, "antibiotics"),
    ("I0007", "Cifran 500",           "Ciprofloxacin",       "Ranbaxy",      "10 tab",  85.00, 68.00, 67.00, 66.00, 12, "10+1", 200, "antibiotics"),
    ("I0008", "Pantop 40",            "Pantoprazole",        "Aristo",       "15 tab",  145.00,120.00,118.00,116.00, 12, "10+1", 350, "acidity"),
    ("I0009", "Omez 20",              "Omeprazole",          "Dr Reddy's",   "15 cap",  95.00, 76.00, 75.00, 74.00, 12, "",    280, "acidity"),
    ("I0010", "Digene",               "Antacid gel",         "Abbott",       "170 ml", 105.00, 85.00, 83.50, 82.00, 12, "",    120, "acidity"),
    ("I0011", "Cetirizine 10",        "Cetirizine",          "Cipla",        "10 tab",  15.00, 12.00, 11.80, 11.60, 12, "10+1", 500, "allergy"),
    ("I0012", "Levocet-M",            "Levocet+Montelukast", "Micro Labs",   "10 tab",  110.00, 88.00, 87.00, 86.00, 12, "",    180, "allergy"),
    ("I0013", "Allegra 120",          "Fexofenadine",        "Sanofi",       "10 tab",  185.00,150.00,148.00,146.00, 12, "",    140, "allergy"),
    ("I0014", "Ecosprin 75",          "Aspirin",             "USV",          "14 tab",  16.00, 13.00, 12.80, 12.60, 12, "10+1", 400, "cardiac"),
    ("I0015", "Storvas 20",           "Atorvastatin",        "Torrent",      "10 tab", 132.00,110.00,108.00,106.00, 12, "",    220, "cardiac"),
    ("I0016", "Amlokind 5",           "Amlodipine",          "Mankind",      "10 tab",  42.00, 34.00, 33.50, 33.00, 12, "10+1", 350, "cardiac"),
    ("I0017", "Telma 40",             "Telmisartan",         "Glenmark",     "15 tab", 156.00,130.00,128.00,126.00, 12, "",    260, "cardiac"),
    ("I0018", "Glimestar M2",         "Glimepiride+Met",     "Mankind",      "10 tab", 145.00,120.00,118.00,116.00, 12, "",    200, "diabetic"),
    ("I0019", "Galvus Met 50/500",    "Vildagliptin+Met",    "Novartis",     "15 tab", 385.00,325.00,320.00,315.00, 12, "",    120, "diabetic"),
    ("I0020", "Metformin 500 SR",     "Metformin",           "USV",          "15 tab",  25.00, 20.00, 19.80, 19.60, 12, "10+1", 500, "diabetic"),
    ("I0021", "Sinarest",             "Cold combination",    "Centaur",      "10 tab",  65.00, 52.00, 51.50, 51.00, 12, "10+1", 260, "cold-cough"),
    ("I0022", "Vicks Action 500",     "Cold combination",    "P&G",          "10 tab",  50.00, 40.00, 39.50, 39.00, 12, "",    300, "cold-cough"),
    ("I0023", "Ascoril LS",           "Cough syrup",         "Glenmark",     "100 ml", 115.00, 93.00, 91.50, 90.00, 12, "",    150, "cold-cough"),
    ("I0024", "Benadryl",             "Cough syrup",         "J&J",          "100 ml", 105.00, 85.00, 83.50, 82.00, 12, "",    140, "cold-cough"),
    ("I0025", "Otrivin Adult",        "Xylometazoline nasal","GSK",          "10 ml",   95.00, 76.00, 75.00, 74.00, 12, "",    120, "cold-cough"),
    ("I0026", "Volini Gel",           "Diclofenac gel",      "Sun Pharma",   "50 g",   145.00,118.00,116.00,114.00, 12, "",    100, "topical"),
    ("I0027", "Moov",                 "Pain relief spray",   "Reckitt",      "50 g",   135.00,110.00,108.00,106.00, 12, "",    90,  "topical"),
    ("I0028", "Betadine",             "Povidone Iodine",     "Win Medicare", "100 ml", 145.00,118.00,116.00,114.00, 12, "",    110, "topical"),
    ("I0029", "Dettol Antiseptic",    "Chloroxylenol",       "Reckitt",      "550 ml", 195.00,158.00,156.00,154.00, 12, "",    80,  "topical"),
    ("I0030", "Boroline",             "Antiseptic cream",    "GD Pharma",    "20 g",    50.00, 40.00, 39.50, 39.00, 12, "",    150, "topical"),
    ("I0031", "Shelcal 500",          "Calcium+Vit D3",      "Torrent",      "15 tab", 145.00,120.00,118.00,116.00, 12, "",    220, "supplements"),
    ("I0032", "Zincovit",             "Multivitamin",        "Apex",         "15 tab",  95.00, 76.00, 75.00, 74.00, 12, "10+1", 400, "supplements"),
    ("I0033", "Neurobion Forte",      "Vit B complex",       "Merck",        "10 tab",  55.00, 44.00, 43.50, 43.00, 12, "10+1", 300, "supplements"),
    ("I0034", "Becosules",            "Vit B complex",       "Pfizer",       "20 cap",  60.00, 48.00, 47.50, 47.00, 12, "10+1", 350, "supplements"),
    ("I0035", "Iberet Folic",         "Iron+Folic",          "Abbott",       "30 tab", 195.00,158.00,156.00,154.00, 12, "",    180, "supplements"),
    ("I0036", "Insulin (Huminsulin R)","Insulin",            "Eli Lilly",    "10 ml",  245.00,205.00,202.00,200.00, 12, "",    50,  "diabetic"),
    ("I0037", "Thyronorm 50 mcg",     "Thyroxine",           "Abbott",       "120 tab",145.00,120.00,118.00,116.00, 12, "",    120, "hormonal"),
    ("I0038", "Eltroxin 100 mcg",     "Thyroxine",           "GSK",          "120 tab",165.00,138.00,136.00,134.00, 12, "",    100, "hormonal"),
    ("I0039", "Meftal Spas",          "Mefenamic+Dicyclomine","Blue Cross",  "10 tab",  75.00, 60.00, 59.00, 58.00, 12, "10+1", 200, "painkillers"),
    ("I0040", "Buscopan",             "Hyoscine",            "Sanofi",       "10 tab",  85.00, 68.00, 67.00, 66.00, 12, "",    150, "painkillers"),
    ("I0041", "ORS Powder",           "Rehydration salts",   "Cipla",        "20.5 g",  22.00, 17.60, 17.40, 17.20,  5, "20+2", 500, "otc"),
    ("I0042", "Electral Sachet",      "Rehydration salts",   "FDC",          "21.8 g",  22.00, 17.60, 17.40, 17.20,  5, "20+2", 500, "otc"),
    ("I0043", "Glucon-D",             "Glucose powder",      "Zydus",        "125 g",   55.00, 44.00, 43.50, 43.00,  5, "",    200, "otc"),
    ("I0044", "Sugar Free Natura",    "Sweetener",           "Zydus",        "100 tab", 145.00,118.00,116.00,114.00, 18, "",    100, "otc"),
    ("I0045", "Himalaya Liv 52",      "Liver tonic",         "Himalaya",     "100 tab", 195.00,158.00,156.00,154.00, 12, "",    150, "supplements"),
    ("I0046", "Cyclopam",             "Antispasmodic",       "Indoco",       "10 tab",  65.00, 52.00, 51.50, 51.00, 12, "10+1", 200, "painkillers"),
    ("I0047", "Ondem MD 4",           "Ondansetron",         "Alkem",        "10 tab", 105.00, 85.00, 83.50, 82.00, 12, "",    180, "anti-emetic"),
    ("I0048", "Emeset",               "Ondansetron",         "Cipla",        "10 tab",  95.00, 76.00, 75.00, 74.00, 12, "10+1", 160, "anti-emetic"),
    ("I0049", "Enterogermina",        "Probiotic",           "Sanofi",       "5 vial", 195.00,158.00,156.00,154.00,  5, "",    120, "gastro"),
    ("I0050", "Vizylac",              "Probiotic",           "Torrent",      "10 cap",  75.00, 60.00, 59.00, 58.00, 12, "10+1", 180, "gastro"),
]

ROUTES = [
    ("Coimbatore North", "Mon,Wed,Fri", "Ramesh"),
    ("Coimbatore South", "Tue,Thu,Sat", "Suresh"),
    ("Tirupur / Erode",  "Wed,Sat",     "Mahesh"),
    ("Ooty / Mettupalayam", "Mon,Thu",  "Kumar"),
]

SUPPLIERS = [
    ("SUP001", "Micro Labs",     "Ramesh",     "9843000001", "Bengaluru",    "29ABCDE1234F1Z1", "30 days"),
    ("SUP002", "GSK India",      "Sales Team", "9843000002", "Mumbai",       "27FGHIJ5678K2Z2", "30 days"),
    ("SUP003", "IPCA",           "Prakash",    "9843000003", "Ratlam",       "23LMNOP9012L3Z3", "45 days"),
    ("SUP004", "Sun Pharma",     "Suresh",     "9843000004", "Vadodara",     "24QRSTU3456M4Z4", "30 days"),
    ("SUP005", "Cipla",          "Rakesh",     "9843000005", "Mumbai",       "27VWXYZ7890N5Z5", "30 days"),
    ("SUP006", "Torrent",        "Manoj",      "9843000006", "Ahmedabad",    "24ABCDE1122G6Z6", "45 days"),
    ("SUP007", "Sanofi India",   "Ashok",      "9843000007", "Mumbai",       "27FGHIJ3344H7Z7", "30 days"),
]

STAFF = [
    ("Ramesh K",     "Salesman",   "9944000001", 25000, 100),
    ("Suresh P",     "Salesman",   "9944000002", 25000, 100),
    ("Mahesh V",     "Delivery",   "9944000003", 18000,  80),
    ("Kumar S",      "Delivery",   "9944000004", 18000,  80),
    ("Priya M",      "Accountant", "9944000005", 22000,   0),
    ("Ravi K",       "Packer",     "9944000006", 15000,  60),
    ("Anita R",      "Reception",  "9944000007", 14000,   0),
]


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    # Routes first (needed for shop.route_id)
    route_ids = {}
    for name, dow, sm in ROUTES:
        cur = c.execute("SELECT id FROM delivery_routes WHERE name=?", (name,)).fetchone()
        if cur:
            route_ids[name] = cur["id"]
        else:
            cur = c.execute("INSERT INTO delivery_routes (name, day_of_week, salesman) VALUES (?,?,?)", (name, dow, sm))
            route_ids[name] = cur.lastrowid

    # Shops
    for i, (code, name, cp, phone, city, gstin, credit, days, tier) in enumerate(SHOPS):
        if c.execute("SELECT 1 FROM retail_shops WHERE code=?", (code,)).fetchone():
            continue
        rid = list(route_ids.values())[i % len(route_ids)]
        c.execute("""INSERT INTO retail_shops
            (code, name, contact_person, phone, whatsapp, city, gstin, credit_limit, credit_days, price_tier, route_id, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'active')""",
            (code, name, cp, phone, phone, city, gstin, credit, days, tier, rid))

    # Items
    for row in ITEMS:
        code = row[0]
        if c.execute("SELECT 1 FROM wholesale_items WHERE code=?", (code,)).fetchone():
            continue
        c.execute("""INSERT INTO wholesale_items
            (code, name, generic, manufacturer, pack_size, mrp, ptr, ptr_b, ptr_c, gst_rate, scheme, stock, category, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active')""", row)

    # Suppliers
    for code, name, cp, phone, city, gstin, terms in SUPPLIERS:
        if c.execute("SELECT 1 FROM suppliers WHERE code=?", (code,)).fetchone():
            continue
        c.execute("""INSERT INTO suppliers (code, name, contact_person, phone, address, gstin, payment_terms)
                     VALUES (?,?,?,?,?,?,?)""",
                  (code, name, cp, phone, city, gstin, terms))

    # Staff
    for name, role, phone, base, ot in STAFF:
        if c.execute("SELECT 1 FROM staff WHERE name=? AND phone=?", (name, phone)).fetchone():
            continue
        c.execute("""INSERT INTO staff (name, role, phone, join_date, base_salary, ot_rate_per_hr, status)
                     VALUES (?,?,?,?,?,?,'active')""",
                  (name, role, phone, (date.today() - timedelta(days=random.randint(60, 900))).isoformat(), base, ot))

    # A few realistic sales orders + invoices spread across the last 30 days
    if c.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0] == 0:
        shops = c.execute("SELECT id, price_tier FROM retail_shops").fetchall()
        items = c.execute("SELECT * FROM wholesale_items").fetchall()
        for i in range(20):
            shop = random.choice(shops)
            days_ago = random.randint(0, 30)
            ord_date = (date.today() - timedelta(days=days_ago)).isoformat()
            n = c.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0]
            order_no = f"SO/25-26/{n+1:05d}"
            cur = c.execute("""INSERT INTO sales_orders (order_no, shop_id, order_date, status, source, created_by)
                               VALUES (?,?,?,?,'seed','seeder')""",
                            (order_no, shop["id"], ord_date, random.choice(["invoiced", "invoiced", "invoiced", "dispatched", "draft"])))
            oid = cur.lastrowid
            subtotal = 0
            gst = 0
            for it in random.sample(items, random.randint(3, 8)):
                qty = random.randint(2, 20)
                tier = shop["price_tier"]
                rate = it["ptr_b"] if tier == "B" and it["ptr_b"] else (it["ptr_c"] if tier == "C" and it["ptr_c"] else it["ptr"])
                free = 0
                if it["scheme"]:
                    try:
                        b, bs = it["scheme"].split("+"); b, bs = int(b), int(bs)
                        if b > 0: free = (qty // b) * bs
                    except Exception: pass
                amt = qty * rate
                subtotal += amt
                gst += amt * it["gst_rate"] / 100
                c.execute("""INSERT INTO sales_order_items
                    (order_id, item_id, item_name, pack_size, qty, free_qty, rate, gst_rate, amount)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (oid, it["id"], it["name"], it["pack_size"], qty, free, rate, it["gst_rate"], amt))
            total = subtotal + gst
            c.execute("UPDATE sales_orders SET subtotal=?, gst_amount=?, total=? WHERE id=?",
                      (subtotal, gst, total, oid))

            # For invoiced/dispatched, create an invoice too
            row = c.execute("SELECT status FROM sales_orders WHERE id=?", (oid,)).fetchone()
            if row["status"] == "invoiced":
                inv_n = c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
                inv_no = f"INV/25-26/{inv_n+1:05d}"
                due = (date.today() - timedelta(days=days_ago) + timedelta(days=30)).isoformat()
                # some randomly paid, some overdue
                paid = total if random.random() < 0.4 else 0
                status = "paid" if paid >= total else "open"
                c.execute("""INSERT INTO invoices (invoice_no, order_id, shop_id, invoice_date, due_date, total, paid, status)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (inv_no, oid, shop["id"], ord_date, due, total, paid, status))
                if paid > 0:
                    c.execute("""INSERT INTO payments (shop_id, invoice_id, amount, method, paid_on)
                                 VALUES (?,?,?,?,?)""",
                              (shop["id"], c.execute("SELECT last_insert_rowid()").fetchone()[0], paid, "upi", ord_date))

    # Expenses spread through this month
    if c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0:
        cats = [("rent", 25000), ("salary", 100000), ("transport", 8500), ("utilities", 4200),
                ("fuel", 6000), ("office", 3200), ("marketing", 5500)]
        for cat, amt in cats:
            c.execute("""INSERT INTO expenses (spent_on, category, description, amount, payment_method, entered_by)
                         VALUES (?,?,?,?,?,?)""",
                      (date.today().replace(day=random.randint(1, 20)).isoformat(),
                       cat, f"{cat.title()} for this month", amt, "bank", "seeder"))

    c.commit()
    print("seed done:")
    print("  shops     :", c.execute("SELECT COUNT(*) FROM retail_shops").fetchone()[0])
    print("  items     :", c.execute("SELECT COUNT(*) FROM wholesale_items").fetchone()[0])
    print("  suppliers :", c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0])
    print("  staff     :", c.execute("SELECT COUNT(*) FROM staff").fetchone()[0])
    print("  orders    :", c.execute("SELECT COUNT(*) FROM sales_orders").fetchone()[0])
    print("  invoices  :", c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0])
    print("  expenses  :", c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])
    c.close()


if __name__ == "__main__":
    main()
