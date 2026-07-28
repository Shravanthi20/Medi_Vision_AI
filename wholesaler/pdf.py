"""
Server-rendered PDF invoices with letterhead
==============================================

Replaces browser print-to-PDF (still available as a fallback via
window.print()) with a real PDF generated server-side via reportlab -
pure Python, no system libraries (no Cairo/Pango), light enough for the
box's single shared vCPU. Includes the company's letterhead (logo if
uploaded, else a generated placeholder mark + name), full GST breakup,
and the terms/bank details set in /customize - all driven from settings,
same as everything else customizable in this app.

Logo upload: saved to uploads/<tenant-slug>/logo.<ext> and served back
through /uploads/<slug>/logo — a company logo isn't sensitive, so this
is deliberately unauthenticated (it has to render inside a PDF and
inside the public catalog/invoice pages without needing a session).
"""
from __future__ import annotations

import os
import io

from flask import Response, abort, request, redirect, url_for, flash, session, send_file

from app import app, conn, login_required
from erp import setting_get, setting_set

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                    Spacer, Image as RLImage)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GREEN = colors.HexColor("#16a34a")
DIM = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")


def _logo_path(slug: str) -> str | None:
    for ext in ("png", "jpg", "jpeg"):
        p = os.path.join(UPLOAD_DIR, slug, f"logo.{ext}")
        if os.path.exists(p):
            return p
    return None


@app.route("/uploads/<slug>/logo")
def serve_logo(slug):
    p = _logo_path(slug)
    if not p:
        abort(404)
    return send_file(p)


@app.route("/customize/logo", methods=["POST"])
@login_required
def upload_logo():
    from flask import g
    f = request.files.get("logo")
    if not f or not f.filename:
        flash("Choose an image first.", "err")
        return redirect(url_for("customize"))
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("png", "jpg", "jpeg"):
        flash("Logo must be a PNG or JPG.", "err")
        return redirect(url_for("customize"))
    slug = session.get("tenant") or "default"
    d = os.path.join(UPLOAD_DIR, slug)
    os.makedirs(d, exist_ok=True)
    for old_ext in ("png", "jpg", "jpeg"):
        old = os.path.join(d, f"logo.{old_ext}")
        if os.path.exists(old):
            os.remove(old)
    f.save(os.path.join(d, f"logo.{ext}"))
    flash("Logo uploaded.", "ok")
    return redirect(url_for("customize"))


def _styles():
    ss = getSampleStyleSheet()
    return {
        "company": ParagraphStyle("company", parent=ss["Heading1"], fontSize=18, textColor=colors.HexColor("#0f172a"), spaceAfter=2),
        "dim": ParagraphStyle("dim", parent=ss["Normal"], fontSize=9, textColor=DIM),
        "label": ParagraphStyle("label", parent=ss["Normal"], fontSize=8, textColor=DIM),
        "value": ParagraphStyle("value", parent=ss["Normal"], fontSize=10, textColor=colors.HexColor("#0f172a")),
        "title": ParagraphStyle("title", parent=ss["Heading1"], fontSize=20, alignment=TA_RIGHT, textColor=colors.HexColor("#0f172a")),
        "right_dim": ParagraphStyle("right_dim", parent=ss["Normal"], fontSize=9, textColor=DIM, alignment=TA_RIGHT),
        "small": ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=DIM),
    }


