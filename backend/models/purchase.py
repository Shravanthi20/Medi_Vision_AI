"""Domain C — Purchase: purchase_invoices, purchase_invoice_items,
purchase_returns, purchase_return_items, purchase_payments."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from ..extensions import db


class PurchaseInvoice(db.Model):
    __tablename__ = 'purchase_invoices'

    purchase_id = db.Column(db.Integer, primary_key=True)
    ref_no = db.Column(db.String(20), nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'), nullable=False)
    invoice_no = db.Column(db.String(50))
    invoice_date = db.Column(db.Date)
    ac_date = db.Column(db.Date)
    purchase_type_id = db.Column(db.Integer, db.ForeignKey('purchase_types.purchase_type_id'), nullable=False)
    gross_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    sgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    igst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    round_off = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    net_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    ac_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    line_items = db.relationship('PurchaseInvoiceItem', back_populates='invoice', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('ref_no', 'financial_year_id'),
    )


class PurchaseInvoiceItem(db.Model):
    __tablename__ = 'purchase_invoice_items'

    purchase_item_id = db.Column(db.BigInteger, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'))
    pkg_qty = db.Column(db.Integer, nullable=False, default=0)
    free_qty = db.Column(db.Integer, nullable=False, default=0)
    offer_qty = db.Column(db.Integer, nullable=False, default=0)
    purchase_rate_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)
    mrp_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)
    net_rate = db.Column(db.Numeric(10, 2), nullable=False)
    net_rate_for = db.Column(db.Numeric(10, 2))
    p_tax_code = db.Column(db.String(4))
    stax_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)
    cgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    sgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    igst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    profit_pct = db.Column(db.Numeric(6, 2))
    value = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    invoice = db.relationship('PurchaseInvoice', back_populates='line_items')


class PurchaseReturn(db.Model):
    __tablename__ = 'purchase_returns'

    purchase_return_id = db.Column(db.Integer, primary_key=True)
    return_date = db.Column(db.Date, nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    original_purchase_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    reason_id = db.Column(db.Integer, db.ForeignKey('return_reasons.reason_id'), nullable=False)
    remarks = db.Column(db.Text)
    net_return_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    sgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    igst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    return_items = db.relationship('PurchaseReturnItem', back_populates='purchase_return', lazy='dynamic')


class PurchaseReturnItem(db.Model):
    __tablename__ = 'purchase_return_items'

    purchase_return_item_id = db.Column(db.BigInteger, primary_key=True)
    purchase_return_id = db.Column(db.Integer, db.ForeignKey('purchase_returns.purchase_return_id'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    qty_returned = db.Column(db.Integer, nullable=False)
    return_rate = db.Column(db.Numeric(10, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    return_value = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    purchase_return = db.relationship('PurchaseReturn', back_populates='return_items')

    __table_args__ = (
        db.CheckConstraint('qty_returned > 0', name='pur_qty_returned_positive'),
    )


class PurchasePayment(db.Model):
    __tablename__ = 'purchase_payments'

    payment_id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase_invoices.purchase_id'))
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_mode_id = db.Column(db.Integer, db.ForeignKey('payment_modes.payment_mode_id'), nullable=False)
    cheque_no = db.Column(db.String(30))
    bank_name = db.Column(db.String(100))
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='pur_payment_amount_positive'),
    )
