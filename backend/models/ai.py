from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from ..extensions import db


class AiFaceLog(db.Model):
    __tablename__ = 'ai_face_logs'

    log_id = db.Column(db.BigInteger, primary_key=True)
    camera_id = db.Column(db.String(50), nullable=False)
    detected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'))
    confidence_score = db.Column(db.Numeric(5, 2))
    action_triggered = db.Column(db.String(100))
    is_fraud_alert = db.Column(db.Boolean, nullable=False, default=False)
    face_snapshot_url = db.Column(db.Text)


class PrescriptionOcrLog(db.Model):
    __tablename__ = 'prescription_ocr_logs'

    ocr_log_id = db.Column(db.BigInteger, primary_key=True)
    image_url = db.Column(db.Text, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    raw_extracted_text = db.Column(JSONB)
    parsed_medicines = db.Column(JSONB)
    confidence_score = db.Column(db.Numeric(5, 2))
    verified_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'))
    verified_at = db.Column(db.DateTime)
    requires_human_verification = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CustomerPurchasePattern(db.Model):
    __tablename__ = 'customer_purchase_patterns'

    pattern_id = db.Column(db.BigInteger, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.category_id'))
    combination_id = db.Column(db.Integer, db.ForeignKey('combinations.combination_id'))
    purchase_count = db.Column(db.Integer, nullable=False, default=1)
    last_purchased_date = db.Column(db.Date, nullable=False)
    next_expected_date = db.Column(db.Date)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('customer_id', 'category_id', 'combination_id'),
    )


class SeleniumOrderLog(db.Model):
    __tablename__ = 'selenium_order_logs'

    selenium_log_id = db.Column(db.BigInteger, primary_key=True)
    wanted_id = db.Column(db.Integer, db.ForeignKey('wanted_list.wanted_id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default='RUNNING')
    error_message = db.Column(db.Text)
    screenshot_url = db.Column(db.Text)
    order_ref_no = db.Column(db.String(100))

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('RUNNING','SUCCESS','FAILED','CANCELLED')",
            name='selenium_status_check'
        ),
    )


class WantedList(db.Model):
    __tablename__ = 'wanted_list'

    wanted_id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'))
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.manufacturer_id'))
    required_qty = db.Column(db.Integer, nullable=False, default=1)
    min_qty = db.Column(db.Integer)
    max_qty = db.Column(db.Integer)
    last_purchase_rate = db.Column(db.Numeric(10, 2))

    # ML & Automation
    ml_forecasted_qty = db.Column(db.Integer)
    auto_order_status = db.Column(db.String(20), nullable=False, default='PENDING')
    selenium_log_id = db.Column(db.BigInteger, db.ForeignKey('selenium_order_logs.selenium_log_id', use_alter=True))

    w_date = db.Column(db.Date, nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('wanted_statuses.wanted_status_id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "auto_order_status IN ('PENDING','APPROVED','SCRAPING','ORDERED','FAILED')",
            name='auto_order_status_check'
        ),
    )
