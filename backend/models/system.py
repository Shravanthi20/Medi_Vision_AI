"""Domain G — System / Audit: audit_log, sms_log, system_settings."""

from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    audit_id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    action = db.Column(db.String(10), nullable=False)
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.String(50), nullable=False)
    old_value = db.Column(JSONB)
    new_value = db.Column(JSONB)
    ip_address = db.Column(db.String(45))
    machine_code = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("action IN ('INSERT','UPDATE','DELETE')", name='audit_action_check'),
    )


class SmsLog(db.Model):
    __tablename__ = 'sms_log'

    sms_id = db.Column(db.Integer, primary_key=True)
    recipient_phone = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(10), nullable=False)
    ref_type = db.Column(db.String(30))
    ref_id = db.Column(db.Integer)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("status IN ('SENT','PENDING','FAILED')", name='sms_status_check'),
    )


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    setting_key = db.Column(db.String(100), primary_key=True)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'))
