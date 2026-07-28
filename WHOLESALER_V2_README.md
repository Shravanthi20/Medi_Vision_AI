# MediVision Wholesale — v2 (fully-loaded distributor suite)

Built overnight on top of the retail MediVision AI, but deployed as a
**completely separate app** (own database, own login, own domain) so
retail data and wholesale data never mix.

**Live at:**
- Primary:   https://wholesale.selvammedicals.in
- Fallback:  https://selvammedicals.in/wholesale/  (works even if the subdomain DNS is ever off)
- Public catalog (no login):  https://wholesale.selvammedicals.in/catalog

**Admin login** (paste into Google Password Manager next time you sign in):
- URL:      https://wholesale.selvammedicals.in/login
- Name:     anything you like (used for the audit log)
- Password: `TjWHDJgVZ1swm8OP`

---

## What's built

### Core distribution
| Module     | URL         | What it does |
|------------|-------------|--------------|
| Dashboard  | `/`         | KPIs: active shops, open orders, invoiced today/month, outstanding, overdue, low-stock, top shops, recent orders, overdue chasers |
| Retail shops | `/shops`  | Master with GSTIN, DL, credit limit, credit days, price tier (A/B/C for volume pricing), route, status |
| Shop detail | `/shops/<id>` | Recent orders, invoices, payments and running outstanding for that shop |
| Items      | `/items`    | Wholesale item master with SKU, generic, manufacturer, pack, HSN, GST%, MRP, PTR-A/B/C, scheme (10+1 etc), MOQ, stock, reorder-level, category, batch, expiry |
| Orders     | `/orders`   | List filtered by status; full lifecycle `draft → confirmed → dispatched → invoiced → paid` (or `cancelled`) |
| New order  | `/orders/new` | Line-item entry with autocomplete against the item master; rate auto-fills from the shop's price tier |
| Order detail | `/orders/<id>` | View lines, run next lifecycle step, timeline; dispatch auto-deducts stock, invoice auto-creates the invoice row with due-date from the shop's credit_days |
| Invoices   | `/invoices` | List filtered by open/partial/paid/**overdue** |
| Invoice detail | `/invoices/<id>` | Print-ready tax invoice with company + shop + GST breakup; record cash/UPI/bank/cheque payments; shows balance due |
| Ledger     | `/ledger`   | Every shop with outstanding, sorted overdue-first; one-tap WhatsApp reminder link |
| Routes     | `/routes`   | Delivery beats with day-of-week + salesman; shops assigned per route |
| Public catalog | `/catalog` | Retail shops browse without login, drop qty against items, enter shop code, order lands as a **draft** in `/orders`; unknown shop codes auto-create a `[Pending]` shop on hold for you to approve |
| WhatsApp intake | `POST /api/whatsapp/inbound` | Twilio-webhook stub; parses `SEL001: Dolo 650 x5, Crocin x2` into a draft order — wire the Twilio number to this URL later and orders start dropping in from WhatsApp |

### ERP for the wholesaler's own organization
| Module     | URL         | What it does |
|------------|-------------|--------------|
| Staff      | `/staff`    | Employee master with role, phone, aadhaar, join date, base salary, OT rate |
| Attendance | `/attendance` | Mark present/half/absent/leave + OT hours per staff per day |
| Payroll    | `/payroll`  | Monthly view: days worked, OT, base earned (base ÷ working-days × days-worked), OT amount, advances, net payable |
| Suppliers  | `/suppliers` | Manufacturer/distributor master |
| Purchases  | `/purchases` | Purchase orders with lines, GST; "mark received" bumps stock automatically |
| Expenses   | `/expenses` | Categorised expense entries with monthly total and by-category breakdown |
| Reports    | `/reports`  | Monthly revenue, expenses, rough profit, top items, top shops, GST in/out/net, invoice ageing (0/30/60/90/90+ buckets) |
| Customize  | `/customize` | Toggle any module on/off, edit company details for invoices, edit invoice terms + bank block, add custom key=value fields on shops and items |
| Settings   | `/settings` | Environment info (company details, DB path) |

### Public + integration
| Endpoint | Purpose |
|----------|---------|
| `GET /api/items?q=&limit=` | JSON items list — used by the order-entry autocomplete |
| `GET /api/shops?q=`        | JSON shops list |
| `GET /catalog`             | Public catalog for retail shops to place orders themselves |
| `POST /api/whatsapp/inbound` | Twilio-webhook stub for parsing WhatsApp orders |
| `GET /health`              | Uptime probe |

---

## Sample data seeded

- **10 retail shops** in Coimbatore / Tirupur / Erode / Ooty / Salem area
- **50 medicines** across painkillers, antibiotics, acidity, allergy, cardiac, diabetic, cold-cough, topical, supplements, otc, anti-emetic, gastro, hormonal — with realistic MRP + PTR (A/B/C tiers) + schemes like "10+1"
- **7 suppliers** (Micro Labs, GSK, IPCA, Sun Pharma, Cipla, Torrent, Sanofi)
- **7 staff** (2 salesmen, 2 delivery, 1 accountant, 1 packer, 1 reception) with base salary + OT rate
- **4 delivery routes** with day-of-week and assigned salesman
- **20 sales orders** spread across the last 30 days in various statuses (draft, dispatched, invoiced)
- **12 invoices** (some paid, some open, some already overdue → so `/ledger` and `/reports` aging show real buckets)
- **7 monthly expenses** across rent, salary, transport, utilities, fuel, office, marketing

The seed is **idempotent** — re-running it will not create duplicates.
To wipe everything and start fresh: `rm /var/www/wholesaler/wholesaler.db && systemctl restart wholesaler.service && cd /var/www/wholesaler && ./venv/bin/python seed.py`.

---

## Files on the VPS

```
/var/www/wholesaler/
├── app.py            # main routes (dashboard, shops, items, orders, invoices, ledger, routes, catalog, wa-inbound)
├── erp.py            # side-import: staff/attendance/payroll, suppliers/purchases, expenses, reports, customize, /api/*
├── wsgi.py           # gunicorn entry (imports app + erp)
├── seed.py           # sample data
├── requirements.txt  # flask, gunicorn, python-dotenv
├── .env              # WS_SECRET_KEY, WS_ADMIN_PASSWORD, DB path, company details, PORT=3002
├── wholesaler.db     # SQLite database — back this up
├── venv/             # Python 3.10 virtualenv
├── static/style.css  # dark theme, matches MediVision brand
└── templates/
    ├── base.html           # nav + layout
    ├── login.html
    ├── dashboard.html
    ├── shops.html / shop_detail.html
    ├── items.html
    ├── orders.html / order_new.html / order_detail.html
    ├── invoices.html / invoice_detail.html
    ├── ledger.html
    ├── routes.html
    ├── catalog.html / catalog_thanks.html
    ├── staff.html / attendance.html / payroll.html
    ├── suppliers.html / purchases.html / purchase_new.html / purchase_detail.html
    ├── expenses.html
    ├── reports.html
    ├── customize.html
    └── settings.html
```

Service: `systemctl status wholesaler.service` — auto-restarts on crash, auto-starts on VPS reboot (via the existing pm2 systemd unit is unrelated; this uses its own systemd unit `wholesaler.service`).

Logs:
- `/var/log/wholesaler-access.log` (every HTTP request)
- `/var/log/wholesaler-error.log`  (crashes + startup)

---

## Try it now (order-of-operations walk-through)

1. Sign in at https://wholesale.selvammedicals.in/login
2. **Dashboard** — you should see 10 active shops, 50 items in catalog, revenue this month, real overdue amounts
3. **New order** → pick "Selvam Medicals" → start typing an item name (autocomplete works) → set qty → save → confirm → dispatch (stock deducts) → invoice (invoice row created with 30-day due)
4. **Invoice detail** → record a partial payment → status flips to `partial` → record the rest → status flips to `paid`
5. **Ledger** — every unpaid shop shows outstanding, with a WhatsApp-remind link
6. **Attendance** → mark today for every staff → save
7. **Payroll** → the same month shows base + OT + advances → net payable per person
8. **Expenses** → add today's diesel or shop rent → shows in the by-category card and in `/reports`
9. **Reports** → revenue, rough profit, GST net, invoice ageing all in one screen
10. **Customize** → toggle "Purchases" off → the nav link disappears without deleting any data → toggle back on → link returns
11. **Catalog** (open in incognito): https://wholesale.selvammedicals.in/catalog — this is what retail shops see; order lands as a draft in `/orders`

---

## What's NOT built yet (next-iteration ideas)

- **Multi-user with roles** (staff can log in with different permissions — currently one shared admin login)
- **PDF invoices** (currently print-to-PDF from the browser; a proper server-side PDF with your letterhead is next)
- **WhatsApp Business API wiring** (the `/api/whatsapp/inbound` parser is ready; needs a Twilio number and webhook config)
- **SMS / WhatsApp reminders** on overdue (link exists, one-click sends via WA — automation is next)
- **Delivery boy mobile app** — a Capacitor wrapper of `/routes` that lets a salesman tick-off deliveries and collect cash on the road
- **Retail-shop self-service portal** — each shop logs in with their code + OTP, sees their own ledger, downloads invoices, pays online
- **UPI collect** on invoices — currently manual "record payment"; wire Razorpay/PhonePe for a proper "pay now" button on the shop-side portal
- **Barcode scan** in item master and PO receipt
- **Item image upload** for catalog
- **Bulk import from Excel** (item master + shop master)
- **Historical shop-wise price agreements** (right now the tier is fixed per shop; some shops negotiate item-specific rates)
- **Stock ledger** (in/out log per item — currently we just show current stock)
- **Multi-branch/depot** (right now single warehouse)
- **Push notifications** to phone for new catalog orders

Ping me any morning with which one is highest priority and I'll build it next.

---

## Files that back this up

Backup nightly to keep sleeping easy:
```
scp -i ~/.ssh/id_ed25519_medivision_vps root@88.222.215.67:/var/www/wholesaler/wholesaler.db ./wholesaler-$(date +%Y%m%d).db
```

Full disaster-recovery: everything except `wholesaler.db` and `.env` is regenerable from this repo. Just keep those two files backed up.
