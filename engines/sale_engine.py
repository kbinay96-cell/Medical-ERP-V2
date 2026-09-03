# engines/sale_engine.py
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_validator import SaleInvoiceValidator
from models.sale_invoice_model import SaleInvoiceModel, SaleInvoiceSearchFilters

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# DTOs
# --------------------------------------------------------------------------- #

@dataclass
class SaleInvoiceLineDTO:
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    entry_mode: str  # "free_qty" | "net_rate"
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
    sale_mode: str
    payment_type: str
    grand_total: float
    amount_paid_now: float
    balance_amount: float
    status: str
    area_id: Optional[int] = None
    price_level_id: Optional[int] = None
    lines: list[SaleInvoiceLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Partial-success exception
# --------------------------------------------------------------------------- #

class EngineErrorWithInvoice(Exception):
    """
    Raised by create_sale_invoice() when the invoice itself saved
    cleanly but one or more per-line stock deductions failed. Carries
    the saved DTO so the Screen can tell the user "invoice X was
    created, but: ..." rather than silently hiding a partial-stock
    situation.
    """

    def __init__(self, dto: SaleInvoiceDTO, stock_errors: list[str]) -> None:
        self.dto = dto
        self.stock_errors = stock_errors
        super().__init__(
            f"Invoice {dto.invoice_number} saved, but stock errors: {'; '.join(stock_errors)}"
        )


# --------------------------------------------------------------------------- #
# ENGINE
# --------------------------------------------------------------------------- #

class SaleEngine:
    """
    Business-rule orchestration for Sales Invoice.

    Screens call ONLY this class. Stock is never written here — every
    deduction goes through ItemEngine.post_stock_movement(transaction_type='SALE').
    """

    def __init__(
        self,
        model: SaleInvoiceModel,
        item_engine,
        item_free_scheme_engine,
        country_tax_lookup_fn: Callable[[int], float],
        manufacturer_lookup_fn: Callable[[int], dict],
    ) -> None:
        self._model = model
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._country_tax_lookup_fn = country_tax_lookup_fn
        self._manufacturer_lookup_fn = manufacturer_lookup_fn
        self._validator = SaleInvoiceValidator(
            number_exists_fn=self._model.get_by_invoice_number,
        )

    # ------------------------------------------------------------------ #
    # SETTINGS
    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_setting(key: str, default=None):
        from engines.settings_engine import get_setting
        return get_setting(key, default)

    def is_wholesale_mode(self) -> bool:
        """Single source of truth: reads sale.column_show_free. When ON,
        the Free column is visible and free-scheme + CC logic run (Wholesale).
        When OFF, free-scheme logic does not run at all (Retail)."""
        return bool(self._get_setting("sale.column_show_free", False))

    # ------------------------------------------------------------------ #
    # NUMBER GENERATION
    # ------------------------------------------------------------------ #
    def generate_invoice_number(self) -> str:
        prefix = self._get_setting("sale.invoice_prefix", "SINV-")
        next_seq = self._model.get_last_invoice_sequence(prefix) + 1
        return f"{prefix}{next_seq:04d}"

    # ------------------------------------------------------------------ #
    # LINE COMPUTATION (preview + save both use this)
    # ------------------------------------------------------------------ #
    def compute_line(self, line_input: dict, is_wholesale: bool) -> dict:
        """
        Computes a single Sale Invoice line from raw user input. Resolves
        item, batch (read-only auto-pick), rate, free scheme, discount, CC
        on free goods, and tax. Returns a dict ready for insert.
        """
        item_id = line_input["item_id"]
        entry_mode = line_input.get("entry_mode", "free_qty")
        qty = float(line_input["qty"])

        item_dto = self._item_engine.get_item(item_id)
        batch = self._pick_nearest_expiry_batch(item_id)
        if batch is None:
            raise ValidationError([f"Item '{item_dto.item_name}' has no available stock to sell."])

        current_rate = float(item_dto.sale_rate or 0)
        rate = float(line_input.get("rate") if line_input.get("rate") is not None else current_rate)

        free_qty = 0.0
        if is_wholesale:
            scheme = self._item_free_scheme_engine.get_scheme_for_item(item_id)
            if scheme is not None:
                scheme_qty, scheme_free = scheme
                if entry_mode == "net_rate":
                    if line_input.get("rate") is None:
                        rate = self._compute_net_rate(current_rate, scheme_qty, scheme_free)
                else:
                    if line_input.get("free_qty") is None:
                        free_qty = self._compute_auto_free_qty(qty, scheme_qty, scheme_free)
                    else:
                        free_qty = float(line_input["free_qty"])

        discount_percent = float(line_input.get("discount_percent", 0) or 0)
        gross = qty * rate
        discount_amount = gross * discount_percent / 100

        cc_percent = 0.0
        cc_amount = 0.0
        if is_wholesale and free_qty > 0:
            cc_percent = self._resolve_cc_percent(item_dto.manufacturer_id)
            purchase_rate = float(item_dto.purchase_rate or 0)
            cc_amount = free_qty * purchase_rate * cc_percent / 100

        tax_percent = 0.0
        tax_amount = 0.0
        if self._get_setting("sale.column_show_tax", False):
            vat_percent, _custom_percent = self._item_engine.resolve_item_tax(item_id)
            tax_percent = vat_percent
            tax_amount = gross * tax_percent / 100

        amount = gross - discount_amount

        return {
            "item_id": item_id,
            "item_batch_id": batch["item_batch_id"],
            "batch_no": batch["batch_no"],
            "expiry_month": batch["expiry_month"],
            "expiry_year": batch["expiry_year"],
            "entry_mode": entry_mode,
            "qty": qty,
            "free_qty": free_qty,
            "rate": round(rate, 4),
            "discount_percent": discount_percent,
            "discount_amount": round(discount_amount, 4),
            "cc_percent": round(cc_percent, 4),
            "cc_amount": round(cc_amount, 4),
            "tax_percent": round(tax_percent, 4),
            "tax_amount": round(tax_amount, 4),
            "amount": round(amount, 4),
        }

    # ------------------------------------------------------------------ #
    # FREE SCHEME HELPERS
    # ------------------------------------------------------------------ #
    def _compute_auto_free_qty(self, qty: float, scheme_qty: float, scheme_free: float) -> float:
        allow_half_free = bool(self._get_setting("sale.allow_half_free", False))
        minimum_auto_free = float(self._get_setting("sale.minimum_auto_free_qty", 1))

        if allow_half_free:
            free_qty = (qty / scheme_qty) * scheme_free
        else:
            free_qty = (qty // scheme_qty) * scheme_free

        free_qty = round(free_qty, 4)
        if free_qty < minimum_auto_free:
            return 0.0
        return free_qty

    def _compute_net_rate(self, current_rate: float, scheme_qty: float, scheme_free: float) -> float:
        if scheme_qty + scheme_free == 0:
            return current_rate
        return round(current_rate * scheme_qty / (scheme_qty + scheme_free), 4)

    # ------------------------------------------------------------------ #
    # BATCH + TAX RESOLUTION
    # ------------------------------------------------------------------ #
    def _pick_nearest_expiry_batch(self, item_id: int) -> Optional[dict]:
        """Reuses ItemEngine.get_batches() (already expiry-ascending) rather
        than duplicating the ordering logic -- takes the first non-zero-qty
        batch. No new sorting code, per project's 'No Duplicate Logic' rule."""
        batches = self._item_engine.get_batches(item_id)
        for batch_dto in batches:
            if float(batch_dto.batch_qty) > 0:
                if hasattr(batch_dto, 'to_dict'):
                    return batch_dto.to_dict()
                return vars(batch_dto)
        return None

    def _resolve_cc_percent(self, manufacturer_id: int) -> float:
        try:
            manufacturer = self._manufacturer_lookup_fn(manufacturer_id) or {}
            country_id = manufacturer.get("country_id")
            if country_id is None:
                return 0.0
            country_tax = self._country_tax_lookup_fn(country_id) or {}
            return float(country_tax.get("custom_percent") or 0.0)
        except Exception:
            logger.exception("Failed to resolve CC%% for manufacturer_id=%s", manufacturer_id)
            return 0.0

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_sale_invoice(self, payload: dict, current_user_id: int) -> SaleInvoiceDTO:
        is_wholesale = self.is_wholesale_mode()

        header_errors = self._validator.validate_header(payload)
        if not header_errors.is_valid:
            raise ValidationError(header_errors.errors)

        raw_lines = payload.get("lines") or []
        line_errors = self._validator.validate_lines(raw_lines)
        if not line_errors.is_valid:
            raise ValidationError(line_errors.errors)

        computed_lines = [self.compute_line(line, is_wholesale) for line in raw_lines]

        total_qty = sum(l["qty"] for l in computed_lines)
        total_free_qty = sum(l["free_qty"] for l in computed_lines)
        total_gross_amount = sum(l["qty"] * l["rate"] for l in computed_lines)
        total_discount_amount = sum(l["discount_amount"] for l in computed_lines)
        total_cc_amount = sum(l["cc_amount"] for l in computed_lines)
        total_tax_amount = sum(l["tax_amount"] for l in computed_lines)
        subtotal = sum(l["amount"] for l in computed_lines) + total_cc_amount + total_tax_amount
        grand_total_raw = subtotal
        grand_total = round(grand_total_raw)
        round_off = grand_total - grand_total_raw

        invoice_number = self.generate_invoice_number()
        now_ad = datetime.now(timezone.utc)
        now_bs = self._now_bs(now_ad)

        header_data = {
            "invoice_number": invoice_number,
            "customer_id": payload["customer_id"],
            "area_id": payload.get("area_id"),
            "price_level_id": payload.get("price_level_id"),
            "invoice_date_ad": payload.get("invoice_date_ad") or now_ad.date(),
            "invoice_date_bs": payload["invoice_date_bs"],
            "sale_mode": "Wholesale" if is_wholesale else "Retail",
            "total_qty": total_qty,
            "total_free_qty": total_free_qty,
            "total_gross_amount": total_gross_amount,
            "total_discount_amount": total_discount_amount,
            "total_cc_amount": total_cc_amount,
            "total_tax_amount": total_tax_amount,
            "round_off": round_off,
            "grand_total": grand_total,
            "payment_type": payload.get("payment_type"),
            "amount_paid_now": payload.get("amount_paid_now", 0) or 0,
            "status": payload.get("status", "Posted"),
            "remarks": (payload.get("remarks") or "").strip() or None,
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert_with_items(header_data, computed_lines)
        except Exception as exc:
            if self._is_unique_violation(exc):
                raise DuplicateRecordError("Invoice Number already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting sale invoice.")
            raise

        stock_errors: list[str] = []
        for line in computed_lines:
            total_deduction = line["qty"] + line["free_qty"]
            try:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    transaction_type="SALE",
                    quantity_change=-total_deduction,
                    current_user_id=current_user_id,
                    reference_type="sale_invoice",
                    reference_id=new_id,
                )
            except Exception as exc:
                logger.exception("Stock deduction failed for line item_id=%s", line["item_id"])
                stock_errors.append(f"Item {line['item_id']}: {exc}")

        if stock_errors:
            dto = self._to_dto(self._model.get_by_id(new_id, include_deleted=False))
            raise EngineErrorWithInvoice(dto, stock_errors)

        return self._to_dto(self._model.get_by_id(new_id, include_deleted=False))

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_sale_invoice(self, sale_invoice_id: int) -> SaleInvoiceDTO:
        row = self._model.get_by_id(sale_invoice_id, include_deleted=False)
        if row is None:
            raise RecordNotFoundError(f"Sale invoice {sale_invoice_id} not found.")
        return self._to_dto(row)

    def search_sale_invoices(
        self,
        search_text: Optional[str] = None,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        sale_mode: Optional[str] = None,
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
            sale_mode=sale_mode,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_dir=order_dir,
        )
        rows, total_count = self._model.search(filters)
        results = [self._to_dto(r) for r in rows]
        return results, total_count

    # ------------------------------------------------------------------ #
    # CANCEL
    # ------------------------------------------------------------------ #
    def cancel_sale_invoice(self, sale_invoice_id: int, current_user_id: int, reason: str) -> None:
        if not reason or not str(reason).strip():
            raise ValidationError(["A cancellation reason is required."])
        existing = self._model.get_by_id(sale_invoice_id, include_deleted=False)
        if existing is None:
            raise RecordNotFoundError(f"Sale invoice {sale_invoice_id} not found.")
        now_ad = datetime.now(timezone.utc)
        now_bs = self._now_bs(now_ad)
        self._model.soft_delete(
            sale_invoice_id=sale_invoice_id,
            deleted_by=current_user_id,
            deleted_at_ad=now_ad,
            deleted_at_bs=now_bs or "",
            reason=reason.strip(),
        )

    # ------------------------------------------------------------------ #
    # INTERNALS
    # ------------------------------------------------------------------ #
    def _to_dto(self, row: dict) -> SaleInvoiceDTO:
        line_rows = self._model.get_items_by_invoice(row["sale_invoice_id"])
        lines = [
            SaleInvoiceLineDTO(
                item_id=r["item_id"],
                item_batch_id=r["item_batch_id"],
                batch_no=r["batch_no"],
                expiry_month=r["expiry_month"],
                expiry_year=r["expiry_year"],
                entry_mode=r.get("entry_mode", "free_qty"),
                qty=float(r["qty"]),
                free_qty=float(r["free_qty"]),
                rate=float(r["rate"]),
                discount_percent=float(r["discount_percent"]),
                discount_amount=float(r["discount_amount"]),
                cc_percent=float(r["cc_percent"]),
                cc_amount=float(r["cc_amount"]),
                tax_percent=float(r["tax_percent"]),
                tax_amount=float(r["tax_amount"]),
                amount=float(r["amount"]),
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
            sale_mode=row.get("sale_mode", "Retail"),
            payment_type=row.get("payment_type", "Cash"),
            grand_total=float(row["grand_total"]),
            amount_paid_now=float(row.get("amount_paid_now", 0) or 0),
            balance_amount=float(row.get("balance_amount", 0) or 0),
            status=row["status"],
            area_id=row.get("area_id"),
            price_level_id=row.get("price_level_id"),
            lines=lines,
        )

    @staticmethod
    def _now_bs(now_ad=None) -> str:
        try:
            from engines.date_engine import ad_to_bs
            return ad_to_bs((now_ad or datetime.now(timezone.utc)).date())
        except Exception:
            logger.warning("Could not convert AD->BS.")
            return ""

    @staticmethod
    def _is_unique_violation(exc: Exception) -> bool:
        return "unique" in str(exc).lower() or "duplicate" in str(exc).lower()


__all__ = ["SaleEngine", "SaleInvoiceDTO", "SaleInvoiceLineDTO", "EngineErrorWithInvoice"]
