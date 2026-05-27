"""Domain F — Compliance: expiry_returns, expiry_return_items, license_documents."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from ..extensions import db


class ExpiryReturn(db.Model):
    __tablename__ = 'expiry_returns'

    expiry_return_id = db.Column(db.Integer, primary_key=True)
    return_no = db.Column(db.String(30), nullable=False, unique=True)
    return_date = db.Column(db.Date, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)

    # Status: DRAFT → DISPATCHED → CREDIT_NOTE_RECEIVED → CLOSED
    status = db.Column(db.String(30), nullable=False, default='DRAFT')

    total_qty = db.Column(db.Integer, nullable=False, default=0)
    total_value = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    credit_note_no = db.Column(db.String(50))
    credit_note_date = db.Column(db.Date)
    credit_note_amount = db.Column(db.Numeric(12, 2))

    remarks = db.Column(db.Text)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('ExpiryReturnItem', back_populates='expiry_return', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('DRAFT','DISPATCHED','CREDIT_NOTE_RECEIVED','CLOSED')",
            name='expiry_return_status_check'
        ),
    )


class ExpiryReturnItem(db.Model):
    __tablename__ = 'expiry_return_items'

    expiry_return_item_id = db.Column(db.BigInteger, primary_key=True)
    expiry_return_id = db.Column(db.Integer, db.ForeignKey('expiry_returns.expiry_return_id', ondelete='CASCADE'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)

    batch_no = db.Column(db.String(30), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    qty_returned = db.Column(db.Integer, nullable=False)
    purchase_rate = db.Column(db.Numeric(10, 2), nullable=False)
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    return_value = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    expiry_return = db.relationship('ExpiryReturn', back_populates='items')

    __table_args__ = (
        db.CheckConstraint('qty_returned > 0', name='expiry_return_qty_positive'),
    )


class LicenseDocument(db.Model):
    __tablename__ = 'license_documents'

    license_id = db.Column(db.Integer, primary_key=True)

    # Type: DRUG_LICENSE_RETAIL / DRUG_LICENSE_WHOLESALE / FSSAI / GST / SHOP_ACT / OTHER
    license_type = db.Column(db.String(50), nullable=False)
    license_name = db.Column(db.String(150), nullable=False)
    license_no = db.Column(db.String(100), nullable=False)
    issuing_authority = db.Column(db.String(150))

    issued_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date, nullable=False)

    # Alert thresholds (days before expiry to alert)
    alert_90 = db.Column(db.Boolean, nullable=False, default=True)
    alert_60 = db.Column(db.Boolean, nullable=False, default=True)
    alert_30 = db.Column(db.Boolean, nullable=False, default=True)

    # Document vault
    doc_url = db.Column(db.Text)
    notes = db.Column(db.Text)

    renewal_cost = db.Column(db.Numeric(10, 2))
    renewal_contact = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
