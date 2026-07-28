from app import app  # noqa: F401
import erp      # noqa: E402,F401 — ERP modules
import website  # noqa: E402,F401 — public corporate site (NOT site.py: shadows stdlib `site`)
import reorder  # noqa: E402,F401 — auto-reorder bot
import tenancy  # noqa: E402,F401 — MUST be last: rebinds conn() to the per-request tenant DB
