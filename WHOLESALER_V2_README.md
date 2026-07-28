# MediVision Wholesale — reference (updated after the multi-tenant + capacity/feature push)

This file replaces the earlier single-company version of this doc — a lot changed
underneath (multi-tenant, per-user roles, several new features) and the old URLs/
logins are no longer accurate. Everything below is current as of this session.

Completely separate from the retail MediVision app (own databases, own domain,
own login) — retail and wholesale data never mix.

---

## URLs

| What | URL |
|---|---|
| **Platform owner console** (manage companies, billing, suspend/activate) | https://wholesale.selvammedicals.in/platform/login |
| **Company sign-in** (staff/admin) | https://wholesale.selvammedicals.in/portal |
| **Shop sign-in** (your retail customers) | https://wholesale.selvammedicals.in/shop/login |
| **Public catalog** (no login, shareable/QR-codeable) | https://wholesale.selvammedicals.in/c/**rathna**/catalog |
| **Public corporate website** | https://wholesale.selvammedicals.in/company |

The `/catalog` and `/api/whatsapp/inbound` URLs **without a company slug still
exist** but only work correctly from inside an already-logged-in session — a
fresh visitor or a Twilio webhook MUST use the slug-scoped URLs above. This
was a real bug found and fixed this session (see "Multi-tenant" below) — don't
revert to the bare URLs when configuring anything external.

---

## Logins

### Platform owner (you)
- Password: `KIsf4AbGVX81NLNz3Q`

### Company: Sri Rathna Agencies (slug `rathna`)
- Company password (logs in as **owner** role): `rathna2026`
- Two **staff accounts were created live during testing** — real accounts on
  the production tenant, not throwaway. Change or remove them:
  - `ramesh` / `sales1234` — role: salesman
  - `priya` / `acct1234` — role: accountant

### Company: Demo Distributors (slug `demo`)
- Password: `demo2026` (empty shop, for showing the platform without touching real data)

**Staff login flow:** at `/portal`, tick "I have a personal staff login" to
switch the form from company-password to username+password. Owners manage
staff accounts at **Staff logins** in the nav (owner role only).

---

## Everything built this session, in order

1. **Wanted-list matcher scaling fix** — was O(catalog size) per line (SequenceMatcher
   against the whole catalog); a 100-line upload against a real 15,000-SKU catalog
   would have taken ~63s and exceeded gunicorn's own 60s timeout. Now a prefix-bucket
   index, capped candidates, bounded cost regardless of catalog size. Measured
   71,000x speedup at 15,000 items; verified identical matching behavior on the
   original test file.
2. **Capacity**: gunicorn 2→3 workers on both apps, SQLite WAL mode (readers don't
   block behind a writer on the same tenant DB), MemoryMax=512M safety caps.
3. **Shop-portal cart** — `/shop/catalog` → `/shop/cart` → checkout, localStorage-backed,
   shop's own tier pricing, no shop-code re-entry needed (session-authenticated).
4. **WhatsApp ordering** (Twilio) — `/api/whatsapp/inbound/<slug>`. A shop texts
   `SEL001: Dolo 650 x5, Crocin x2` and gets a reply confirming what matched, through
   the same alias/exact/fuzzy matcher the wanted-list uses. **Not yet connected to a
   real Twilio account** — see the checklist in `wholesaler/whatsapp.py`'s docstring.
   Status shown at `/customize`.
5. **UPI Pay Now** — `upi://pay` deep link + QR per invoice, using the company's own
   UPI ID (set at `/customize`, field "UPI ID (VPA)"). No payment gateway account
   needed. **Not auto-reconciled** — "record payment" stays a manual step.
6. **Multi-user roles** — owner / accountant / salesman, see Logins above.
7. **PDF invoices** — real server-rendered PDF (reportlab) with letterhead
   (upload a logo at `/customize`), GST breakup, terms/bank details. "Download PDF"
   button on every invoice, admin and shop-portal sides both.

### A real bug found and fixed along the way

A Twilio webhook carries no session cookie. The multi-tenant resolver
(`tenancy.py`) only knows the tenant from a session, so a cookie-less request
was **silently falling back to a stale leftover database** from before
multi-tenancy existed — same seed data, so it *looked* like it was working,
but any alias or data added after multi-tenancy went live was invisible to it.
The identical bug existed in the public `/catalog` link for any visitor with
no prior admin session. Both fixed the same way: the tenant now has to come
from an explicit URL segment (`/api/whatsapp/inbound/<slug>`,
`/c/<slug>/catalog`) which 404s loudly on anything invalid instead of guessing.
The stale database was also renamed aside and replaced with an empty one, so
any *future* bug of this shape fails obviously instead of silently serving
plausible-looking wrong data. Full details and the verification steps are in
the git commit `dbb3b97` and `50bbe36`.

---

## Architecture notes

- **Multi-tenant, database-per-company**: `tenants/<slug>.db`, not shared tables.
  A missing WHERE clause literally cannot leak one company's data into another's
  view — the other company's rows are in a file the request never opens.
- **VPS is 1 shared vCPU** (Hostinger, `88.222.215.67`), also running the retail
  MediVision app, the Aurilius site (Node/Postgres), and nginx. See the capacity
  numbers gathered this session: realistically ~15-30 truly simultaneous active
  users across everything before requests start queuing (not crashing — nginx
  queues, gunicorn processes, response times just climb).
- **Owner privacy boundary is structural, not policy**: `/platform/*` only ever
  opens `platform.db` (hardcoded, no path argument anywhere in that code path).
  Usage numbers shown to the owner are counts/totals pushed up by each tenant —
  never a row of their actual business data.

---

## Known follow-ups

- **`tenants/123.db`** exists on the VPS and wasn't created by me — flagged twice
  now, still unaddressed. Check `/platform` next time you're in, or ask about it.
- **WhatsApp needs a real Twilio account** to actually receive messages — the
  code is done and tested with simulated Twilio requests, but nothing is
  listening on a real WhatsApp number yet.
- **UPI needs your real UPI ID** entered at `/customize` — currently only set on
  the `rathna` tenant with a placeholder VPA (`rathnaagencies@okhdfcbank`) used
  for testing.
- **No signed SSL cert issue** — everything's on the existing `selvammedicals.in`
  wildcard-adjacent setup, no action needed.
- Next-iteration ideas from the original build (barcode scan, Excel bulk import,
  per-shop price agreements, multi-branch/depot) are all still open — see the
  original feature list further down if useful, none of it was touched this session.

---

## Quick smoke test if you want to confirm everything's alive

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://wholesale.selvammedicals.in/portal
curl -s -o /dev/null -w "%{http_code}\n" https://wholesale.selvammedicals.in/c/rathna/catalog
curl -s -o /dev/null -w "%{http_code}\n" https://wholesale.selvammedicals.in/company
```
All three should return `200`.
