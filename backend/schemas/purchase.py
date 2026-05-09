from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.purchase import (
    PurchaseInvoice, PurchaseInvoiceItem,
    PurchaseReturn, PurchaseReturnItem, PurchasePayment
)


class PurchaseInvoiceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchaseInvoice
        load_instance = True


class PurchaseInvoiceItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchaseInvoiceItem
        load_instance = True


class PurchaseReturnSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchaseReturn
        load_instance = True


class PurchaseReturnItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchaseReturnItem
        load_instance = True


class PurchasePaymentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PurchasePayment
        load_instance = True
