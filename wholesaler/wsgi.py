from app import app  # noqa: F401
import erp       # noqa: E402,F401
import website   # noqa: E402,F401 — NOT site.py: shadows stdlib `site`
import reorder   # noqa: E402,F401
import wanted    # noqa: E402,F401 — shop portal + wanted-list matcher
import whatsapp  # noqa: E402,F401 — Twilio inbound/outbound
import upi       # noqa: E402,F401 — UPI pay-now QR
import users     # noqa: E402,F401 — per-user accounts + roles
import tenancy   # noqa: E402,F401 — MUST be last: rebinds conn() per tenant
