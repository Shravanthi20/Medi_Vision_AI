"""
Seed script — populates demo data for all 17 reports.
Run:  python seed_demo_data.py
"""
import sys, os, uuid
from datetime import datetime, date, time, timedelta
from decimal import Decimal

# Setup Flask app context
sys.path.insert(0, os.path.dirname(__file__))
from backend.app_factory import create_app
from backend.extensions import db

app = create_app()

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
            SalesBill, SalesBillItem, BillingVoucher, PrescriptionRegister,
        )
        from backend.models.purchase import PurchaseInvoice, PurchaseInvoiceItem, PurchasePayment
        from backend.models.finance import Expense
        from backend.models.hr import Salesman, AttendanceLog, SalesmanLedger
        from backend.models.ai import AiFaceLog, PrescriptionOcrLog, CustomerPurchasePattern

        # Skip if data already exists
        if SalesBill.query.first():
            print("[SKIP] Data already exists. Skipping seed.")
            return

        today = date.today()
        now = datetime.now()

        # ── Lookups ──────────────────────────────────────────────
        def get_or_create(model, defaults, **kwargs):
            obj = model.query.filter_by(**kwargs).first()
            if obj:
                return obj
            obj = model(**kwargs, **defaults)
            db.session.add(obj)
            db.session.flush()
            return obj

        role = get_or_create(Role, {"can_bill": True, "can_manage_system": True}, role_name="Admin")
        bt = get_or_create(BillType, {"bill_type_name": "Regular"}, bill_type_code="REG")
        pt = get_or_create(PurchaseType, {"purchase_type_name": "Regular"}, purchase_type_code="REG")
        get_or_create(TxnType, {"txn_type_name": "Sale"}, txn_type_code="SALE")
        pm_cash = get_or_create(PaymentMode, {"payment_mode_name": "Cash"}, payment_mode_code="CASH")
        pm_upi = get_or_create(PaymentMode, {"payment_mode_name": "UPI"}, payment_mode_code="UPI")
        get_or_create(WantedStatus, {"status_name": "Pending"}, status_code="PENDING")
        get_or_create(ReturnReason, {"reason_name": "Expired"}, reason_code="EXPIRED")
        db.session.flush()

        # ── Financial Year ───────────────────────────────────────
        fy = get_or_create(FinancialYear, {
            "start_date": date(2025, 4, 1), "end_date": date(2026, 3, 31), "is_active": True
        }, fy_label="2025-2026")

        # ── GST Slabs ────────────────────────────────────────────
        gst5 = get_or_create(GstSlab, {
            "slab_rate_pct": 5, "cgst_pct": 2.5, "sgst_pct": 2.5, "igst_pct": 0,
            "effective_from": date(2017, 7, 1)
        }, slab_code="G05")
        gst12 = get_or_create(GstSlab, {
            "slab_rate_pct": 12, "cgst_pct": 6, "sgst_pct": 6, "igst_pct": 0,
            "effective_from": date(2017, 7, 1)
        }, slab_code="G12")
        gst18 = get_or_create(GstSlab, {
            "slab_rate_pct": 18, "cgst_pct": 9, "sgst_pct": 9, "igst_pct": 0,
            "effective_from": date(2017, 7, 1)
        }, slab_code="G18")

        # ── HSN Codes ────────────────────────────────────────────
        hsn1 = get_or_create(HsnCode, {"description": "Medicaments", "gst_slab_id": gst5.gst_slab_id}, hsn_code="30049099")
        hsn2 = get_or_create(HsnCode, {"description": "Surgical", "gst_slab_id": gst12.gst_slab_id}, hsn_code="90189090")
        hsn3 = get_or_create(HsnCode, {"description": "Cosmetics", "gst_slab_id": gst18.gst_slab_id}, hsn_code="33049990")

        # ── Combination, Category, UOM ───────────────────────────
        combo = get_or_create(Combination, {"generic_name": "Paracetamol"}, combination_name="Paracetamol 500mg")
        cat_tab = get_or_create(ProductCategory, {}, category_name="Tablets")
        cat_syr = get_or_create(ProductCategory, {}, category_name="Syrups")
        cat_cos = get_or_create(ProductCategory, {}, category_name="Cosmetics")
        uom = get_or_create(UnitOfMeasure, {"uom_name": "Strip"}, uom_code="STRIP")

        # ── Manufacturers ────────────────────────────────────────
        mfr1 = get_or_create(Manufacturer, {"manufacturer_name": "Cipla Ltd"}, manufacturer_code="CIPLA")
        mfr2 = get_or_create(Manufacturer, {"manufacturer_name": "Sun Pharma"}, manufacturer_code="SUN")

        # ── Location ─────────────────────────────────────────────
        loc = get_or_create(Location, {"location_name": "Main Store", "is_default": True}, location_code="MAIN")

        # ── Suppliers ────────────────────────────────────────────
        sup1 = get_or_create(Supplier, {
            "supplier_name": "MedPlus Distributors", "phone": "9876500001",
            "gstin": "33AABCU9603R1ZM", "manufacturer_id": mfr1.manufacturer_id
        }, supplier_code="SUP001")
        sup2 = get_or_create(Supplier, {
            "supplier_name": "HealthCare Traders", "phone": "9876500002",
            "gstin": "33AABCU9604R1ZN", "manufacturer_id": mfr2.manufacturer_id
        }, supplier_code="SUP002")

        # ── Doctors ──────────────────────────────────────────────
        doc1 = get_or_create(Doctor, {
            "qualification": "MBBS", "phone": "9876500010"
        }, doctor_name="Dr. Ramesh Kumar")
        doc2 = get_or_create(Doctor, {
            "qualification": "MD", "phone": "9876500011"
        }, doctor_name="Dr. Priya Sharma")

        # ── Customers ───────────────────────────────────────────
        c1 = get_or_create(Customer, {
            "phone": "9876543210", "doctor_id": doc1.doctor_id, "is_chronic_patient": True,
            "total_spend": 4500, "total_visits": 12
        }, customer_name="Rajesh Selvam")
        c2 = get_or_create(Customer, {
            "phone": "9876543211", "doctor_id": doc2.doctor_id,
            "total_spend": 2200, "total_visits": 5
        }, customer_name="Lakshmi Devi")
        c3 = get_or_create(Customer, {
            "phone": "9876543212", "total_spend": 800, "total_visits": 2
        }, customer_name="Arun Prakash")

        # ── Items (3 medicines) ──────────────────────────────────
        items_data = [
            ("MED001", "Dolo 650 (Paracetamol)", mfr1, cat_tab, hsn1, gst5, combo, 35, 22, 10, 100),
            ("MED002", "Augmentin 625 Duo", mfr2, cat_tab, hsn1, gst5, None, 180, 120, 5, 50),
            ("MED003", "Benadryl Cough Syrup", mfr1, cat_syr, hsn2, gst12, None, 120, 78, 8, 40),
        ]
        items = []
        for iid, name, mfr, cat, hsn, gst, cmb, mrp, pr, reorder, maxs in items_data:
            itm = get_or_create(Item, {
                "item_name": name, "manufacturer_id": mfr.manufacturer_id,
                "category_id": cat.category_id, "hsn_id": hsn.hsn_id, "uom_id": uom.uom_id,
                "purchase_gst_slab_id": gst.gst_slab_id, "sales_gst_slab_id": gst.gst_slab_id,
                "combination_id": cmb.combination_id if cmb else None,
                "default_mrp": mrp, "default_selling_price": mrp,
                "reorder_level": reorder, "max_stock": maxs,
            }, item_id=iid)
            items.append(itm)
        db.session.flush()

        # ── User ─────────────────────────────────────────────────
        user_id = uuid.uuid4()
        user = get_or_create(User, {
            "name": "Admin User", "password_hash": "demo",
            "role_id": role.role_id, "user_id": user_id
        }, username="admin")
        uid = user.user_id

        # ── Salesmen ─────────────────────────────────────────────
        sm1 = get_or_create(Salesman, {
            "salesman_name": "Karthik R", "phone": "9876500020",
            "role_id": role.role_id, "salary_per_hr": 80
        }, salesman_code="SM001")
        sm2 = get_or_create(Salesman, {
            "salesman_name": "Divya S", "phone": "9876500021",
            "role_id": role.role_id, "salary_per_hr": 75
        }, salesman_code="SM002")
        db.session.flush()

        # ── Stock Batches (some near-expiry, some healthy) ───────
        batches = []
        batch_data = [
            ("MED001", "B001", today + timedelta(days=365), 100, 35, 22, mfr1),
            ("MED001", "B002", today + timedelta(days=20), 15, 35, 22, mfr1),   # near expiry
            ("MED002", "B003", today + timedelta(days=180), 30, 180, 120, mfr2),
            ("MED002", "B004", today - timedelta(days=5), 8, 180, 120, mfr2),   # expired
            ("MED003", "B005", today + timedelta(days=60), 25, 120, 78, mfr1),
            ("MED003", "B006", today + timedelta(days=400), 50, 120, 78, mfr1),
        ]
        for iid, bno, exp, qty, mrp, pr, mfr in batch_data:
            sb = StockBatch(
                item_id=iid, batch_no=bno, expiry_date=exp,
                location_id=loc.location_id, manufacturer_id=mfr.manufacturer_id,
                mrp=mrp, purchase_rate=pr, opening_qty=qty, current_qty=qty, total_stock=qty,
            )
            db.session.add(sb)
            batches.append(sb)
        db.session.flush()

        # ── Purchase Invoices ────────────────────────────────────
        for i, (sup, inv_date) in enumerate([
            (sup1, today - timedelta(days=30)),
            (sup2, today - timedelta(days=15)),
            (sup1, today - timedelta(days=3)),
        ], 1):
            pi = PurchaseInvoice(
                ref_no=f"PI-{i}", financial_year_id=fy.financial_year_id,
                supplier_id=sup.supplier_id, location_id=loc.location_id,
                invoice_no=f"INV-2026-{i:03d}", invoice_date=inv_date,
                purchase_type_id=pt.purchase_type_id, user_id=uid,
                gross_amount=3000+i*500, discount_amount=100,
                taxable_amount=2900+i*500,
                cgst_amount=72.5+i*12, sgst_amount=72.5+i*12, igst_amount=0,
                net_amount=3045+i*524, ac_amount=3045+i*524,
            )
            db.session.add(pi)
            db.session.flush()
            # One line item per invoice
            pii = PurchaseInvoiceItem(
                purchase_id=pi.purchase_id, item_id=items[i-1].item_id,
                stock_batch_id=batches[i-1].stock_batch_id,
                pkg_qty=50, purchase_rate_at_purchase=22+i*30, mrp_at_purchase=35+i*50,
                net_rate=22+i*30, gst_slab_id=gst5.gst_slab_id,
                cgst_pct=2.5, sgst_pct=2.5, igst_pct=0,
                gst_amount=72.5+i*12, value=2900+i*500,
            )
            db.session.add(pii)

        # ── Purchase Payments (partial) ──────────────────────────
        pp1 = PurchasePayment(
            supplier_id=sup1.supplier_id, payment_date=today - timedelta(days=20),
            amount=2500, payment_mode_id=pm_cash.payment_mode_id, user_id=uid,
        )
        pp2 = PurchasePayment(
            supplier_id=sup2.supplier_id, payment_date=today - timedelta(days=10),
            amount=1800, payment_mode_id=pm_upi.payment_mode_id, user_id=uid,
        )
        db.session.add_all([pp1, pp2])
        db.session.flush()

        # ── Sales Bills (6 bills over last week) ─────────────────
        bill_configs = [
            (today - timedelta(days=5), time(9, 30), c1, sm1, "MED001", batches[0], 10, "cash"),
            (today - timedelta(days=5), time(11, 0), c2, sm1, "MED002", batches[2], 2, "upi"),
            (today - timedelta(days=3), time(10, 15), c3, sm2, "MED003", batches[4], 3, "cash"),
            (today - timedelta(days=2), time(14, 0), c1, sm2, "MED001", batches[0], 5, "cash"),
            (today - timedelta(days=1), time(9, 45), c2, sm1, "MED002", batches[2], 1, "upi"),
            (today, time(10, 0), c3, sm1, "MED003", batches[5], 4, "cash"),
        ]
        for bill_no, (bdate, btime, cust, sm, iid, batch, qty, pmode) in enumerate(bill_configs, 1):
            mrp = float(batch.mrp)
            pr = float(batch.purchase_rate)
            gross = mrp * qty
            disc = round(gross * 0.05, 2)
            taxable = gross - disc
            cgst = round(taxable * 0.025, 2)
            sgst = cgst
            net = round(taxable + cgst + sgst, 2)

            bill = SalesBill(
                bill_no=bill_no, bill_date=bdate, bill_time=btime,
                financial_year_id=fy.financial_year_id,
                customer_id=cust.customer_id, salesman_id=sm.salesman_id,
                user_id=uid, location_id=loc.location_id, bill_type_id=bt.bill_type_id,
                gross_amount=gross, discount_pct=5, discount_amount=disc,
                taxable_amount=taxable, cgst_amount=cgst, sgst_amount=sgst,
                igst_amount=0, net_amount=net, payment_mode=pmode,
            )
            db.session.add(bill)
            db.session.flush()

            bi = SalesBillItem(
                bill_id=bill.bill_id, stock_batch_id=batch.stock_batch_id,
                item_id=iid, qty_sold=qty,
                mrp_at_sale=mrp, purchase_rate_at_sale=pr, selling_price_at_sale=mrp,
                discount_pct=5, net_rate=round(mrp * 0.95, 2),
                gst_slab_id=gst5.gst_slab_id, cgst_pct=2.5, sgst_pct=2.5, igst_pct=0,
                gst_amount=cgst + sgst, profit_pct=round((mrp - pr) / mrp * 100, 2),
                margin_flag=False, value=net,
            )
            db.session.add(bi)

            # Billing voucher for daily sales
            bv = BillingVoucher(
                voucher_type="RECEIPT", voucher_no=f"RV-{bill_no}",
                voucher_date=bdate, payment_type=pmode.capitalize(),
                amount=net, user_id=uid, linked_bill_id=bill.bill_id,
            )
            db.session.add(bv)
        db.session.flush()

        # ── Expenses ─────────────────────────────────────────────
        for cat, amt, d in [
            ("Electricity", 2500, 5), ("Rent", 15000, 1), ("Courier", 350, 3),
        ]:
            db.session.add(Expense(
                financial_year_id=fy.financial_year_id,
                expense_date=today - timedelta(days=d),
                expense_category=cat, amount=amt,
                description=f"{cat} for May 2026", user_id=uid,
            ))

        # ── Attendance Logs (last 7 days for both salesmen) ──────
        for sm in [sm1, sm2]:
            for d in range(7):
                log_date = today - timedelta(days=d)
                came = datetime.combine(log_date, time(9, 0))
                went = datetime.combine(log_date, time(18, 0))
                db.session.add(AttendanceLog(
                    salesman_id=sm.salesman_id, log_date=log_date,
                    log_time=came, status="CAME",
                ))
                db.session.add(AttendanceLog(
                    salesman_id=sm.salesman_id, log_date=log_date,
                    log_time=went, status="WENT",
                ))

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
            db.session.add(AiFaceLog(
                camera_id="CAM-ENTRANCE",
                detected_at=datetime.combine(today, time(hour, 15)),
                customer_id=c1.customer_id if hour < 12 else None,
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
        db.session.add(CustomerPurchasePattern(
            customer_id=c1.customer_id, item_id="MED001",
            purchase_count=8, total_quantity=60, avg_quantity=7.5,
            last_purchased_date=today - timedelta(days=5),
            next_expected_date=today - timedelta(days=2),  # overdue
            is_chronic=True,
        ))
        db.session.add(CustomerPurchasePattern(
            customer_id=c2.customer_id, item_id="MED002",
            purchase_count=3, total_quantity=6, avg_quantity=2.0,
            last_purchased_date=today - timedelta(days=15),
            next_expected_date=today + timedelta(days=10),  # on track
            is_chronic=False,
        ))

        db.session.commit()
        print("[OK] Demo data seeded successfully!")
        print("   - 3 customers, 2 doctors, 2 suppliers")
        print("   - 3 medicines, 6 stock batches (incl. expired & near-expiry)")
        print("   - 6 sales bills, 3 purchase invoices, 3 expenses")
        print("   - 7 days attendance, 2 salary ledger entries")
        print("   - 10 face logs, 4 OCR logs, 2 CRM patterns")
        print("")
        print("[READY] All 17 reports should now show data!")


if __name__ == "__main__":
    seed()
