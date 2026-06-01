from __future__ import annotations

from datetime import date as date_type, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models.core import FinancialYear, Supplier, User
from ..models.finance import Expense
from ..models.purchase import PurchaseInvoice, PurchasePayment, PurchaseReturn
from ..models.lookups import PaymentMode
from ..models.sales import SalesBill, SalesBillItem

from ..models.inventory import StockAdjustment, StockBatch

finance_bp = Blueprint("finance", __name__)


def _json_error(message: str, code: int = 400, details=None):
    payload = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), code


def _parse_date(value: str | None, default=None):
    raw = str(value or "").strip()
    if not raw:
        return default
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return default


def _default_context():
    fy = FinancialYear.query.filter_by(is_active=True).first()
    if not fy:
        today = date_type.today()
        fy = FinancialYear(
            fy_label=f"{today.year}-{str(today.year + 1)[-2:]}",
            start_date=date_type(today.year, 4, 1),
            end_date=date_type(today.year + 1, 3, 31),
            is_active=True,
        )
        db.session.add(fy)
        db.session.flush()

    user = User.query.first()
    if not user:
        from ..models.core import Role
        import hashlib
        import uuid

        role = Role.query.first()
        if not role:
            role = Role(role_name="Admin")
            db.session.add(role)
            db.session.flush()
        user = User(
            user_id=uuid.uuid4(),
            username="admin",
            password_hash=hashlib.sha256(b"admin").hexdigest(),
            role_id=role.role_id,
            is_super_admin=True,
        )
        db.session.add(user)
        db.session.flush()

    db.session.commit()
    return fy.financial_year_id, user.user_id


def _payment_mode_id():
    payment_mode = PaymentMode.query.filter_by(payment_mode_code="CASH").first()
    if not payment_mode:
        payment_mode = PaymentMode(payment_mode_code="CASH", payment_mode_name="Cash")
        db.session.add(payment_mode)
        db.session.flush()
    return payment_mode.payment_mode_id


def _expense_to_row(expense: Expense) -> dict:
    return {
        "id": expense.expense_id,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else "",
        "category": expense.expense_category,
        "amount": float(expense.amount or 0),
        "description": expense.description or "",
        "is_gst_applicable": bool(expense.is_gst_applicable),
        "gst_amount": float(expense.gst_amount or 0),
        "voucher_no": expense.voucher_no or "",
        "is_active": bool(expense.is_active),
    }


def _date_window():
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    return start_date, end_date


def _sales_scope(start_date, end_date):
    query = SalesBill.query.filter(SalesBill.is_cancelled.is_(False))
    return _apply_date_filter(query, SalesBill.bill_date, start_date, end_date)


def _purchase_scope(start_date, end_date):
    query = PurchaseInvoice.query
    return _apply_date_filter(query, PurchaseInvoice.invoice_date, start_date, end_date)


def _return_scope(start_date, end_date):
    query = PurchaseReturn.query
    return _apply_date_filter(query, PurchaseReturn.return_date, start_date, end_date)


def _expense_scope(start_date, end_date):
    query = Expense.query.filter(Expense.is_active.is_(True))
    return _apply_date_filter(query, Expense.expense_date, start_date, end_date)


def _payment_scope(start_date, end_date):
    query = PurchasePayment.query
    return _apply_date_filter(query, PurchasePayment.payment_date, start_date, end_date)


def _apply_date_filter(query, column, start_date, end_date):
    if start_date:
        query = query.filter(column >= start_date)
    if end_date:
        query = query.filter(column <= end_date)
    return query


@finance_bp.route("/api/finance/expenses", methods=["GET"])
def list_expenses():
    query = Expense.query.order_by(Expense.expense_date.desc(), Expense.expense_id.desc())
    start_date, end_date = _date_window()
    query = _apply_date_filter(query, Expense.expense_date, start_date, end_date)
    category = request.args.get("category", "").strip()
    if category:
        query = query.filter(func.lower(Expense.expense_category) == category.lower())
    return jsonify([_expense_to_row(row) for row in query.all()])


@finance_bp.route("/api/finance/expenses", methods=["POST"])
def create_expense():
    data = request.get_json(silent=True) or {}
    missing = [field for field in ("expense_date", "category", "amount") if not str(data.get(field, "")).strip()]
    if missing:
        return _json_error("Missing required expense fields", 400, missing)

    try:
        fy_id, user_id = _default_context()
        expense = Expense(
            financial_year_id=fy_id,
            expense_date=_parse_date(data.get("expense_date"), default=date_type.today()),
            expense_category=str(data.get("category", "")).strip(),
            amount=float(data.get("amount", 0) or 0),
            description=str(data.get("description", "")).strip(),
            is_gst_applicable=bool(data.get("is_gst_applicable", False)),
            gst_amount=float(data.get("gst_amount", 0) or 0),
            voucher_no=str(data.get("voucher_no", "")).strip(),
            user_id=user_id,
            is_active=bool(data.get("is_active", True)),
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify({"status": "success", "expense": _expense_to_row(expense)})
    except (ValueError, TypeError) as err:
        db.session.rollback()
        return _json_error("Invalid expense payload", 400, str(err))
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to save expense", 500, str(err))


@finance_bp.route("/api/finance/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id: int):
    expense = db.session.get(Expense, expense_id)
    if not expense:
        return _json_error("Expense not found", 404, {"id": expense_id})
    try:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"status": "success", "deleted": expense_id})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to delete expense", 500, str(err))


