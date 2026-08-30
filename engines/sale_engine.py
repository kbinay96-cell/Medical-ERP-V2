# engines/sale_engine.py
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_validator import SaleValidator
from models.sale_invoice_model import SaleInvoiceModel, SaleInvoiceSearchFilters

logger = logging.getLogger(__name__)


def _ve(message: str) -> None:
    raise ValidationError([message])


@dataclass
class SaleInvoiceLineDTO:
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    qty: float
    free_qty: float
    rate: float
    discount_percent: float
    discount_amount: float = 0.0
    cc_percent: float = 0.0
    cc_amount: float = 0.0
    tax_percent: float = 0.0
    tax_amount: float = 0.0
    amount: float = 0.0


@dataclass
class SaleInvoiceDTO:
    sale_invoice_id: Optional[int]
    invoice_number: str
    customer_id: int
    customer_name: str
    invoice_date_bs: str
    payment_mode: str
    grand_total: float
    paid_amount: float
    balance_amount: float
    status: str
    lines: list[SaleInvoiceLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class SaleEngine:
    """Business-rule orchestration for Sales Invoice.

    Screens call ONLY this class. Stock is never written here — every
    deduction goes through ItemEngine.post_stock_movement(transaction_type='SALE').
    """

    def __init__(self, model: SaleInvoiceModel, date_engine, item_engine) -> None:
        self._model = model
        self._date_engine = date_engine
        self._item_engine = item_engine

    def generate_invoice_number(self) -> str:
        from engines.settings_engine import get_setting

        prefix = get_setting("sale.invoice_prefix", "SINV-")
        next_seq = self._model.get_last_invoice_sequence(prefix) + 1
        return f"{prefix}{next_seq:04d}"

    def _calculate_line(self, line: SaleInvoiceLineDTO) -> SaleInvoiceLineDTO:
        discount_amount = line.qty * line.rate * (line.discount_percent / 100.0)
        taxable = (line.qty * line.rate) - discount_amount
        cc_amount = line.free_qty * line.rate * (line.cc_percent / 100.0)
        tax_amount = taxable * (line.tax_percent / 100.0)
        amount = taxable + cc_amount + tax_amount
        line.discount_amount = round(discount_amount, 4)
        line.cc_amount = round(cc_amount, 4)
        line.tax_amount = round(tax_amount, 4)
        line.amount = round(amount, 4)
        return line

    def _resolve_tax_percent(self, item_id: int) -> float:
        try:
            vat_percent, _custom = self._item_engine.resolve_item_tax(item_id)
            return float(vat_percent or 0.0)
        except Exception:
            logger.exception("Failed to resolve VAT%% for item_id=%s", item_id)
            return 0.0

    def _resolve_cc_percent(self, item_id: int) -> float:
        try:
            _vat, custom_percent = self._item_engine.resolve_item_tax(item_id)
            return float(custom_percent or 0.0)
        except Exception:
            logger.exception("Failed to resolve CC%% for item_id=%s", item_id)
            return 0.0

    def _invoice_date_ad(self, invoice_date_bs: str) -> date:
        from engines.date_engine import DateEngineError, bs_to_ad

        try:
            return bs_to_ad(invoice_date_bs)
        except DateEngineError:
            logger.exception("Could not convert BS invoice date %s to AD", invoice_date_bs)
            return date.today()

    def _now_stamps(self) -> tuple[datetime, Optional[str]]:
        from engines.date_engine import DateEngineError, ad_to_bs

        now_ad = datetime.now(timezone.utc)
        try:
            now_bs = ad_to_bs(now_ad.date())
        except DateEngineError:
            logger.exception("Could not resolve BS date for sale invoice audit stamp")
            now_bs = None
        return now_ad, now_bs

    def create_sale_invoice(self, payload: dict[str, Any], current_user_id: int) -> SaleInvoiceDTO:
        is_valid, error = SaleValidator.validate_invoice_header(payload)
        if not is_valid:
            _ve(error)

        raw_lines = payload.get("lines") or []
        for raw_line in raw_lines:
            is_valid, error = SaleValidator.validate_invoice_line(raw_line)
            if not is_valid:
                _ve(error)

        lines: list[SaleInvoiceLineDTO] = []
        needed_by_batch: dict[int, float] = {}

        for raw_line in raw_lines:
            item_batch_id = int(raw_line["item_batch_id"])
            batch = self._item_engine.get_batch(item_batch_id)
            if batch.item_id != int(raw_line["item_id"]):
                _ve(f"Batch '{batch.batch_no}' does not belong to the selected item.")

            qty = float(raw_line.get("qty") or 0.0)
            free_qty = float(raw_line.get("free_qty") or 0.0)
            needed_by_batch[item_batch_id] = needed_by_batch.get(item_batch_id, 0.0) + qty + free_qty

            dto_line = SaleInvoiceLineDTO(
                item_id=int(raw_line["item_id"]),
                item_batch_id=item_batch_id,
                batch_no=batch.batch_no,
                expiry_month=int(batch.expiry_month),
                expiry_year=int(batch.expiry_year),
                qty=qty,
                free_qty=free_qty,
                rate=float(raw_line.get("rate") or 0.0),
                discount_percent=float(raw_line.get("discount_percent") or 0.0),
                tax_percent=self._resolve_tax_percent(int(raw_line["item_id"])),
                cc_percent=self._resolve_cc_percent(int(raw_line["item_id"])),
            )
            lines.append(self._calculate_line(dto_line))

        for item_batch_id, needed in needed_by_batch.items():
            batch = self._item_engine.get_batch(item_batch_id)
            if float(batch.batch_qty) < needed:
                _ve(
                    f"Insufficient stock for batch '{batch.batch_no}' "
                    f"(available {batch.batch_qty}, needed {needed})."
                )

        raw_total = sum(l.amount for l in lines)
        bill_discount_amount = round(float(payload.get("bill_discount_amount") or 0.0), 4)
        if bill_discount_amount < 0:
            _ve("Bill discount cannot be negative.")
        if bill_discount_amount > raw_total:
            _ve("Bill discount cannot exceed the invoice total.")

        total_after_discount = raw_total - bill_discount_amount
        grand_total = round(total_after_discount)
        round_off_amount = round(grand_total - total_after_discount, 2)

        payment_mode = (payload.get("payment_mode") or "Cash").strip()
        if payment_mode == "Cash":
            paid_amount = grand_total
        elif payment_mode == "Credit":
            paid_amount = 0.0
        else:
            paid_amount = round(float(payload.get("paid_amount") or 0.0), 4)
            if paid_amount > grand_total:
                _ve("Paid amount cannot exceed grand total.")

        balance_amount = round(grand_total - paid_amount, 4)

        customer_id = int(payload["customer_id"])
        self._enforce_credit_limit(customer_id, balance_amount)

        now_ad, now_bs = self._now_stamps()
        invoice_number = self.generate_invoice_number()
        invoice_date_bs = str(payload["invoice_date_bs"]).strip()
        invoice_date_ad = self._invoice_date_ad(invoice_date_bs)

        new_invoice_id = self._model.insert_invoice(
            {
                "invoice_number": invoice_number,
                "customer_id": customer_id,
                "invoice_date_ad": invoice_date_ad,
                "invoice_date_bs": invoice_date_bs,
                "payment_mode": payment_mode,
                "total_qty": round(sum(l.qty + l.free_qty for l in lines), 4),
                "total_gross_amount": round(sum(l.qty * l.rate for l in lines), 4),
                "total_discount_amount": round(sum(l.discount_amount for l in lines) + bill_discount_amount, 4),
                "total_cc_amount": round(sum(l.cc_amount for l in lines), 4),
                "total_tax_amount": round(sum(l.tax_amount for l in lines), 4),
                "bill_discount_amount": bill_discount_amount,
                "round_off_amount": round_off_amount,
                "grand_total": grand_total,
                "paid_amount": paid_amount,
                "balance_amount": balance_amount,
                "status": "Posted",
                "remarks": (payload.get("remarks") or None),
                "created_by": current_user_id,
                "created_at_ad": now_ad,
                "created_at_bs": now_bs,
            }
        )

        for dto_line in lines:
            self._model.insert_invoice_item(
                new_invoice_id,
                {
                    "item_id": dto_line.item_id,
                    "item_batch_id": dto_line.item_batch_id,
                    "batch_no": dto_line.batch_no,
                    "expiry_month": dto_line.expiry_month,
                    "expiry_year": dto_line.expiry_year,
                    "qty": dto_line.qty,
                    "free_qty": dto_line.free_qty,
                    "rate": dto_line.rate,
                    "discount_percent": dto_line.discount_percent,
                    "discount_amount": dto_line.discount_amount,
                    "cc_percent": dto_line.cc_percent,
                    "cc_amount": dto_line.cc_amount,
                    "tax_percent": dto_line.tax_percent,
                    "tax_amount": dto_line.tax_amount,
                    "amount": dto_line.amount,
                },
            )

        for item_batch_id, needed in needed_by_batch.items():
            self._item_engine.post_stock_movement(
                item_batch_id=item_batch_id,
                transaction_type="SALE",
                quantity_change=-needed,
                current_user_id=current_user_id,
                reference_type="sale_invoice",
                reference_id=new_invoice_id,
                remarks=f"Sale {invoice_number}",
            )

        customer_name = ""
        try:
            from engines.customer_engine import get_customer

            customer = get_customer(customer_id) or {}
            customer_name = customer.get("customer_name") or ""
        except Exception:
            logger.exception("Could not load customer name for sale invoice %s", new_invoice_id)

        return SaleInvoiceDTO(
            sale_invoice_id=new_invoice_id,
            invoice_number=invoice_number,
            customer_id=customer_id,
            customer_name=customer_name,
            invoice_date_bs=invoice_date_bs,
            payment_mode=payment_mode,
            grand_total=grand_total,
            paid_amount=paid_amount,
            balance_amount=balance_amount,
            status="Posted",
            lines=lines,
        )

    def _enforce_credit_limit(self, customer_id: int, this_balance: float) -> None:
        if this_balance <= 0:
            return
        try:
            from engines.customer_engine import get_customer

            customer = get_customer(customer_id)
        except Exception:
            logger.exception("Credit-limit check: could not load customer %s", customer_id)
            return
        if not customer:
            _ve("Customer was not found.")
        credit_limit = float(customer.get("credit_limit") or 0)
        if credit_limit <= 0:
            return
        outstanding = self._model.get_customer_outstanding(customer_id)
        if outstanding + this_balance > credit_limit:
            _ve(
                f"This sale would exceed the customer's credit limit "
                f"(limit {credit_limit:.2f}, outstanding {outstanding:.2f}, "
                f"this bill due {this_balance:.2f})."
            )

    def get_sale_invoice(self, sale_invoice_id: int, include_deleted: bool = False) -> SaleInvoiceDTO:
        row = self._model.get_by_id(sale_invoice_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Sale invoice {sale_invoice_id} not found.")
        line_rows = self._model.get_items_by_invoice(sale_invoice_id)
        lines = [
            SaleInvoiceLineDTO(
                item_id=int(r["item_id"]),
                item_batch_id=int(r["item_batch_id"]),
                batch_no=r["batch_no"],
                expiry_month=int(r["expiry_month"]),
                expiry_year=int(r["expiry_year"]),
                qty=float(r["qty"]),
                free_qty=float(r["free_qty"] or 0),
                rate=float(r["rate"]),
                discount_percent=float(r["discount_percent"] or 0),
                discount_amount=float(r["discount_amount"] or 0),
                cc_percent=float(r["cc_percent"] or 0),
                cc_amount=float(r["cc_amount"] or 0),
                tax_percent=float(r["tax_percent"] or 0),
                tax_amount=float(r["tax_amount"] or 0),
                amount=float(r["amount"] or 0),
            )
            for r in line_rows
        ]
        customer_name = row.get("customer_name") or ""
        if not customer_name:
            try:
                from engines.customer_engine import get_customer

                customer = get_customer(row["customer_id"]) or {}
                customer_name = customer.get("customer_name") or ""
            except Exception:
                customer_name = ""
        return SaleInvoiceDTO(
            sale_invoice_id=row["sale_invoice_id"],
            invoice_number=row["invoice_number"],
            customer_id=row["customer_id"],
            customer_name=customer_name,
            invoice_date_bs=row["invoice_date_bs"],
            payment_mode=row["payment_mode"],
            grand_total=float(row["grand_total"]),
            paid_amount=float(row["paid_amount"]),
            balance_amount=float(row["balance_amount"]),
            status=row["status"],
            lines=lines,
        )

    def search_sale_invoices(
        self,
        search_text: Optional[str] = None,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
        order_by: Optional[str] = None,
        order_dir: str = "DESC",
    ) -> tuple[list[SaleInvoiceDTO], int]:
        filters = SaleInvoiceSearchFilters(
            search_text=search_text,
            customer_id=customer_id,
            status=status,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_dir=order_dir,
        )
        rows, total_count = self._model.search(filters)
        results = [
            SaleInvoiceDTO(
                sale_invoice_id=r["sale_invoice_id"],
                invoice_number=r["invoice_number"],
                customer_id=r["customer_id"],
                customer_name=r.get("customer_name") or "",
                invoice_date_bs=r["invoice_date_bs"],
                payment_mode=r["payment_mode"],
                grand_total=float(r["grand_total"]),
                paid_amount=float(r["paid_amount"]),
                balance_amount=float(r["balance_amount"]),
                status=r["status"],
                lines=[],
            )
            for r in rows
        ]
        return results, total_count

    def cancel_sale_invoice(self, sale_invoice_id: int, current_user_id: int, reason: str) -> None:
        """Soft-delete only. Does NOT reverse stock — that is Sale Return."""
        if not reason or not str(reason).strip():
            _ve("A cancellation reason is required.")
        existing = self._model.get_by_id(sale_invoice_id, include_deleted=False)
        if existing is None:
            raise RecordNotFoundError(f"Sale invoice {sale_invoice_id} not found.")
        now_ad, now_bs = self._now_stamps()
        self._model.soft_delete(
            sale_invoice_id=sale_invoice_id,
            deleted_by=current_user_id,
            deleted_at_ad=now_ad,
            deleted_at_bs=now_bs or "",
            reason=reason.strip(),
        )
