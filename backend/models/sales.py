from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from ..extensions import db


class SalesBill(db.Model):
    __tablename__ = 'sales_bills'

    bill_id = db.Column(db.Integer, primary_key=True)
    bill_no = db.Column(db.Integer, nullable=False)
    bill_date = db.Column(db.Date, nullable=False)
    bill_time = db.Column(db.Time, nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.doctor_id'))
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.salesman_id'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'), nullable=False)
    bill_type_id = db.Column(db.Integer, db.ForeignKey('bill_types.bill_type_id'), nullable=False)

    ocr_log_id = db.Column(db.BigInteger, db.ForeignKey('prescription_ocr_logs.ocr_log_id'))
    ai_fraud_flag = db.Column(db.Boolean, nullable=False, default=False)

    # Financials
    gross_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    sgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    igst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    round_off = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    net_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)

    is_cancelled = db.Column(db.Boolean, nullable=False, default=False)
    cancel_reason = db.Column(db.Text)
    cancelled_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'))
    cancelled_at = db.Column(db.DateTime)
    is_return = db.Column(db.Boolean, nullable=False, default=False)
    original_bill_id = db.Column(db.Integer, db.ForeignKey('sales_bills.bill_id'))
    remarks = db.Column(db.Text)
    prescription_base64 = db.Column(db.Text)  # Stores the Base64 image/PDF
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('SalesBillItem', back_populates='bill', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('bill_no', 'financial_year_id', name='bill_no_fy_unique'),
        db.CheckConstraint(
            "is_cancelled = FALSE OR (is_cancelled = TRUE AND cancel_reason IS NOT NULL)",
            name='cancel_reason_required'
        ),
    )


class SalesBillItem(db.Model):
    __tablename__ = 'sales_bill_items'

    bill_item_id = db.Column(db.BigInteger, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('sales_bills.bill_id'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    qty_sold = db.Column(db.Integer, nullable=False)
    free_qty = db.Column(db.Integer, nullable=False, default=0)

    # Computer Vision Packing Verification
    cv_verified_qty = db.Column(db.Integer, nullable=False, default=0)
    is_packing_verified = db.Column(db.Boolean, nullable=False, default=False)
    cv_camera_log_url = db.Column(db.Text)

    # Pricing snapshot
    mrp_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    purchase_rate_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price_at_sale = db.Column(db.Numeric(10, 2), nullable=False)
    discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    net_rate = db.Column(db.Numeric(10, 2), nullable=False)

    # GST snapshot
    gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)
    cgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    sgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    igst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False)

    profit_pct = db.Column(db.Numeric(6, 2), nullable=False)
    margin_flag = db.Column(db.Boolean, nullable=False, default=False)
    value = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    bill = db.relationship('SalesBill', back_populates='items')

    __table_args__ = (
        db.CheckConstraint('qty_sold > 0', name='qty_sold_positive'),
    )


class ApprovalLog(db.Model):
    __tablename__ = 'approval_logs'

    approval_id = db.Column(db.BigInteger, primary_key=True)
    override_type = db.Column(db.String(20), nullable=False)
    ref_type = db.Column(db.String(30), nullable=False)
    ref_id = db.Column(db.BigInteger, nullable=False)
    requested_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    approved_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    requested_value = db.Column(db.Numeric(10, 2))
    approved_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("override_type IN ('MARGIN','DISCOUNT','CANCEL')", name='override_type_check'),
    )


class PrescriptionRegister(db.Model):
    __tablename__ = 'prescription_register'

    rx_id = db.Column(db.BigInteger, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('sales_bills.bill_id'), nullable=False)
    bill_item_id = db.Column(db.BigInteger, db.ForeignKey('sales_bill_items.bill_item_id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.doctor_id'))
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    batch_no = db.Column(db.String(30), nullable=False)
    manufacturer_name = db.Column(db.String(150), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    dispenser_sign = db.Column(db.String(100))
    rx_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SalesReturn(db.Model):
    __tablename__ = 'sales_returns'

    sales_return_id = db.Column(db.Integer, primary_key=True)
    return_no = db.Column(db.Integer, nullable=False)
    return_date = db.Column(db.Date, nullable=False)
    financial_year_id = db.Column(db.Integer, db.ForeignKey('financial_years.financial_year_id'), nullable=False)
    original_bill_id = db.Column(db.Integer, db.ForeignKey('sales_bills.bill_id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'))
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.salesman_id'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    reason_id = db.Column(db.Integer, db.ForeignKey('return_reasons.reason_id'), nullable=False)
    remarks = db.Column(db.Text)
    total_return_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    sgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    igst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    net_return_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    return_items = db.relationship('SalesReturnItem', back_populates='sales_return', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('return_no', 'financial_year_id'),
    )


class SalesReturnItem(db.Model):
    __tablename__ = 'sales_return_items'

    return_item_id = db.Column(db.BigInteger, primary_key=True)
    sales_return_id = db.Column(db.Integer, db.ForeignKey('sales_returns.sales_return_id'), nullable=False)
    original_bill_item_id = db.Column(db.BigInteger, db.ForeignKey('sales_bill_items.bill_item_id'), nullable=False)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    qty_returned = db.Column(db.Integer, nullable=False)
    return_rate = db.Column(db.Numeric(10, 2), nullable=False)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    return_value = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    sales_return = db.relationship('SalesReturn', back_populates='return_items')

    __table_args__ = (
        db.CheckConstraint('qty_returned > 0', name='qty_returned_positive'),
    )


class ReceiptPayment(db.Model):
    __tablename__ = 'receipts_payments'

    receipt_id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    bill_id = db.Column(db.Integer, db.ForeignKey('sales_bills.bill_id'))
    receipt_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_mode_id = db.Column(db.Integer, db.ForeignKey('payment_modes.payment_mode_id'), nullable=False)
    cheque_no = db.Column(db.String(30))
    bank_name = db.Column(db.String(100))
    upi_ref = db.Column(db.String(50))
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='receipt_amount_positive'),
    )