@finance_bp.route("/api/finance/summary", methods=["GET"])
def finance_summary():
    start_date, end_date = _date_window()
    sales_query = _sales_scope(start_date, end_date)
    purchase_query = _purchase_scope(start_date, end_date)
    return_query = _return_scope(start_date, end_date)
    expense_query = _expense_scope(start_date, end_date)
    adj_query = _apply_date_filter(StockAdjustment.query, StockAdjustment.adj_date, start_date, end_date)

    sales_total = float(
        db.session.query(func.coalesce(func.sum(SalesBill.net_amount), 0))
        .filter(SalesBill.bill_id.in_(sales_query.with_entities(SalesBill.bill_id)))
        .scalar()
    )
    tax_total = float(
        db.session.query(func.coalesce(func.sum(SalesBill.cgst_amount + SalesBill.sgst_amount + SalesBill.igst_amount), 0))
        .filter(SalesBill.bill_id.in_(sales_query.with_entities(SalesBill.bill_id)))
        .scalar()
    )
    purchase_total = float(
        db.session.query(func.coalesce(func.sum(PurchaseInvoice.net_amount), 0))
        .filter(PurchaseInvoice.purchase_id.in_(purchase_query.with_entities(PurchaseInvoice.purchase_id)))
        .scalar()
    )
    purchase_returns_total = float(
        db.session.query(func.coalesce(func.sum(PurchaseReturn.net_return_amount), 0))
        .filter(PurchaseReturn.purchase_return_id.in_(return_query.with_entities(PurchaseReturn.purchase_return_id)))
        .scalar()
    )
    expense_total = float(
        db.session.query(func.coalesce(func.sum(Expense.amount + Expense.gst_amount), 0))
        .filter(Expense.expense_id.in_(expense_query.with_entities(Expense.expense_id)))
        .scalar()
    )
    payment_query = _payment_scope(start_date, end_date)
    supplier_payables_total = float(
        db.session.query(func.coalesce(func.sum(PurchaseInvoice.net_amount), 0))
        .filter(PurchaseInvoice.purchase_id.in_(purchase_query.with_entities(PurchaseInvoice.purchase_id)))
        .scalar()
    ) - float(
        db.session.query(func.coalesce(func.sum(PurchaseReturn.net_return_amount), 0))
        .filter(PurchaseReturn.purchase_return_id.in_(return_query.with_entities(PurchaseReturn.purchase_return_id)))
        .scalar()
    ) - float(
        db.session.query(func.coalesce(func.sum(PurchasePayment.amount), 0))
        .filter(PurchasePayment.payment_id.in_(payment_query.with_entities(PurchasePayment.payment_id)))
        .scalar()
    )

    adjustment_loss = float(
        db.session.query(func.coalesce(func.sum(StockAdjustment.qty * StockBatch.purchase_rate), 0))
        .join(StockBatch, StockAdjustment.stock_batch_id == StockBatch.stock_batch_id)
        .filter(StockAdjustment.adjustment_id.in_(adj_query.with_entities(StockAdjustment.adjustment_id)))
        .filter(StockAdjustment.qty < 0)
        .scalar()
    )
    adjustment_loss = abs(adjustment_loss)

    cogs = float(
        db.session.query(func.coalesce(func.sum(SalesBillItem.qty_sold * SalesBillItem.purchase_rate_at_sale), 0))
        .filter(SalesBillItem.bill_id.in_(sales_query.with_entities(SalesBill.bill_id)))
        .scalar()
    )

    gross_profit = sales_total - cogs - adjustment_loss
    net_profit = gross_profit - expense_total
    bill_count = int(sales_query.count())

    return jsonify(
        {
            "sales_total": sales_total,
            "tax_total": tax_total,
            "purchase_total": purchase_total,
            "purchase_returns_total": purchase_returns_total,
            "expense_total": expense_total,
            "supplier_payables_total": max(0.0, supplier_payables_total),
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "adjustment_loss": adjustment_loss,
            "bill_count": bill_count,
            "daily_sales": [
                {
                    "date": row.day.isoformat(),
                    "bill_count": int(row.bill_count or 0),
                    "gross_sales": float(row.gross_sales or 0),
                    "discounts": float(row.discounts or 0),
                    "tax": float(row.tax or 0),
                    "net_sales": float(row.net_sales or 0),
                }
                for row in (
                    db.session.query(
                        SalesBill.bill_date.label("day"),
                        func.count(SalesBill.bill_id).label("bill_count"),
                        func.coalesce(func.sum(SalesBill.gross_amount), 0).label("gross_sales"),
                        func.coalesce(func.sum(SalesBill.discount_amount), 0).label("discounts"),
                        func.coalesce(func.sum(SalesBill.cgst_amount + SalesBill.sgst_amount + SalesBill.igst_amount), 0).label("tax"),
                        func.coalesce(func.sum(SalesBill.net_amount), 0).label("net_sales"),
                    )
                    .select_from(SalesBill)
                    .filter(SalesBill.bill_id.in_(sales_query.with_entities(SalesBill.bill_id)))
                    .group_by(SalesBill.bill_date)
                    .order_by(SalesBill.bill_date.asc())
                    .all()
                )
            ],
        }
    )


