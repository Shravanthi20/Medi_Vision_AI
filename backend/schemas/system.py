from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.system import AuditLog, SmsLog, SystemSetting


class AuditLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AuditLog
        load_instance = True


class SmsLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SmsLog
        load_instance = True


class SystemSettingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SystemSetting
        load_instance = True
