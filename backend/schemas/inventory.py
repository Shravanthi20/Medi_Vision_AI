from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.inventory import StockBatch, StockLedger, ExpiryAlert


class StockBatchSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StockBatch
        load_instance = True


class StockLedgerSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = StockLedger
        load_instance = True


class ExpiryAlertSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ExpiryAlert
        load_instance = True