@finance_bp.route("/api/finance/daily-sales", methods=["GET"])
def daily_sales_report():
    start_date, end_date = _date_window()
    query = SalesBill.query.filter(SalesBill.is_cancelled.is_(False))
    query = _apply_date_filter(query, SalesBill.bill_date, start_date, end_date)
    rows = (
        db.session.query(
            SalesBill.bill_date.label("day"),
            func.count(SalesBill.bill_id).label("bill_count"),
            func.coalesce(func.sum(SalesBill.gross_amount), 0).label("gross_sales"),
            func.coalesce(func.sum(SalesBill.discount_amount), 0).label("discounts"),
            func.coalesce(func.sum(SalesBill.cgst_amount + SalesBill.sgst_amount + SalesBill.igst_amount), 0).label("tax"),
            func.coalesce(func.sum(SalesBill.net_amount), 0).label("net_sales"),
        )
        .select_from(SalesBill)
        .filter(SalesBill.bill_id.in_(query.with_entities(SalesBill.bill_id)))
        .group_by(SalesBill.bill_date)
        .order_by(SalesBill.bill_date.asc())
        .all()
    )
    return jsonify(
        [
            {
                "date": row.day.isoformat(),
                "bill_count": int(row.bill_count or 0),
                "gross_sales": float(row.gross_sales or 0),
                "discounts": float(row.discounts or 0),
                "tax": float(row.tax or 0),
                "net_sales": float(row.net_sales or 0),
            }
            for row in rows
        ]
    )


@finance_bp.route("/api/finance/profit-loss", methods=["GET"])
def profit_loss_report():
    start_date, end_date = _date_window()

    sales_query = SalesBill.query.filter(SalesBill.is_cancelled.is_(False))
    sales_query = _apply_date_filter(sales_query, SalesBill.bill_date, start_date, end_date)
    purchase_query = PurchaseInvoice.query
    purchase_query = _apply_date_filter(purchase_query, PurchaseInvoice.invoice_date, start_date, end_date)
    return_query = PurchaseReturn.query
    return_query = _apply_date_filter(return_query, PurchaseReturn.return_date, start_date, end_date)
    expense_query = Expense.query.filter(Expense.is_active.is_(True))
    expense_query = _apply_date_filter(expense_query, Expense.expense_date, start_date, end_date)
    adj_query = _apply_date_filter(StockAdjustment.query, StockAdjustment.adj_date, start_date, end_date)

    sales_total = float(db.session.query(func.coalesce(func.sum(SalesBill.net_amount), 0)).filter(SalesBill.bill_id.in_(sales_query.with_entities(SalesBill.bill_id))).scalar())
    tax_total = float(
        db.session.query(func.coalesce(func.sum(SalesBill.cgst_amount + SalesBill.sgst_amount + SalesBill.igst_amount), 0))
        .filter(SalesBill.bill_id.in_(sales_query.with_entities(SalesBill.bill_id)))
        .scalar()
    )
    purchase_total = float(
        db.session.query(func.coalesce(func.sum(PurchaseInvoice.net_amount), 0))
        .filter(PurchaseInvoice.purchase_id.in_(purchase_query.with_entities(PurchaseInvoice.purchase_id)))
        .scalar()
    )
    purchase_returns_total = float(
        db.session.query(func.coalesce(func.sum(PurchaseReturn.net_return_amount), 0))
        .filter(PurchaseReturn.purchase_return_id.in_(return_query.with_entities(PurchaseReturn.purchase_return_id)))
        .scalar()
    )
    expense_total = float(
        db.session.query(func.coalesce(func.sum(Expense.amount + Expense.gst_amount), 0))
        .filter(Expense.expense_id.in_(expense_query.with_entities(Expense.expense_id)))
        .scalar()
    )

    adjustment_loss = float(db.session.query(func.coalesce(func.sum(StockAdjustment.qty * StockBatch.purchase_rate), 0)).join(StockBatch, StockAdjustment.stock_batch_id == StockBatch.stock_batch_id).filter(StockAdjustment.adjustment_id.in_(adj_query.with_entities(StockAdjustment.adjustment_id))).filter(StockAdjustment.qty < 0).scalar())
    adjustment_loss = abs(adjustment_loss)
    cogs = float(db.session.query(func.coalesce(func.sum(SalesBillItem.qty_sold * SalesBillItem.purchase_rate_at_sale), 0)).filter(SalesBillItem.bill_id.in_(sales_query.with_entities(SalesBill.bill_id))).scalar())
    gross_profit = sales_total - cogs - adjustment_loss
    net_profit = gross_profit - expense_total

    return jsonify(
        {
            "sales_total": sales_total,
            "tax_total": tax_total,
            "purchase_total": purchase_total,
            "purchase_returns_total": purchase_returns_total,
            "expense_total": expense_total,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "adjustment_loss": adjustment_loss,
        }
    )


