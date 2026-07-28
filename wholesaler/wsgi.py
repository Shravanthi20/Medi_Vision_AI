from app import app  # noqa: F401
import erp      # noqa: E402,F401
import website  # noqa: E402,F401 — NOT site.py: shadows stdlib `site`
import reorder  # noqa: E402,F401
import wanted   # noqa: E402,F401 — shop portal + wanted-list matcher
import tenancy  # noqa: E402,F401 — MUST be last: rebinds conn() per tenant
