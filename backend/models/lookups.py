from ..extensions import db


class BillType(db.Model):
    __tablename__ = 'bill_types'

    bill_type_id = db.Column(db.Integer, primary_key=True)
    bill_type_code = db.Column(db.String(10), nullable=False, unique=True)
    bill_type_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class PurchaseType(db.Model):
    __tablename__ = 'purchase_types'

    purchase_type_id = db.Column(db.Integer, primary_key=True)
    purchase_type_code = db.Column(db.String(10), nullable=False, unique=True)
    purchase_type_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class TxnType(db.Model):
    __tablename__ = 'txn_types'

    txn_type_id = db.Column(db.Integer, primary_key=True)
    txn_type_code = db.Column(db.String(20), nullable=False, unique=True)
    txn_type_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class PaymentMode(db.Model):
    __tablename__ = 'payment_modes'

    payment_mode_id = db.Column(db.Integer, primary_key=True)
    payment_mode_code = db.Column(db.String(10), nullable=False, unique=True)
    payment_mode_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class WantedStatus(db.Model):
    __tablename__ = 'wanted_statuses'

    wanted_status_id = db.Column(db.Integer, primary_key=True)
    status_code = db.Column(db.String(10), nullable=False, unique=True)
    status_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class ReturnReason(db.Model):
    __tablename__ = 'return_reasons'

    reason_id = db.Column(db.Integer, primary_key=True)
    reason_code = db.Column(db.String(20), nullable=False, unique=True)
    reason_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
