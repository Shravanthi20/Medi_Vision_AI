import sys, os, uuid, random, re
from datetime import datetime, date, time, timedelta
import xlrd
from decimal import Decimal
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(__file__))
from backend.app_factory import create_app
from backend.extensions import db

app = create_app()

STOCK_FILE = "/home/rishiikesh/Rishiikesh/Projects/Intern-SelvamMedicals/Medi_Vision_AI/SS & CO ITEM STOCK REPORT.xls"
DRUG_FILE = "/home/rishiikesh/Rishiikesh/Projects/Intern-SelvamMedicals/Medi_Vision_AI/DRUG REPORT 01.01.26 TO 31.01.26 (1).xls"

def clean_float(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '')
        return float(val) if val else 0.0
    except ValueError:
        return 0.0

def clean_drug_name(name):
    # Remove hashtags, asterisks, underscores, and clean spaces
    name = re.sub(r'###|\*|_', '', name)
    return name.strip().lower()

def seed():
    with app.app_context():
        from backend.models.core import (
            Role, User, FinancialYear, GstSlab, HsnCode, Combination,
            Manufacturer, ProductCategory, UnitOfMeasure, Item, Location,
            Supplier, Doctor, Customer,
        )
        from backend.models.lookups import (
            BillType, PurchaseType, TxnType, PaymentMode, WantedStatus, ReturnReason,
        )
        from backend.models.inventory import StockBatch
        from backend.models.sales import (
            SalesBill, SalesBillItem, BillingVoucher,
        )
        from backend.models.finance import Expense
        from backend.models.hr import Salesman, AttendanceLog, SalesmanLedger
        from backend.models.ai import AiFaceLog, PrescriptionOcrLog, CustomerPurchasePattern

        today = date.today()
        now = datetime.now()

        def get_or_create(model, defaults, **kwargs):
            obj = model.query.filter_by(**kwargs).first()
            if obj:
                return obj
            obj = model(**kwargs, **defaults)
            db.session.add(obj)
            db.session.flush()
            return obj

        print("Creating Core configuration & lookups...")
        role = get_or_create(Role, {"can_bill": True, "can_manage_system": True}, role_name="Admin")
        bt = get_or_create(BillType, {"bill_type_name": "Regular"}, bill_type_code="REG")
        pt = get_or_create(PurchaseType, {"purchase_type_name": "Regular"}, purchase_type_code="REG")
        get_or_create(TxnType, {"txn_type_name": "Sale"}, txn_type_code="SALE")
        pm_cash = get_or_create(PaymentMode, {"payment_mode_name": "Cash"}, payment_mode_code="CASH")
        pm_upi = get_or_create(PaymentMode, {"payment_mode_name": "UPI"}, payment_mode_code="UPI")
        get_or_create(WantedStatus, {"status_name": "Pending"}, status_code="PENDING")
        get_or_create(ReturnReason, {"reason_name": "Expired"}, reason_code="EXPIRED")

        fy = get_or_create(FinancialYear, {
            "start_date": date(2025, 4, 1), "end_date": date(2026, 3, 31), "is_active": True
        }, fy_label="2025-2026")

        gst0 = get_or_create(GstSlab, {"slab_rate_pct": 0, "cgst_pct": 0, "sgst_pct": 0, "igst_pct": 0, "effective_from": date(2017, 7, 1)}, slab_code="G00")
        gst5 = get_or_create(GstSlab, {"slab_rate_pct": 5, "cgst_pct": 2.5, "sgst_pct": 2.5, "igst_pct": 0, "effective_from": date(2017, 7, 1)}, slab_code="G05")
        gst12 = get_or_create(GstSlab, {"slab_rate_pct": 12, "cgst_pct": 6, "sgst_pct": 6, "igst_pct": 0, "effective_from": date(2017, 7, 1)}, slab_code="G12")
        gst18 = get_or_create(GstSlab, {"slab_rate_pct": 18, "cgst_pct": 9, "sgst_pct": 9, "igst_pct": 0, "effective_from": date(2017, 7, 1)}, slab_code="G18")

        hsn_gen = get_or_create(HsnCode, {"description": "General", "gst_slab_id": gst12.gst_slab_id}, hsn_code="00000000")
        uom_gen = get_or_create(UnitOfMeasure, {"uom_name": "Pieces"}, uom_code="PCS")
        cat_gen = get_or_create(ProductCategory, {}, category_name="General")
        loc_main = get_or_create(Location, {"location_name": "Main Store", "is_default": True}, location_code="MAIN")
        
        mfr_gen = get_or_create(Manufacturer, {"manufacturer_name": "Unknown"}, manufacturer_code="UNKNOWN")

        user_id = uuid.uuid4()
        user = get_or_create(User, {
            "name": "Admin User", "password_hash": generate_password_hash("demo"),
            "role_id": role.role_id, "user_id": user_id
        }, username="admin")
        
        # In case the user already exists with old unhashed password, update it
        user.password_hash = generate_password_hash("demo")
        
        uid = user.user_id

        sm1 = get_or_create(Salesman, {"salesman_name": "Karthik R", "phone": "9876500020", "role_id": role.role_id, "salary_per_hr": 80}, salesman_code="SM001")
        sm2 = get_or_create(Salesman, {"salesman_name": "Divya S", "phone": "9876500021", "role_id": role.role_id, "salary_per_hr": 75}, salesman_code="SM002")

        db.session.commit()

        # Check existing items to avoid duplicates
        existing_items = {i.item_id for i in Item.query.all()}
        
        print("Parsing Stock Data...")
        items_map = {}
        all_loaded_stock = []
        try:
            wb_stock = xlrd.open_workbook(STOCK_FILE)
            stock_sheet = wb_stock.sheets()[0]
            count = 0
            # Read first ~200 items (reduced for lighter load)
            for r in range(2, min(202, stock_sheet.nrows)):
                row = [str(stock_sheet.cell_value(r, c)).strip() for c in range(stock_sheet.ncols)]
                if len(row) < 10 or not row[1]: continue
                
                item_name = row[1][:199]
                
                # Skip obviously non-medicine items
                skip_keywords = ['sparkler', 'wala', 'fancy', 'razor', 'pop', 'shot', 'firework']
                if any(k in item_name.lower() for k in skip_keywords):
                    continue

                qty = int(clean_float(row[2]))
                mrp = clean_float(row[3])
                sel_price = clean_float(row[4])
                pur_rate = clean_float(row[7])
                
                # Make sure ID is unique and max 10 chars, maybe auto generated
                item_id = f"I{r:05d}"
                if item_id in existing_items:
                    continue
                
                itm = Item(
                    item_id=item_id,
                    item_name=item_name,
                    manufacturer_id=mfr_gen.manufacturer_id,
                    category_id=cat_gen.category_id,
                    hsn_id=hsn_gen.hsn_id,
                    uom_id=uom_gen.uom_id,
                    purchase_gst_slab_id=gst12.gst_slab_id,
                    sales_gst_slab_id=gst12.gst_slab_id,
                    default_mrp=mrp,
                    default_selling_price=sel_price,
                    min_margin_pct=10.0,
                    reorder_level=5,
                    max_stock=100
                )
                db.session.add(itm)
                
                # Create Stock Batch
                batch = StockBatch(
                    item_id=item_id,
                    batch_no=f"B{r}",
                    expiry_date=today + timedelta(days=random.randint(30, 700)),
                    location_id=loc_main.location_id,
                    manufacturer_id=mfr_gen.manufacturer_id,
                    mrp=mrp,
                    purchase_rate=pur_rate,
                    opening_qty=qty,
                    current_qty=qty,
                    total_stock=qty,
                )
                db.session.add(batch)
                db.session.flush()
                
                clean_name = clean_drug_name(item_name)
                items_map[clean_name] = (itm, batch)
                all_loaded_stock.append((itm, batch))
                count += 1
            db.session.commit()
            print(f"Added {count} new items and stock batches.")
        except Exception as e:
            print(f"Error reading stock data: {e}")
            db.session.rollback()

        print("Parsing Sales Data...")
        try:
            wb_drug = xlrd.open_workbook(DRUG_FILE)
            drug_sheet = wb_drug.sheets()[0]
            
            doctors = {}
            customers = {}
            
            curr_billno = None
            curr_doc = None
            curr_pat = None
            current_bill = None
            current_voucher = None
            
            # Read first ~150 bills (skip first 2 rows, reduced for lighter load)
            sales_added = db.session.query(db.func.max(SalesBill.bill_no)).scalar() or 0
            for r in range(2, min(152, drug_sheet.nrows)):
                row = [str(drug_sheet.cell_value(r, c)).strip() for c in range(drug_sheet.ncols)]
                if len(row) < 9 or not row[4]: continue
                
                if row[0]:
                    curr_billno = row[0]
                    curr_doc = row[1][:149] if row[1] else "Self"
                    curr_pat = row[2][:149] if row[2] else "Walk-in Customer"
                    current_bill = None
                
                billno_raw = curr_billno
                doc_name = curr_doc
                pat_name = curr_pat
                drug_name = row[4][:199]
                qty = max(1.0, clean_float(row[5]))
                mfr_name = row[6][:149]
                
                # Setup Doc
                if doc_name not in doctors:
                    doc = Doctor.query.filter_by(doctor_name=doc_name).first()
                    if not doc:
                        doc = Doctor(doctor_name=doc_name)
                        db.session.add(doc)
                        db.session.flush()
                    doctors[doc_name] = doc
                    
                # Setup Customer
                if pat_name not in customers:
                    cust = Customer.query.filter_by(customer_name=pat_name).first()
                    if not cust:
                        cust = Customer(customer_name=pat_name, phone=f"98765{random.randint(10000, 99999)}", doctor_id=doctors[doc_name].doctor_id)
                        db.session.add(cust)
                        db.session.flush()
                    customers[pat_name] = cust
                    
                # Setup Bill (accumulate items for same bill)
                mrp = random.uniform(50.0, 500.0)
                gross = mrp * qty
                disc = round(gross * 0.05, 2)
                taxable = gross - disc
                cgst = round(taxable * 0.06, 2)
                sgst = cgst
                net = round(taxable + cgst + sgst, 2)
                
                bdate = today - timedelta(days=random.randint(0, 30))
                btime = time(random.randint(9, 20), random.randint(0, 59))
                
                if not current_bill:
                    current_bill = SalesBill(
                        bill_no=sales_added + 1,
                        bill_date=bdate, bill_time=btime,
                        financial_year_id=fy.financial_year_id,
                        customer_id=customers[pat_name].customer_id, salesman_id=sm1.salesman_id,
                        user_id=uid, location_id=loc_main.location_id, bill_type_id=bt.bill_type_id,
                        gross_amount=0, discount_pct=5, discount_amount=0,
                        taxable_amount=0, cgst_amount=0, sgst_amount=0,
                        igst_amount=0, net_amount=0, payment_mode=random.choice(["cash", "upi"]),
                    )
                    db.session.add(current_bill)
                    db.session.flush()
                    sales_added += 1
                
                # Accumulate for the current bill
                current_bill.gross_amount += gross
                current_bill.discount_amount += disc
                current_bill.taxable_amount += taxable
                current_bill.cgst_amount += cgst
                current_bill.sgst_amount += sgst
                current_bill.net_amount += net
                
                clean_name = clean_drug_name(drug_name)
                if clean_name in items_map:
                    itm, sb = items_map[clean_name]
                    pr = float(sb.purchase_rate)
                    mrp = float(sb.mrp)
                else:
                    if all_loaded_stock:
                        itm, sb = random.choice(all_loaded_stock)
                        pr = float(sb.purchase_rate)
                        mrp = float(sb.mrp)
                    else:
                        continue
                    
                bi = SalesBillItem(
                    bill_id=current_bill.bill_id, stock_batch_id=sb.stock_batch_id,
                    item_id=itm.item_id, qty_sold=qty,
                    mrp_at_sale=mrp, purchase_rate_at_sale=pr, selling_price_at_sale=mrp,
                    discount_pct=5, net_rate=round(mrp * 0.95, 2),
                    gst_slab_id=gst12.gst_slab_id, cgst_pct=6.0, sgst_pct=6.0, igst_pct=0,
                    gst_amount=cgst + sgst, profit_pct=round((mrp - pr) / mrp * 100, 2) if mrp else 0,
                    margin_flag=False, value=net,
                )
                db.session.add(bi)
                
                if current_voucher is None:
                    current_voucher = BillingVoucher(
                        voucher_type="RECEIPT", voucher_no=f"RV-{current_bill.bill_id}",
                        voucher_date=bdate, payment_type=current_bill.payment_mode.capitalize(),
                        amount=0, user_id=uid, linked_bill_id=current_bill.bill_id,
                    )
                    db.session.add(current_voucher)
                
                current_voucher.amount += net
                
            db.session.commit()
            print(f"Added {sales_added} real sales bills.")
        except Exception as e:
            print(f"Error reading drug data: {e}")
            db.session.rollback()

        # Add some mock AI, Expense, HR data so reports work fully
        print("Adding supplementary mock data (HR, Expenses, AI)...")
        for cat, amt, d in [("Electricity", 2500, 5), ("Rent", 15000, 1), ("Courier", 350, 3)]:
            db.session.add(Expense(
                financial_year_id=fy.financial_year_id,
                expense_date=today - timedelta(days=d),
                expense_category=cat, amount=amt,
                description=f"{cat} for month", user_id=uid,
            ))
            
        for sm in [sm1, sm2]:
            for d in range(7):
                log_date = today - timedelta(days=d)
                db.session.add(AttendanceLog(salesman_id=sm.salesman_id, log_date=log_date, log_time=datetime.combine(log_date, time(9, 0)), status="CAME"))
                db.session.add(AttendanceLog(salesman_id=sm.salesman_id, log_date=log_date, log_time=datetime.combine(log_date, time(18, 0)), status="WENT"))
                
        # Get dynamic customer and item IDs to link to AI & CRM patterns
        dynamic_customers = Customer.query.limit(3).all()
        dynamic_items = Item.query.limit(3).all()
        
        # ── Salesman Ledger ──────────────────────────────────────
        for sm, hrs, comm, paid in [
            (sm1, 72, 450, True), (sm2, 68, 320, False),
        ]:
            db.session.add(SalesmanLedger(
                salesman_id=sm.salesman_id, period_label="May 1-15 2026",
                period_from=date(2026, 5, 1), period_to=date(2026, 5, 15),
                total_working_hrs=hrs, salary_per_hr=float(sm.salary_per_hr),
                gross_salary=hrs * float(sm.salary_per_hr),
                advance_taken=500, ai_commission_earned=comm,
                net_payable=hrs * float(sm.salary_per_hr) - 500 + comm,
                is_paid=paid, paid_date=today if paid else None,
            ))

        # ── AI Face Logs (footfall) ──────────────────────────────
        for hour in [9, 10, 10, 11, 12, 14, 15, 15, 16, 17]:
            cust = random.choice(dynamic_customers) if hour < 12 and dynamic_customers else None
            db.session.add(AiFaceLog(
                camera_id="CAM-ENTRANCE",
                detected_at=datetime.combine(today, time(hour, 15)),
                customer_id=cust.customer_id if cust else None,
                confidence_score=92.5 if hour < 12 else 78.0,
                is_fraud_alert=(hour == 16),
                action_triggered="ALERT: Match on watchlist" if hour == 16 else None,
            ))

        # ── Prescription OCR Logs ────────────────────────────────
        for conf, human, verified in [
            (95.2, False, False), (72.1, True, True), (88.5, False, False), (45.0, True, False),
        ]:
            db.session.add(PrescriptionOcrLog(
                image_url="/uploads/rx_sample.jpg",
                processed_at=now - timedelta(hours=len(str(conf))),
                confidence_score=conf,
                requires_human_verification=human,
                verified_at=now if verified else None,
                parsed_medicines=[{"name": "Dolo 650", "qty": 10}] if conf > 50 else None,
            ))

        # ── Customer Purchase Patterns (CRM) ────────────────────
        if len(dynamic_customers) >= 2 and len(dynamic_items) >= 2:
            db.session.add(CustomerPurchasePattern(
                customer_id=dynamic_customers[0].customer_id, item_id=dynamic_items[0].item_id,
                purchase_count=8, total_quantity=60, avg_quantity=7.5,
                last_purchased_date=today - timedelta(days=5),
                next_expected_date=today - timedelta(days=2),  # overdue
                is_chronic=True,
            ))
            db.session.add(CustomerPurchasePattern(
                customer_id=dynamic_customers[1].customer_id, item_id=dynamic_items[1].item_id,
                purchase_count=3, total_quantity=6, avg_quantity=2.0,
                last_purchased_date=today - timedelta(days=15),
                next_expected_date=today + timedelta(days=10),  # on track
                is_chronic=False,
            ))
            
        db.session.commit()
        print("Real data seeding complete!")

if __name__ == "__main__":
    seed()
