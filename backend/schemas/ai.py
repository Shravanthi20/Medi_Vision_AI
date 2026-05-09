from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.ai import (
    AiFaceLog, PrescriptionOcrLog, CustomerPurchasePattern,
    SeleniumOrderLog, WantedList
)


class AiFaceLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = AiFaceLog
        load_instance = True


class PrescriptionOcrLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrescriptionOcrLog
        load_instance = True
        exclude = ('raw_extracted_text',)  # Large blob; only include on detail view


class CustomerPurchasePatternSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = CustomerPurchasePattern
        load_instance = True


class SeleniumOrderLogSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SeleniumOrderLog
        load_instance = True


class WantedListSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = WantedList
        load_instance = True
