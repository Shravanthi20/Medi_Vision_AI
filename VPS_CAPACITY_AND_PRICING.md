# VPS capacity + pricing — grounded in what's actually running

Written against the real box (checked live, not estimated): `srv1626708`, **1 vCPU** (AMD EPYC 9354P host,
oversold to 1 core), **3.8 GB RAM**, **49 GB disk** (41 GB free), currently running **two** Flask apps
side by side (`medivision` + `wholesaler`, 3 gunicorn workers each = 6 workers sharing that one core).
Current usage: 763 MB RAM, load average ~0.00 — essentially idle, because there's no real traffic yet.

This doc answers three things you asked for together: what the current box can actually hold, what it
needs to become for your stated numbers (50–80 staff PCs, 200–400 retail clients at 20–30 min sessions),
and what to charge. `GO_TO_MARKET.md` already has a broader city-by-city rollout plan and a generic VPS
tier table — this one is narrower and current: it's about *this* server, *today*, for the features that
actually exist right now (registration, billing, credit control, back-orders, Excel import, password
hashing, platform management — all shipped this session).

---

## 1. What "200-400 users, 20-30 min sessions" actually means for load

The trap in sizing this is treating 400 as "400 simultaneous connections." It isn't. A 20–30 minute
session is mostly a retailer reading a screen, deciding what to order, typing — not issuing requests.
The number that matters is **concurrent requests in flight at the same second**, which is a small
fraction of total active users:

- **Staff side (50–80 people):** bursty around shift start, order-confirm windows, and end-of-day billing.
  Realistic peak: maybe 10–15 staff hitting the app in the same few seconds during a busy morning.
- **Retailer side (200–400 shops):** they don't all order at 9:00am sharp, but pharma distribution does
  cluster — most shops place their day's order in a 2–3 hour morning window. If 300 shops order once a
  day in a 3-hour window, that's ~1.7 orders/minute on average, with real bursts of 10-20 concurrent
  active sessions at the worst moment (start of the window, or right after a WhatsApp/SMS nudge goes out).

**Realistic peak concurrent in-flight requests: 20–40**, not 400. That's the number to size against.

---

## 2. Where this box actually breaks first

Not RAM (3.8 GB with 763 MB used has huge headroom) and not disk (41 GB free — a tenant's entire
database, 25k items included, is a few tens of MB). It's **CPU**, for two compounding reasons:

1. **1 vCPU total, shared by two separate apps.** Gunicorn's sync workers are already correctly tuned
   for this (`-w 3` on each = the standard `(2×cores)+1` formula for 1 core) — but more workers on the
   *same* core doesn't add capacity, it just adds context-switching. Six workers fighting over one core
   means once you're genuinely running 20-30 concurrent requests, response times climb fast rather than
   staying flat.
2. **SQLite, one file per tenant.** Reads scale fine (WAL mode, already on — task from earlier this
   session). Writes to the *same tenant's* database serialize: if three staff at Sri Rathna are all
   confirming orders in the same second, they queue, they don't parallelize. At today's volume (a handful
   of orders/minute) this is invisible. At 200-400 retailers ordering in a tight morning window, with
   staff also actively working the same tenant DB, write contention is the first thing that will show up
   as slowness — before CPU maxes out, before RAM runs low.

**Bottom line: this exact box, unchanged, will start to feel sluggish somewhere in the range of
2-4 concurrently active wholesaler tenants each with real staff+retailer traffic at your stated scale.**
Below that, today's box is fine and there's no reason to spend more yet — you have one real tenant
(rathna) right now.

---

## 3. Concrete upgrade path

| Stage | Trigger | Target | Why |
|---|---|---|---|
| **Now** | 1 real tenant, pilot traffic | Stay as-is (1 vCPU / 4 GB) | Current load is ~0. Spending more now buys nothing. |
| **Stage 1** | 2nd–3rd paying wholesaler signs on, OR rathna alone hits your stated 50-80 staff + 200-400 retailers actively daily | **2 vCPU / 8 GB** | Doubles the CPU ceiling for request handling; gunicorn workers go to `-w 5` per app. This is very likely the *only* upgrade you need to comfortably run rathna alone at full stated scale. |
| **Stage 2** | 4-8 wholesaler tenants, each with real daily traffic | **4 vCPU / 16 GB**, and split the two apps (`medivision`, `wholesaler`) onto separate VPS instances | Two unrelated products no longer need to compete for the same core; each gets its own box. |
| **Stage 3** | 10+ wholesaler tenants, or any single tenant's write volume starts genuinely queuing under WAL | Move that tenant (or all of them) from SQLite to a shared **PostgreSQL** instance, keep the app tier on VPS | SQLite-per-tenant is the right call for isolation and 0-config now; it's not the right call at real multi-tenant write volume. This is a schema-migration project, not a VPS click-upgrade — budget real time for it, don't do it reactively during an outage. |

