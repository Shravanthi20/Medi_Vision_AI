from backend import create_app
from backend.models.sales import SalesBill, ReceiptPayment
from backend.models.lookups import PaymentMode
from backend.extensions import db
from datetime import datetime

app = create_app()
with app.app_context():
    cash_pm = PaymentMode.query.filter_by(payment_mode_code='CASH').first()
    if not cash_pm:
        print("CASH payment mode not found!")
        exit()

    # Find bills with customers that don't have a linked payment
    bills = SalesBill.query.filter(SalesBill.customer_id.isnot(None), SalesBill.is_cancelled.is_(False)).all()
    count = 0
    for bill in bills:
        # Check if payment already exists for this bill
        existing = ReceiptPayment.query.filter_by(bill_id=bill.bill_id).first()
        if not existing:
            payment = ReceiptPayment(
                customer_id=bill.customer_id,
                bill_id=bill.bill_id,
                receipt_date=bill.bill_date,
                amount=bill.net_amount,
                payment_mode_id=cash_pm.payment_mode_id,
                user_id=bill.user_id,
                remarks=f"System reconciliation: Auto-payment for past bill #{bill.bill_no}"
            )
            db.session.add(payment)
            count += 1
    
    db.session.commit()
    print(f"Created {count} missing payment records.")