@finance_bp.route("/api/finance/supplier-payables", methods=["GET"])
def supplier_payables():
    start_date, end_date = _date_window()
    suppliers = Supplier.query.order_by(Supplier.supplier_name.asc()).all()
    rows = []
    for supplier in suppliers:
        purchase_query = PurchaseInvoice.query.filter(PurchaseInvoice.supplier_id == supplier.supplier_id)
        purchase_query = _apply_date_filter(purchase_query, PurchaseInvoice.invoice_date, start_date, end_date)
        returns_query = PurchaseReturn.query.filter(PurchaseReturn.supplier_id == supplier.supplier_id)
        returns_query = _apply_date_filter(returns_query, PurchaseReturn.return_date, start_date, end_date)
        payments_query = PurchasePayment.query.filter(PurchasePayment.supplier_id == supplier.supplier_id)
        payments_query = _apply_date_filter(payments_query, PurchasePayment.payment_date, start_date, end_date)

        purchases = float(
            db.session.query(func.coalesce(func.sum(PurchaseInvoice.net_amount), 0))
            .filter(PurchaseInvoice.purchase_id.in_(purchase_query.with_entities(PurchaseInvoice.purchase_id)))
            .scalar()
        )
        returns = float(
            db.session.query(func.coalesce(func.sum(PurchaseReturn.net_return_amount), 0))
            .filter(PurchaseReturn.purchase_return_id.in_(returns_query.with_entities(PurchaseReturn.purchase_return_id)))
            .scalar()
        )
        payments = float(
            db.session.query(func.coalesce(func.sum(PurchasePayment.amount), 0))
            .filter(PurchasePayment.payment_id.in_(payments_query.with_entities(PurchasePayment.payment_id)))
            .scalar()
        )
        payable = max(0.0, purchases - returns - payments)
        rows.append(
            {
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
                "purchases": purchases,
                "returns": returns,
                "payments": payments,
                "payable": payable,
                "credit_limit": float(supplier.credit_limit or 0),
                "credit_days": int(supplier.credit_days or 0),
            }
        )
    return jsonify(rows)


@finance_bp.route("/api/finance/supplier-payments", methods=["POST"])
def record_supplier_payment():
    data = request.get_json(silent=True) or {}
    supplier_id = data.get("supplier_id")
    amount = float(data.get("amount", 0) or 0)
    if not supplier_id:
        return _json_error("Missing required field: supplier_id", 400)
    if amount <= 0:
        return _json_error("Amount must be greater than zero", 400)

    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return _json_error("Supplier not found", 404, {"supplier_id": supplier_id})

    try:
        fy_id, user_id = _default_context()
        payment = PurchasePayment(
            supplier_id=supplier.supplier_id,
            purchase_id=None,
            payment_date=_parse_date(data.get("payment_date"), default=date_type.today()),
            amount=amount,
            payment_mode_id=int(data.get("payment_mode_id") or _payment_mode_id()),
            cheque_no=str(data.get("cheque_no", "")).strip(),
            bank_name=str(data.get("bank_name", "")).strip(),
            user_id=user_id,
            remarks=str(data.get("remarks", "")).strip(),
        )
        db.session.add(payment)
        db.session.commit()
        return jsonify({"status": "success", "payment": {
            "supplier_id": supplier.supplier_id,
            "amount": amount,
            "payment_date": payment.payment_date.isoformat(),
            "financial_year_id": fy_id,
        }})
    except Exception as err:
        db.session.rollback()
        return _json_error("Failed to record supplier payment", 500, str(err))
