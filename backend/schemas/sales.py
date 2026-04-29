from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.sales import (
    SalesBill, SalesBillItem, ApprovalLog, PrescriptionRegister,
    SalesReturn, SalesReturnItem, ReceiptPayment
)


class SalesBillSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SalesBill
        load_instance = True


class SalesBillItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SalesBillItem
        load_instance = True


class ApprovalLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ApprovalLog
        load_instance = True


class PrescriptionRegisterSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrescriptionRegister
        load_instance = True


class SalesReturnSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SalesReturn
        load_instance = True


class SalesReturnItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SalesReturnItem
        load_instance = True


class ReceiptPaymentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ReceiptPayment
        load_instance = True
