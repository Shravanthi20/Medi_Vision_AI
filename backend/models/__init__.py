"""All SQLAlchemy models — imported here so Alembic auto-discovers them."""


# Lookups
from .lookups import (
    BillType, PurchaseType, TxnType, PaymentMode, WantedStatus, ReturnReason
)


# Core / Masters
from .core import (
    Role, User, FinancialYear, GstSlab, HsnCode, Combination,
    Manufacturer, ProductCategory, UnitOfMeasure, Item, Location,
    Supplier, SupplierItem, Doctor, Customer
)


# HR / Staff
from .hr import Salesman, AttendanceLog, SalesmanLedger


# Inventory
from .inventory import StockBatch, StockLedger, ExpiryAlert


# AI / CV / ML
from .ai import (
    AiFaceLog, PrescriptionOcrLog, CustomerPurchasePattern,
    SeleniumOrderLog, WantedList
)


# Sales / Billing
from .sales import (
    SalesBill, SalesBillItem, ApprovalLog, PrescriptionRegister,
    SalesReturn, SalesReturnItem, ReceiptPayment
)


# Purchase
from .purchase import (
    PurchaseInvoice, PurchaseInvoiceItem,
    PurchaseReturn, PurchaseReturnItem, PurchasePayment
)


# GST / Finance
from .finance import GstTransaction, Expense


# System / Audit
from .system import AuditLog, SmsLog, SystemSetting
