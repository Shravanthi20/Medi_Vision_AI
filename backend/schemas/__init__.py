"""All Marshmallow schemas — central import point."""

from .lookups import (
    BillTypeSchema, PurchaseTypeSchema, TxnTypeSchema,
    PaymentModeSchema, WantedStatusSchema, ReturnReasonSchema
)

from .core import (
    RoleSchema, UserSchema, FinancialYearSchema, GstSlabSchema,
    HsnCodeSchema, CombinationSchema, ManufacturerSchema,
    ProductCategorySchema, UnitOfMeasureSchema, ItemSchema,
    LocationSchema, SupplierSchema, SupplierItemSchema,
    DoctorSchema, CustomerSchema
)

from .hr import SalesmanSchema, AttendanceLogSchema, SalesmanLedgerSchema
from .inventory import StockBatchSchema, StockLedgerSchema, ExpiryAlertSchema

from .ai import (
    AiFaceLogSchema, PrescriptionOcrLogSchema,
    CustomerPurchasePatternSchema, SeleniumOrderLogSchema, WantedListSchema
)

from .sales import (
    SalesBillSchema, SalesBillItemSchema, ApprovalLogSchema,
    PrescriptionRegisterSchema, SalesReturnSchema,
    SalesReturnItemSchema, ReceiptPaymentSchema
)

from .purchase import (
    PurchaseInvoiceSchema, PurchaseInvoiceItemSchema,
    PurchaseReturnSchema, PurchaseReturnItemSchema, PurchasePaymentSchema
)

from .finance import GstTransactionSchema, ExpenseSchema
from .system import AuditLogSchema, SmsLogSchema, SystemSettingSchema