def build_invoice_pdf(inv, lines, company: dict, slug: str) -> bytes:
    """inv, lines: sqlite3.Row-like. company: dict with name/gstin/address/phone."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    S = _styles()
    story = []

    # ── Letterhead ──────────────────────────────────────────────────
    logo_path = _logo_path(slug)
    if logo_path:
        logo_cell = RLImage(logo_path, width=42 * mm, height=22 * mm, kind="proportional")
    else:
        # Placeholder mark: colored box with the company's initial, so an
        # invoice never looks broken just because no logo was uploaded yet.
        logo_cell = Paragraph(
            f'<para alignment="center"><font color="white" size="22"><b>{(company["name"] or "?")[0]}</b></font></para>',
            ParagraphStyle("mark", alignment=TA_CENTER))

    addr_lines = [company["name"]]
    if company.get("address"):
        addr_lines.append(company["address"])
    bits = []
    if company.get("phone"):
        bits.append(company["phone"])
    if company.get("gstin"):
        bits.append(f"GSTIN {company['gstin']}")
    if bits:
        addr_lines.append(" · ".join(bits))

    head_left = [Paragraph(company["name"], S["company"])]
    for line in addr_lines[1:]:
        head_left.append(Paragraph(line, S["dim"]))

    head_right = [Paragraph("TAX INVOICE", S["title"]),
                 Paragraph(f"#{inv['invoice_no']}", S["right_dim"]),
                 Paragraph(f"Date: {inv['invoice_date']}", S["right_dim"]),
                 Paragraph(f"Due: {inv['due_date']}", S["right_dim"])]

    head_tbl = Table([[logo_cell, head_left, head_right]], colWidths=[26 * mm, 80 * mm, None])
    head_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), GREEN if not logo_path else colors.white),
        ("BOX", (0, 0), (0, 0), 0, colors.white),
    ]))
    story.append(head_tbl)
    story.append(Spacer(1, 6 * mm))

    # rule
    rule = Table([[""]], colWidths=[178 * mm], rowHeights=[0.6])
    rule.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.75, LINE)]))
    story.append(rule)
    story.append(Spacer(1, 5 * mm))

    # ── Bill to ─────────────────────────────────────────────────────
    bill_to = [Paragraph("BILL TO", S["label"]),
              Paragraph(f"<b>{inv['shop_name']}</b>", S["value"])]
    if inv["shop_address"] or inv["shop_city"]:
        bill_to.append(Paragraph(f"{inv['shop_address'] or ''} {inv['shop_city'] or ''}".strip(), S["dim"]))
    if inv["shop_gstin"]:
        bill_to.append(Paragraph(f"GSTIN: {inv['shop_gstin']}", S["dim"]))
    if inv["shop_dl"]:
        bill_to.append(Paragraph(f"DL: {inv['shop_dl']}", S["dim"]))
    story.append(Table([[bill_to]], colWidths=[178 * mm]))
    story.append(Spacer(1, 6 * mm))

    # ── Line items ──────────────────────────────────────────────────
    header = ["Item", "Qty", "Free", "Rate", "GST%", "Amount"]
    rows = [header]
    for l in lines:
        rows.append([
            f"{l['item_name']}\n{l['pack_size'] or ''}".strip(),
            str(l["qty"]), str(l["free_qty"] or 0),
            f"{l['rate']:.2f}", f"{l['gst_rate']:.0f}%", f"{l['amount']:.2f}",
        ])
    tbl = Table(rows, colWidths=[70 * mm, 18 * mm, 18 * mm, 24 * mm, 20 * mm, 28 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, 0), DIM),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Totals ──────────────────────────────────────────────────────
    balance = (inv["total"] or 0) - (inv["paid"] or 0)
    totals = [
        ["", "Grand total", f"Rs {inv['total']:.2f}"],
        ["", "Paid", f"Rs {inv['paid']:.2f}"],
        ["", "Balance due", f"Rs {balance:.2f}"],
    ]
    ttbl = Table(totals, colWidths=[110 * mm, 40 * mm, 28 * mm])
    ttbl.setStyle(TableStyle([
        ("FONTSIZE", (1, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, 2), (-1, 2), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 2), (-1, 2), colors.HexColor("#dc2626") if balance > 0 else DIM),
        ("LINEABOVE", (1, 2), (-1, 2), 0.75, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(ttbl)

    # ── Terms / bank ────────────────────────────────────────────────
    terms = setting_get("invoice.terms", "").strip()
    bank = setting_get("invoice.bank", "").strip()
    if terms or bank:
        story.append(Spacer(1, 10 * mm))
        story.append(Table([[""]], colWidths=[178 * mm], rowHeights=[0.6],
                           style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE)])))
        story.append(Spacer(1, 3 * mm))
        if bank:
            story.append(Paragraph(f"<b>Payment details:</b> {bank}", S["small"]))
        if terms:
            story.append(Paragraph(terms, S["small"]))

    doc.build(story)
    return buf.getvalue()


def _load_invoice(inv_id: int, shop_id: int | None = None):
    with conn() as c:
        q = """SELECT i.*, s.name shop_name, s.gstin shop_gstin, s.address shop_address,
                      s.city shop_city, s.drug_license shop_dl
               FROM invoices i JOIN retail_shops s ON s.id=i.shop_id WHERE i.id=?"""
        params = [inv_id]
        if shop_id is not None:
            q += " AND i.shop_id=?"
            params.append(shop_id)
        inv = c.execute(q, params).fetchone()
        if not inv:
            return None, []
        lines = c.execute("SELECT * FROM sales_order_items WHERE order_id=?",
                          (inv["order_id"],)).fetchall() if inv["order_id"] else []
    return inv, lines


def _company_dict():
    return {
        "name": setting_get("company.name", "MediVision Wholesale"),
        "gstin": setting_get("company.gstin", ""),
        "address": setting_get("company.address", ""),
        "phone": setting_get("company.phone", ""),
    }


@app.route("/invoices/<int:inv_id>/pdf")
@login_required
def invoice_pdf(inv_id):
    if not HAVE_REPORTLAB:
        abort(501)
    inv, lines = _load_invoice(inv_id)
    if not inv:
        abort(404)
    pdf_bytes = build_invoice_pdf(inv, lines, _company_dict(), session.get("tenant", "default"))
    return Response(pdf_bytes, mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={inv['invoice_no'].replace('/', '-')}.pdf"})


@app.route("/shop/bills/<int:inv_id>/pdf")
def shop_bill_pdf(inv_id):
    if not HAVE_REPORTLAB:
        abort(501)
    if not session.get("shop_id"):
        abort(404)
    inv, lines = _load_invoice(inv_id, shop_id=session["shop_id"])
    if not inv:
        abort(404)
    pdf_bytes = build_invoice_pdf(inv, lines, _company_dict(), session.get("tenant", "default"))
    return Response(pdf_bytes, mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={inv['invoice_no'].replace('/', '-')}.pdf"})
