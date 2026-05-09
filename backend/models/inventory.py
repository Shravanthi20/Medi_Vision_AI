from datetime import datetime
from ..extensions import db


class StockBatch(db.Model):
    __tablename__ = 'stock_batches'

    stock_batch_id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    batch_no = db.Column(db.String(30), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.location_id'), nullable=False)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.manufacturer_id'), nullable=False)
    mrp = db.Column(db.Numeric(10, 2), nullable=False)
    purchase_rate = db.Column(db.Numeric(10, 2), nullable=False)
    opening_qty = db.Column(db.Integer, nullable=False, default=0)
    current_qty = db.Column(db.Integer, nullable=False, default=0)
    total_stock = db.Column(db.Integer, nullable=False, default=0)

    # ML Intelligence
    is_dead_stock = db.Column(db.Boolean, nullable=False, default=False)
    sell_through_rate = db.Column(db.Numeric(5, 2))

    is_non_movable = db.Column(db.Boolean, nullable=False, default=False)
    last_sale_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('item_id', 'batch_no', 'location_id', name='batch_unique'),
        db.CheckConstraint('current_qty >= 0', name='stock_non_negative'),
    )


class StockLedger(db.Model):
    __tablename__ = 'stock_ledger'

    ledger_id = db.Column(db.BigInteger, primary_key=True)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    txn_type_id = db.Column(db.Integer, db.ForeignKey('txn_types.txn_type_id'), nullable=False)
    txn_date = db.Column(db.Date, nullable=False)
    qty_in = db.Column(db.Integer, nullable=False, default=0)
    qty_out = db.Column(db.Integer, nullable=False, default=0)
    balance_qty = db.Column(db.Integer, nullable=False)
    ref_type = db.Column(db.String(30), nullable=False)
    ref_id = db.Column(db.BigInteger, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            '(qty_in > 0 AND qty_out = 0) OR (qty_out > 0 AND qty_in = 0)',
            name='one_direction'
        ),
    )


class ExpiryAlert(db.Model):
    __tablename__ = 'expiry_alerts'

    alert_id = db.Column(db.Integer, primary_key=True)
    stock_batch_id = db.Column(db.Integer, db.ForeignKey('stock_batches.stock_batch_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    days_to_expiry = db.Column(db.Integer, nullable=False)
    qty_at_risk = db.Column(db.Integer, nullable=False)
    alert_level = db.Column(db.String(10), nullable=False)  # CRITICAL | WARN | INFO
    is_resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("alert_level IN ('CRITICAL','WARN','INFO')", name='alert_level_check'),
    )
