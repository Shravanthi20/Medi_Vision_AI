from backend import create_app
from backend.models.lookups import PaymentMode
from backend.extensions import db

app = create_app()
with app.app_context():
    for code in ['UPI', 'CARD', 'CREDIT']:
        if not PaymentMode.query.filter_by(payment_mode_code=code).first():
            db.session.add(PaymentMode(payment_mode_code=code, payment_mode_name=code))
    db.session.commit()
    print("Payment modes updated")
