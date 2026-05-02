from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from ..extensions import db

class Role(db.Model):
    __tablename__ = 'roles'

    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), nullable=False, unique=True)
    can_bill = db.Column(db.Boolean, nullable=False, default=True)
    can_cancel_bill = db.Column(db.Boolean, nullable=False, default=False)
    can_view_purchase = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_system = db.Column(db.Boolean, nullable=False, default=False)
    can_approve_override = db.Column(db.Boolean, nullable=False, default=False)
    max_discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = db.relationship('User', back_populates='role')


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.salesman_id'), nullable=True) # Will be resolved when salesmen table is created
    is_super_admin = db.Column(db.Boolean, nullable=False, default=False)
    custom_max_discount_pct = db.Column(db.Numeric(5, 2))
    custom_can_cancel_bill = db.Column(db.Boolean)
    custom_can_approve_override = db.Column(db.Boolean)
    machine_code = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = db.relationship('Role', back_populates='users')


class FinancialYear(db.Model):
    __tablename__ = 'financial_years'

    financial_year_id = db.Column(db.Integer, primary_key=True)
    fy_label = db.Column(db.String(9), nullable=False, unique=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('end_date > start_date', name='fy_date_check'),
    )


class GstSlab(db.Model):
    __tablename__ = 'gst_slabs'

    gst_slab_id = db.Column(db.Integer, primary_key=True)
    slab_code = db.Column(db.String(4), nullable=False)
    slab_rate_pct = db.Column(db.Numeric(5, 2), nullable=False)
    cgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    sgst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    igst_pct = db.Column(db.Numeric(5, 2), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('cgst_pct + sgst_pct = slab_rate_pct OR igst_pct = slab_rate_pct', name='gst_rate_check'),
    )


class HsnCode(db.Model):
    __tablename__ = 'hsn_codes'

    hsn_id = db.Column(db.Integer, primary_key=True)
    hsn_code = db.Column(db.String(8), nullable=False, unique=True)
    description = db.Column(db.Text)
    gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Combination(db.Model):
    __tablename__ = 'combinations'

    combination_id = db.Column(db.Integer, primary_key=True)
    combination_name = db.Column(db.String(200), nullable=False, unique=True)
    generic_name = db.Column(db.String(200))
    drug_class = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Manufacturer(db.Model):
    __tablename__ = 'manufacturers'

    manufacturer_id = db.Column(db.Integer, primary_key=True)
    manufacturer_code = db.Column(db.String(10), nullable=False, unique=True)
    manufacturer_name = db.Column(db.String(150), nullable=False)
    gstin = db.Column(db.String(15))
    state_code = db.Column(db.String(2))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductCategory(db.Model):
    __tablename__ = 'product_categories'

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UnitOfMeasure(db.Model):
    __tablename__ = 'units_of_measure'

    uom_id = db.Column(db.Integer, primary_key=True)
    uom_code = db.Column(db.String(10), nullable=False, unique=True)
    uom_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Item(db.Model):
    __tablename__ = 'items'

    item_id = db.Column(db.String(10), primary_key=True)
    item_name = db.Column(db.String(200), nullable=False)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.manufacturer_id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.category_id'), nullable=False)
    combination_id = db.Column(db.Integer, db.ForeignKey('combinations.combination_id'))
    hsn_id = db.Column(db.Integer, db.ForeignKey('hsn_codes.hsn_id'), nullable=False)
    uom_id = db.Column(db.Integer, db.ForeignKey('units_of_measure.uom_id'), nullable=False)

    purchase_packing = db.Column(db.String(50))
    sales_packing = db.Column(db.String(50))
    conversion_factor = db.Column(db.Integer, nullable=False, default=1)

    cv_bounding_box_ratio = db.Column(db.Numeric(5, 2))
    is_refrigerated = db.Column(db.Boolean, nullable=False, default=False)
    rack_number = db.Column(db.String(20))

    purchase_gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)
    sales_gst_slab_id = db.Column(db.Integer, db.ForeignKey('gst_slabs.gst_slab_id'), nullable=False)

    default_mrp = db.Column(db.Numeric(10, 2))
    default_selling_price = db.Column(db.Numeric(10, 2))
    default_discount_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    offer_buy_qty = db.Column(db.Integer, nullable=False, default=0)
    offer_free_qty = db.Column(db.Integer, nullable=False, default=0)

    min_margin_pct = db.Column(db.Numeric(5, 2), nullable=False, default=0.10)
    reorder_level = db.Column(db.Integer, nullable=False, default=0)
    max_stock = db.Column(db.Integer)

    is_schedule_h = db.Column(db.Boolean, nullable=False, default=False)
    is_narcotic = db.Column(db.Boolean, nullable=False, default=False)
    requires_rx = db.Column(db.Boolean, nullable=False, default=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Location(db.Model):
    __tablename__ = 'locations'

    location_id = db.Column(db.Integer, primary_key=True)
    location_code = db.Column(db.String(10), nullable=False, unique=True)
    location_name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    supplier_id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(20), nullable=False, unique=True)
    supplier_name = db.Column(db.String(150), nullable=False)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.manufacturer_id'))
    gstin = db.Column(db.String(15))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    credit_limit = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    credit_days = db.Column(db.Integer, nullable=False, default=0)
    
    b2b_portal_url = db.Column(db.Text)
    b2b_credentials = db.Column(JSONB)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierItem(db.Model):
    __tablename__ = 'supplier_items'

    supplier_item_id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id'), nullable=False)
    item_id = db.Column(db.String(10), db.ForeignKey('items.item_id'), nullable=False)
    preferred_flag = db.Column(db.Boolean, nullable=False, default=False)
    last_purchase_rate = db.Column(db.Numeric(10, 2))
    last_purchase_date = db.Column(db.Date)
    min_order_qty = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('supplier_id', 'item_id'),
    )


class Doctor(db.Model):
    __tablename__ = 'doctors'

    doctor_id = db.Column(db.Integer, primary_key=True)
    doctor_name = db.Column(db.String(150), nullable=False)
    qualification = db.Column(db.String(100))
    registration_no = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Customer(db.Model):
    __tablename__ = 'customers'

    customer_id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.doctor_id'))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(15))

    face_image_url = db.Column(db.Text)
    face_embedding = db.Column(Vector(128))
    last_face_scan_at = db.Column(db.DateTime)
    is_chronic_patient = db.Column(db.Boolean, nullable=False, default=False)
    risk_score = db.Column(db.Integer, nullable=False, default=0)

    is_cash_customer = db.Column(db.Boolean, nullable=False, default=True)
    credit_limit = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    outstanding_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
