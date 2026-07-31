# MediVision AI — Continuation Handoff

> Read THIS file to continue. Do **not** re-read the whole prior chat — everything you need is here + in git. Branch: `feat/customer-tracking`.

## Two separate apps, two domains (don't confuse them)

| App | Domain | VPS dir | Port | Service |
|---|---|---|---|---|
| **Retail POS/ERP** | `selvammedicals.in` | `/var/www/medivision` | 3001 | `medivision` |
| **Wholesaler (multi-tenant)** | `wholesale.selvammedicals.in` | `/var/www/wholesaler` | 3002 | `wholesaler` |

Local repo: `D:\SRI HARI\Medi_Vision_AI latest shrihari`. The wholesaler working tree is edited in a **scratchpad** copy then copied into `wholesaler/` before commit (see git history).

## Deploy + verify pattern (both apps)
```bash
scp -i ~/.ssh/id_ed25519_medivision_vps <file> root@88.222.215.67:/var/www/<app>/<path>
ssh -i ~/.ssh/id_ed25519_medivision_vps root@88.222.215.67 \
  "cd /var/www/<app> && python3 -c 'import ast; ast.parse(open(\"app.py\").read())' && systemctl restart <service> && sleep 2 && systemctl is-active <service>"
```
- **Verify the file actually landed** (`grep -c <marker> <remote file>`) — an scp once reported success but didn't transfer.
- After DB work on real data: test live, then **restore any test rows/stock/status you changed**.
- Credentials (gate pw, owner/admin passwords, shop PINs, SSH key name) live in the assistant **memory files** and each app's `.env` — **kept out of git on purpose**. Recall them, don't hardcode into the repo.

## DONE & live — retail app
- Catalog: **36,136 medicines** (35,898 priced + item codes), **586 suppliers** (credit_days + outstanding), **67 customers**, **7,498 historical bills** (id prefix `OLD*`, real ts backfilled).
- Bulk DBF import: batched upload, `extra_json` keeps unmapped columns, per-file field-mapping diagnostics, `/api/import-dbf/clear` (type CLEAR).
- `/admin` login fixed (was unreachable), registration approval works, VPS-usage panel.
- Bill **editing** (`PUT /api/bills/<id>`, stock reconciled by signed delta).
- Billing screen: item **location** + **Add-to-Wanted-List** from search, **Symptom Advisor** modal, tab-scroll fix.
- Supplier edit no longer wipes credit data (was `INSERT OR REPLACE`).

## DONE & live — wholesaler
Retailer self-registration + owner approval, counter billing, partial dispatch → back-order, credit-limit guard, **shop PIN hashing**, order-pipeline widget + one-click status, public `/demo`.

## PENDING — pick up here
1. **Suppliers view page** (retail) — API + edit-safety done, **no screen yet**. Smallest next task. Nav in `frontend/templates/portal.html`; follow the `/api/suppliers` GET shape.
2. **Print alignment** — TVS MSP 250 Star = **dot-matrix on pre-printed stationery**, not thermal. Legacy layout map is in `PBLTMP.DBF` (row/col field positions, parseable via `A._parse_dbf_bytes`). Needs a photo of a blank form OR full parse of PBLTMP. Thermal 80mm already works (`/bill/<id>`).
3. **Multiple bill tabs** (Chrome-style +) — real state rework.
4. **Owner-editable print/label settings** page.
5. **Face-scan greeting + voice** — user said YES, do **last** (needs camera/speaker hardware; flag biometric/consent when built).
6. **Auto-order bot** (wanted-list → logs into wholesaler portal → places order) — **needs explicit user go-ahead**; it commits real purchases.
7. **Item-name aliasing** catalog ↔ wholesaler Excel (reuse alias-learning in wholesaler `wanted.py`).
8. Wanted-list + print-template finetuning noted by user.

## Token hygiene (user is on a usage-limited Pro plan)
- Prefer **Sonnet 5** for bulk work; Opus only for hard reasoning.
- Keep sessions short/focused; **don't paste big tool dumps** into chat — they re-cost every turn.
- Commit often; git is the memory.

## Paste-to-resume (new chat)
> "Read CONTINUE_HERE.md. Continue MediVision on branch feat/customer-tracking. Next task: build the retail **Suppliers view page** (#1 in PENDING). Deploy + verify live per the pattern in the file. Use Sonnet."
