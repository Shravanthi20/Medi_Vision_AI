# SmartOrder AI POS Upgrade Report

Date: 2026-04-05
Project: smartorder_ai
Primary Updated File: invoice_v2.html

## Scope Requested
You asked for these upgrades:
- Draggable/right billing panel with adjustable size
- Purchase Excel import
- Utilities cards always visible at top
- Hold bill -> create new bill flow, with held bill visibility and restore
- User creation with role-based access
- Super user, manager, user, owner technical (full access)
- Smart reorder/forecasting integration and website name matching (Retailio + more)
- Retail + wholesale billing support
- Doctor/hospital support in billing context
- Reorder menu option for wanted list from min/reorder point

## Implemented Changes

### 1) Sales/Billing UX
- Added draggable resizer between medicine grid and right billing panel.
- Billing panel width is persisted in localStorage (`billWidth`).
- Added billing type selector:
  - `Retail`
  - `Wholesale` (applies mode discount in totals)
- Added customer type selector:
  - `Customer`
  - `Doctor`
  - `Hospital`

### 2) Hold Bill Workflow
- Implemented actual hold flow (`hb()`):
  - Saves current bill snapshot into `heldBills` localStorage.
  - Clears current bill and starts a new bill.
- Added held bill dropdown (`hold-list`) in billing header.
- Added actions:
  - `Load` to restore selected held bill.
  - `New` to force start new bill.

### 3) Purchase Excel Import
- Added SheetJS runtime script and import UI in Purchase section.
- Implemented:
  - `parsePurchaseExcel()`
  - `renderPurchaseImportPreview()`
  - `importPurchaseExcelToInventory()`
- Supports columns (flexibly matched):
  - medicine/item/product/name
  - qty/quantity/stock/units/strips
  - mrp/price/rate/ptr/amount (optional)
  - batch (optional)
  - expiry (optional)
- Imports into medicines inventory and logs one purchase entry.

### 4) Utilities Sticky Actions
- Made utilities action block sticky at top via `.util-actions-sticky`.
- Keeps Stock/Expiry/Export/Backup cards visible while scrolling utility page.

### 5) Re-Order AI Menu + Wanted List
- Added left menu item: `Re-Order AI`.
- Added reorder panel (`p-reorder`) with:
  - Forecast Days
  - Lead Days
  - Safety Stock
  - Generate Wanted List
  - Export CSV
- Implemented:
  - `generateWantedList()`
  - `exportWantedCsv()`
- Logic combines:
  - current stock
  - min/reorder point (`medicine.reorder`)
  - recent sales-derived average daily usage
  - lead+safety requirement

### 6) Website Name Matching (Retailio + More)
- Added connector site management in reorder panel.
- Implemented:
  - `addConnectorSite()`
  - `removeConnectorSite()`
  - `renderConnectorSites()`
  - `matchedSiteForMedicine()`
- Stores connector sites in localStorage (`connectorSites`).

### 7) Role-Based Access + Users
- Added role/access model:
  - `owner_technical` (full)
  - `super_user`
  - `manager`
  - `user`
- Added users panel (`p-users`) and top-right user switch.
- Implemented:
  - `initUsers()`
  - `renderUsersPanel()`
  - `addAppUser()`
  - `removeAppUser()`
  - `applyRoleAccess()`
- Menu entries are locked/unlocked by role.

### 8) Live Data/Runtime Integration Fixes
- Added API/static origin fallback logic for running frontend on `:8000` while backend is `:5001`:
  - `API` -> `http://127.0.0.1:5001/api` when page served from `:8000`
  - `STATIC_BASE` -> backend static
- Face API script points to backend static endpoint.

## Persistence Added
- `heldBills` (held bill queue)
- `billWidth` (resizer width)
- `connectorSites` (website mapping)
- `appUsers` (local user list)
- `currentUserId` (active signed-in user simulation)

## Notes
- This is app-level role control in frontend logic (as requested).
- For production SaaS/subscription: backend auth, tenant isolation, and secure RBAC enforcement should be added server-side.

## Output Files
- Updated: `invoice_v2.html`
- Report: `IMPLEMENTATION_REPORT.md`
- Archive: generated ZIP bundle (see filename below)
