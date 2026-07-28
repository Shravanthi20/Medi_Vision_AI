"""
Public corporate website (white-label)
======================================

A distributor's public-facing marketing site: home, about, brands,
associates, order-online, contact. Everything — company name, tagline,
years in business, stats, brand list, addresses — is driven from the
`settings` table, so the same code serves ANY company. Change the values
in /customize (or /site-admin) and the site re-skins itself.

Defaults are seeded for "Sri Rathna Agencies" on first run.

Routes are mounted under /company so the wholesaler admin app keeps the
root. In production, point a domain at /company via nginx.
"""
from __future__ import annotations

from flask import render_template, request, redirect, url_for, flash, session
from app import app, conn, login_required
from erp import setting_get, setting_set

# ── Default content (used when a setting hasn't been overridden) ────────
DEFAULTS = {
    "site.company":      "Sri Rathna Agencies",
    "site.tagline":      "Pharmaceutical Distribution, Done Right",
    "site.subtagline":   "Serving retailers, hospitals and institutions across Tamil Nadu with reliable supply, fair pricing and next-day delivery.",
    "site.years":        "25",
    "site.retailers":    "1200",
    "site.brands":       "180",
    "site.deliveries":   "500",
    "site.about":        ("Sri Rathna Agencies has grown from a single counter into one of the region's "
                          "most dependable pharmaceutical distribution houses. We stock a deep range across "
                          "acute and chronic therapy, maintain cold-chain integrity end to end, and run our "
                          "own delivery fleet so a retailer never has to choose between speed and reliability.\n\n"
                          "Our customers are independent pharmacies, hospital pharmacies, nursing homes, "
                          "dispensaries and government institutions. What keeps them with us is not price "
                          "alone — it is fill-rate, honest expiry handling, and someone who picks up the phone."),
    "site.mission":      "Every medicine, in stock, on time, at a fair price.",
    "site.address":      "Coimbatore, Tamil Nadu, India",
    "site.phone":        "+91 98430 00000",
    "site.email":        "orders@srirathnaagencies.com",
    "site.hours":        "Mon–Sat, 9:00 AM – 8:00 PM",
    "site.gstin":        "",
    "site.dl":           "",
    "site.brandlist":    ("Sun Pharma, Cipla, Dr Reddy's, Micro Labs, Mankind, Torrent, Alkem, "
                          "Lupin, Zydus, Glenmark, Intas, Abbott, GSK, Sanofi, Pfizer, USV, "
                          "Aristo, IPCA, Alembic, Emcure, Hetero, Macleods, Wockhardt, Indoco"),
    "site.services":     ("Next-day delivery|Own fleet covering the district, orders placed before 6 PM ship the same evening.\n"
                          "Deep stock range|180+ companies and 12,000+ SKUs across acute, chronic and OTC.\n"
                          "Cold chain|Validated 2–8°C storage and insulated transport for insulins and vaccines.\n"
                          "Fair credit terms|Transparent credit limits and cycles agreed up front, no surprises.\n"
                          "Expiry protection|Clear near-expiry policy and prompt credit notes on returns.\n"
                          "Digital ordering|Order by web, WhatsApp or phone — whatever suits your counter."),
    "site.whyus":        ("98%|Order fill rate\n"
                          "24 hrs|Typical delivery time\n"
                          "Zero|Cold-chain breaks last year\n"
                          "Same day|Credit note turnaround"),
}


def sv(key: str) -> str:
    """Setting value with fallback to the shipped default."""
    return setting_get(key, DEFAULTS.get(key, ""))


# Keyword -> icon, checked in order against the service title. Falls back to
# a generic mark. Keyword-matched (not positional) so it still makes sense
# even after an owner edits/reorders/adds lines from /site-admin.
_ICON_KEYWORDS = [
    (("deliver", "fleet", "next-day", "next day"), "🚚"),
    (("stock", "sku", "range", "inventory"), "📦"),
    (("cold", "chain", "storage", "vaccine", "insulin"), "🌡️"),
    (("credit", "payment", "terms", "billing"), "🤝"),
    (("expiry", "expired", "return", "credit note"), "♻️"),
    (("digital", "whatsapp", "online", "app", "order by"), "💬"),
    (("gst", "tax", "compliance", "licence", "license"), "📋"),
    (("support", "service", "call", "help"), "🎧"),
]


def _icon_for(title: str) -> str:
    t = title.lower()
    for keywords, icon in _ICON_KEYWORDS:
        if any(k in t for k in keywords):
            return icon
    return "✦"


def site_ctx() -> dict:
    """Everything the public templates need."""
    brands = [b.strip() for b in sv("site.brandlist").split(",") if b.strip()]

    services = []
    for line in sv("site.services").splitlines():
        if "|" in line:
            title, desc = line.split("|", 1)
            title = title.strip()
            services.append({"title": title, "desc": desc.strip(), "icon": _icon_for(title)})

    stats = []
    for line in sv("site.whyus").splitlines():
        if "|" in line:
            val, label = line.split("|", 1)
            stats.append({"value": val.strip(), "label": label.strip()})

    return {
        "c": {k.replace("site.", ""): sv(k) for k in DEFAULTS.keys()},
        "brands": brands,
        "services": services,
        "stats": stats,
    }


# ── Public pages ───────────────────────────────────────────────────────
@app.route("/company")
def site_home():
    return render_template("site/home.html", **site_ctx())


@app.route("/company/about")
def site_about():
    return render_template("site/about.html", **site_ctx())


@app.route("/company/brands")
def site_brands():
    return render_template("site/brands.html", **site_ctx())


@app.route("/company/associates")
def site_associates():
    return render_template("site/associates.html", **site_ctx())


@app.route("/company/contact", methods=["GET", "POST"])
def site_contact():
    sent = False
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        shop = (request.form.get("shop") or "").strip()
        msg = (request.form.get("message") or "").strip()
        if name and phone:
            with conn() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS site_enquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, phone TEXT, shop TEXT, message TEXT,
                    created_at TEXT DEFAULT (datetime('now')), handled INTEGER DEFAULT 0)""")
                c.execute("INSERT INTO site_enquiries (name, phone, shop, message) VALUES (?,?,?,?)",
                          (name, phone, shop, msg))
            sent = True
    return render_template("site/contact.html", sent=sent, **site_ctx())


# ── Admin: edit the public site content ────────────────────────────────
@app.route("/site-admin", methods=["GET", "POST"])
@login_required
def site_admin():
    if request.method == "POST":
        for key in DEFAULTS.keys():
            val = request.form.get(key)
            if val is not None:
                setting_set(key, val.strip())
        flash("Website content saved.", "ok")
        return redirect(url_for("site_admin"))

    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS site_enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, phone TEXT, shop TEXT, message TEXT,
            created_at TEXT DEFAULT (datetime('now')), handled INTEGER DEFAULT 0)""")
        enquiries = c.execute("SELECT * FROM site_enquiries ORDER BY id DESC LIMIT 50").fetchall()

    current = {k: sv(k) for k in DEFAULTS.keys()}
    return render_template("site_admin.html", current=current, defaults=DEFAULTS, enquiries=enquiries)
