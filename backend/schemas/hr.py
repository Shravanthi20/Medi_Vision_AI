from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.hr import Salesman, AttendanceLog, SalesmanLedger


class SalesmanSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Salesman
        load_instance = True


class AttendanceLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AttendanceLog
        load_instance = True


class SalesmanLedgerSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SalesmanLedger
        load_instance = True
