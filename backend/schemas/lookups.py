from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.lookups import (
    BillType, PurchaseType, TxnType, PaymentMode, WantedStatus, ReturnReason
)


class BillTypeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = BillType
        load_instance = True


class PurchaseTypeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchaseType
        load_instance = True


class TxnTypeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = TxnType
        load_instance = True


class PaymentModeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PaymentMode
        load_instance = True


class WantedStatusSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = WantedStatus
        load_instance = True


class ReturnReasonSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ReturnReason
        load_instance = True
