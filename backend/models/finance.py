"""Domain E — GST / Finance: gst_transactions, expenses."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from ..extensions import db


class GstTransaction(db.Model):
    __tablename__ = 'gst_transactions'

    gst_txn_id = db.Column(db.BigInteger, primary_key=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    txn_type_id = db.Column(db.Integer, db.ForeignKey('txn_types.txn_type_id'), nullable=False)
    ref_id = db.Column(db.Integer, nullable=False)
    ref_type = db.Column(db.String(30), nullable=False)
    txn_date = db.Column(db.Date, nullable=False)
    hsn_id = db.Column(db.Integer, db.ForeignKey('hsn_codes.hsn_id'), nullable=False)
    gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)
    taxable_value = db.Column(db.Numeric(12, 2), nullable=False)
    cgst = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    sgst = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    igst = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    is_interstate = db.Column(db.Boolean, nullable=False, default=False)
    party_gstin = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Expense(db.Model):
    __tablename__ = 'expenses'

    expense_id = db.Column(db.Integer, primary_key=True)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    expense_category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.Text)
    is_gst_applicable = db.Column(db.Boolean, nullable=False, default=False)
    gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'))
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    voucher_no = db.Column(db.String(30))
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='expense_amount_positive'),
    )
