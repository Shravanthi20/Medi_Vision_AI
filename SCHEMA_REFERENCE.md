# Medi Vision AI - Schema & API Reference

This document serves as a developer reference for the PostgreSQL database schema and the API query functions implemented in the backend routes.

## 🗄️ Database Schema Models

The database layer is built using SQLAlchemy ORM. The models are logically grouped into domains.

### 1. Lookups & Enums
**File:** [`backend/models/lookups.py`](backend/models/lookups.py)
Contains constant/reference tables that satisfy foreign key dependencies.
- `BillType`: Types of bills (Retail, Wholesale).
- `PurchaseType`: Types of purchases (Local, Interstate).
- `TxnType`, `PaymentMode`, `WantedStatus`, `ReturnReason`

### 2. Core & Masters
**File:** [`backend/models/core.py`](backend/models/core.py)
Core entity definitions for the system.
- `User`, `Role`: Authentication and authorization.
- `FinancialYear`, `Location`: System context.
- `Item`: The primary medicine/product catalog with default pricing, taxes, and packing info.
- `Customer`: Customer profiles. *Note: Includes `face_embedding` (`Vector(128)`) for AI biometrics.*
- `Supplier`, `Doctor`, `Manufacturer`, `ProductCategory`, `GstSlab`, `HsnCode`, `UnitOfMeasure`, `Combination`.

### 3. Inventory
**File:** [`backend/models/inventory.py`](backend/models/inventory.py)
Stock management.
- `StockBatch`: Tracks individual batches of items (batch no, expiry, MRP, purchase rate, current quantity).
- `StockLedger`: Historical tracking of stock movements.
- `ExpiryAlert`: Alerts for expiring batches.

### 4. Sales & Billing
**File:** [`backend/models/sales.py`](backend/models/sales.py)
Transaction handling for outward goods.
- `SalesBill`: The main invoice header. *Note: Includes `prescription_base64` for storing RX images.*
- `SalesBillItem`: Line items linked to a `SalesBill` and `StockBatch`.
- `ReceiptPayment`: Payments received against bills or customer accounts.
- `SalesReturn`, `SalesReturnItem`, `PrescriptionRegister`, `ApprovalLog`.

### 5. Purchases
**File:** [`backend/models/purchase.py`](backend/models/purchase.py)
Transaction handling for inward goods.
- `PurchaseInvoice`: The main inward invoice header.
- `PurchaseInvoiceItem`: Line items linked to incoming stock.
- `PurchasePayment`, `PurchaseReturn`, `PurchaseReturnItem`.

### 6. HR & Staff
**File:** [`backend/models/hr.py`](backend/models/hr.py)
- `Salesman`: Staff profiles.
- `AttendanceLog`: Check-in/out logs.
- `SalesmanLedger`: Commission and salary tracking.

### 7. AI & Machine Learning
**File:** [`backend/models/ai.py`](backend/models/ai.py)
- `AiFaceLog`: Logs of facial recognition events.
- `PrescriptionOcrLog`: Logs of OCR processing on uploaded prescriptions.
- `CustomerPurchasePattern`, `SeleniumOrderLog`, `WantedList`.

### 8. System & Finance
**Files:** [`backend/models/system.py`](backend/models/system.py), [`backend/models/finance.py`](backend/models/finance.py)
- `SystemSetting`: Key-value store for SMS templates and configs.
- `SmsLog`, `AuditLog`.
- `GstTransaction`, `Expense`.

---

## 🚀 API Routes & Query Functions

The API is structured to maintain a backward-compatible JSON interface while interacting with the PostgreSQL ORM backend.

### Inventory API
**File:** [`backend/routes/inventory.py`](backend/routes/inventory.py)
- `GET /api/medicines`: Fetches all items, aggregating total stock from `StockBatch`.
- `GET /api/medicines/alerts`: Queries items where stock is below `reorder_level` or batches expire within `expiry_days`.
- `POST /api/medicines`: Upserts an `Item` and its associated `StockBatch`.
- `DELETE /api/medicines/<id>`: Deletes an item and its batches.
- `GET /api/shelves`, `POST /api/shelves`, `DELETE /api/shelves/<id>`: Manages `Location` entities.

### Bills / Sales API
**File:** [`backend/routes/bills.py`](backend/routes/bills.py)
- `GET /api/bills`: Retrieves `SalesBill` records. Supports filtering by `start_date`, `end_date`, `customer`, and `doctor`.
- `GET /api/bills/<id>`: Retrieves a specific bill and its line items.
- `POST /api/bills`: Creates a `SalesBill` and `SalesBillItem`s. Calculates GST splits, saves `prescription_base64`, deducts stock from `StockBatch`, and updates customer outstanding balances.
- `PATCH /api/bills/<id>`: Updates bill financial totals.
- `DELETE /api/bills/<id>`: Soft-cancels a bill and restores stock quantities.
- `GET /api/reports/gst`: Aggregates taxable amounts and GST amounts over a date range.

### Purchases API
**File:** [`backend/routes/purchases.py`](backend/routes/purchases.py)
- `GET /api/purchases`: Retrieves `PurchaseInvoice` records with supplier details.
- `POST /api/purchases`: Creates a `PurchaseInvoice` and `PurchaseInvoiceItem`s. Automatically creates missing items and stock batches.

### Masters API (Customers, Suppliers, Doctors)
**File:** [`backend/routes/masters.py`](backend/routes/masters.py)
- `GET /api/customers`, `POST /api/customers`, `DELETE /api/customers/<id>`: Manages `Customer` profiles. *The POST method accepts and parses `face_vector` JSON arrays to populate the `Vector(128)` database column.*
- `GET /api/customers/<id>/ledger`: Aggregates `SalesBill` and `ReceiptPayment` records to calculate a running financial balance for a customer.
- `POST /api/customers/<id>/payment`: Creates a `ReceiptPayment` and deducts the amount from the customer's outstanding balance.
- `GET /api/suppliers`, `POST /api/suppliers`, `DELETE /api/suppliers/<id>`: Manages `Supplier` entities.
- `GET /api/doctors`, `POST /api/doctors`, `DELETE /api/doctors/<id>`: Manages `Doctor` entities.

### Communications & SMS API
**Files:** [`backend/routes/communications.py`](backend/routes/communications.py), [`backend/routes/sms.py`](backend/routes/sms.py)
- `GET /api/communications/templates`, `POST ...`, `PUT ...`, `DELETE ...`: CRUD for generic communication templates stored in `SystemSetting`.
- `GET /api/communications/logs`: Queries `SmsLog` for message history.
- `GET /api/sms/messages`, `POST /api/sms/messages`, `PATCH ...`: Advanced SMS management handling provider dispatch, retry logic, and dynamic template rendering.
