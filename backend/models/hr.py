from datetime import datetime
from ..extensions import db


class Salesman(db.Model):
    __tablename__ = 'salesmen'

    salesman_id = db.Column(db.Integer, primary_key=True)
    salesman_code = db.Column(db.String(10), nullable=False, unique=True)
    salesman_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False)
    salary_per_hr = db.Column(db.Numeric(8, 2), nullable=False, default=0.00)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AttendanceLog(db.Model):
    __tablename__ = 'attendance_log'

    log_id = db.Column(db.BigInteger, primary_key=True)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.salesman_id'), nullable=False)
    log_date = db.Column(db.Date, nullable=False)
    log_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'CAME' | 'WENT'
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("status IN ('CAME','WENT')", name='attendance_status_check'),
    )


class SalesmanLedger(db.Model):
    __tablename__ = 'salesman_ledger'

    salesman_ledger_id = db.Column(db.Integer, primary_key=True)
    salesman_id = db.Column(db.Integer, db.ForeignKey('salesmen.salesman_id'), nullable=False)
    period_label = db.Column(db.String(30), nullable=False)
    period_from = db.Column(db.Date, nullable=False)
    period_to = db.Column(db.Date, nullable=False)
    total_working_hrs = db.Column(db.Numeric(8, 2), nullable=False, default=0.00)
    salary_per_hr = db.Column(db.Numeric(8, 2), nullable=False)
    gross_salary = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    advance_taken = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    ai_commission_earned = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    performance_score = db.Column(db.Numeric(5, 2))

    net_payable = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    paid_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