Realistic near-term cost: a 2 vCPU / 8 GB VPS from a budget provider (Contabo/Hostinger-class) runs
roughly **₹1,200–2,000/month** in India; a premium provider (DigitalOcean/Linode/AWS Lightsail-class)
roughly **₹2,500–4,000/month** for the same spec. Check your actual current invoice for this server's
real provider and rate — I can see the box's specs from inside it, not what you're being billed.

**My recommendation: don't upgrade today.** Set a trigger, not a date — the moment you onboard wholesaler
#2, or rathna's real usage visibly climbs (check `journalctl`/`htop` load average, not a guess), move to
Stage 1. That's a 10-minute provider-console resize, not a migration, so there's no cost to waiting.

---

## 4. Development fee + subscription pricing

### What actually shipped this session (the real scope, not the original ask)
The original ask was "a web ordering page." What's live now: public marketing site, live-search
catalog + retailer self-registration with owner approval, a full order-status pipeline (draft → confirmed
→ dispatched → invoiced) with one-click staff actions, counter billing, partial dispatch with automatic
back-orders, credit-limit enforcement with an audited override, Excel bulk stock import and wanted-list
ordering with fuzzy product matching, hashed credentials throughout, and a platform console to onboard
and manage wholesaler tenants. That's a full distributor ERP, not an ordering page — price it as one.

### One-time setup fee (per wholesaler company you onboard)
This covers branding their `/company` site, seeding their catalog, creating their staff logins, and a
short walkthrough call. Suggested: **₹15,000–₹35,000**, scaled by catalog size and how much hand-holding
the onboarding needs (a distributor who can fill the Excel template themselves is cheaper to onboard than
one who needs you to do the data entry).

### Monthly subscription (per wholesaler company)
The platform console already has a 4-tier plan structure built in (`starter`/`growth`/`pro`/`unlimited`
in `tenancy.py`) at ₹1,000/₹2,500/₹5,000/₹9,000 — that was priced for "an ordering page." Given the actual
feature set now, I'd revise upward:

| Tier | Retail shops | Staff logins | Suggested price |
|---|---:|---:|---:|
| Starter | up to 50 | 3 | ₹2,000/mo |
| Growth | up to 200 | 8 | ₹4,500/mo |
| Pro | up to 500 | 20 | ₹9,000/mo |
| Unlimited | unlimited | unlimited | ₹15,000/mo |

Rathna's stated numbers (200-400 shops, 50-80 staff) sit at Pro/Unlimited. Hosting cost for one tenant at
that scale, per Section 3, is a small fraction of the subscription price you'd be charging — the shared
VPS is what makes the margin work; don't quote per-tenant hosting cost back to a customer, it's already
priced in.

### Alternative worth considering, not necessarily recommending
Some distribution-software vendors charge a small percentage of GMV (order value processed) instead of a
flat fee, especially for their largest accounts — it scales revenue with the customer's actual growth
instead of capping it at a tier. This fits *large* wholesalers better than small ones (who want a
predictable monthly number they can budget against). If you go this route, I'd offer it only above the
Unlimited tier, as a negotiated deal, not a published price — flat tiers are easier for a distributor to
say yes to on a first call.

---

## 5. Direct answer to "current VPS to what it needs to upgrade"

**Nothing to upgrade today.** The box is idle. Upgrade to 2 vCPU / 8 GB the moment you have a second
paying wholesaler tenant, or the moment rathna's own daily traffic visibly approaches the 50-80 staff /
200-400 retailer numbers you described actually being active (not just registered) — whichever comes
first. That single upgrade almost certainly covers rathna alone at full stated scale; the bigger
architectural moves (split apps onto separate boxes, move to Postgres) are Stage 2/3 problems for when
you have several real tenants, not something to build ahead of need.
