from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.finance import GstTransaction, Expense


class GstTransactionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = GstTransaction
        load_instance = True


class ExpenseSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Expense
        load_instance = True
