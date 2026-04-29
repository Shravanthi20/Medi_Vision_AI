from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from ..models.core import (
    Role, User, FinancialYear, GstSlab, HsnCode, Combination,
    Manufacturer, ProductCategory, UnitOfMeasure, Item, Location,
    Supplier, SupplierItem, Doctor, Customer
)

class RoleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = True


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ('password_hash',)


class FinancialYearSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = FinancialYear
        load_instance = True


class GstSlabSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = GstSlab
        load_instance = True


class HsnCodeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = HsnCode
        load_instance = True


class CombinationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Combination
        load_instance = True


class ManufacturerSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Manufacturer
        load_instance = True


class ProductCategorySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ProductCategory
        load_instance = True


class UnitOfMeasureSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = UnitOfMeasure
        load_instance = True


class ItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Item
        load_instance = True


class LocationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Location
        load_instance = True


class SupplierSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Supplier
        load_instance = True


class SupplierItemSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = SupplierItem
        load_instance = True


class DoctorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Doctor
        load_instance = True


class CustomerSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Customer
        load_instance = True
        # Exclude pgvector embeddings from standard JSON responses
        exclude = ('face_embedding',)
