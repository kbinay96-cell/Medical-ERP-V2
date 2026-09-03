"""
engines/sale_return_engine.py

Sale Return Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - generates Return Numbers (SRTN-0001 style, mirrors SINV-/PINV- pattern)
    - resolves each return line's read-only rate/discount/cc/tax by
      copying proportionally from the original sale_invoice_item (never
      re-entered, per confirmed scope)
    - enforces the cumulative-returned-qty rule via
      SaleReturnValidator + SaleInvoiceModel.get_returnable_items()
    - orchestrates validation before touching the database
      (models/sale_return_model.py)
    - posts stock re-entry through the EXISTING
      ItemEngine.post_stock_movement() -- no new stock-writing code
    - stamps BS-first audit fields via the shared Date Engine
    - enforces the Cancel = reversal-posting rule (never edits history,
      never deletes a Posted return -- only a Draft may be soft-deleted)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_return_validator import SaleReturnValidator
from models.sale_return_model import SaleReturnModel, SaleReturnSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_RETURN_PREFIX = "SRTN-"
DEFAULT_RETURN_PADDING = 4  # SRTN-0001


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; SaleReturnEngine falls back to AD-only stamps.")
        return None


@dataclass
class SaleReturnLineDTO:
    """Read-facing representation of one posted Sale Return line."""
    sale_return_item_id: int
    sale_invoice_item_id: int
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    return_qty: float
    rate: float
    discount_percent: float
    discount_amount: float
    cc_percent: float
    cc_amount: float
    tax_percent: float
    tax_amount: float
    amount: float
    remarks: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "SaleReturnLineDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


@dataclass
class SaleReturnDTO:
    """Read-facing representation returned by the Engine to callers."""
    sale_return_id: int
    return_number: str
    sale_invoice_id: int
    customer_id: int
    return_date_ad: Any
    return_date_bs: str
    return_reason: str
    refund_mode: str
    total_qty: float
    total_gross_amount: float
    total_discount_amount: float
    total_cc_amount: float
    total_tax_amount: float
    round_off: float
    grand_total: float
    status: str
    cancellation_reason: Optional[str]
    remarks: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    invoice_number: Optional[str] = None    # only populated by search() (joined)
    customer_name: Optional[str] = None     # only populated by search() (joined)
    lines: list[SaleReturnLineDTO] = None

    @classmethod
    def from_row(cls, row: dict, lines: Optional[list[SaleReturnLineDTO]] = None) -> "SaleReturnDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "lines"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, lines=lines or [])

    def to_dict(self) -> dict:
        return asdict(self)


class SaleReturnEngine:
    """Business-rule orchestration for the Sale Return module."""

    def __init__(
        self,
        model: Optional[SaleReturnModel] = None,
        sale_invoice_model=None,               # models.sale_invoice_model.SaleInvoiceModel -- REQUIRED, injected (shared instance)
        item_engine=None,                      # engines.item_engine.ItemEngine -- REQUIRED, injected (shared instance)
        date_engine: Optional[Any] = None,
        validator: Optional[SaleReturnValidator] = None,
    ) -> None:
        if sale_invoice_model is None:
            raise ValueError("SaleReturnEngine requires a sale_invoice_model instance (shared with the Sale module).")
        if item_engine is None:
            raise ValueError("SaleReturnEngine requires an item_engine instance (shared with the rest of the app).")

        self._model = model or SaleReturnModel()
        self._sale_invoice_model = sale_invoice_model
        self._item_engine = item_engine
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or SaleReturnValidator(
            return_number_exists_fn=self._return_number_exists,
            returned_qty_fn=self._model.get_returned_qty_for_invoice_item,
        )

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _return_number_exists(self, return_number: str, exclude_id: Optional[int] = None) -> bool:
        existing = self._model.search(SaleReturnSearchFilters(search_text=return_number, page_size=1))
        for row in existing:
            if row["return_number"] == return_number and row["sale_return_id"] != exclude_id:
                return True
        return False

    def _generate_return_number(self) -> str:
        """Sequential SRTN-0001 style, same approach as invoice_number generation."""
        latest = self._model.search(SaleReturnSearchFilters(page_size=1, include_deleted=True))
        next_seq = 1
        if latest:
            last_number = latest[0]["return_number"]
            try:
                next_seq = int(last_number.replace(DEFAULT_RETURN_PREFIX, "")) + 1
            except ValueError:
                next_seq = 1
        return f"{DEFAULT_RETURN_PREFIX}{next_seq:0{DEFAULT_RETURN_PADDING}d}"

    def _stamp_bs_date(self, ad_value: date) -> str:
        if self._date_engine is None:
            return ad_value.isoformat()
        try:
            return self._date_engine.ad_to_bs(ad_value)
        except Exception:
            logger.warning("BS conversion failed for %s; falling back to AD string.", ad_value)
            return ad_value.isoformat()

    def _build_line_from_original(self, return_row: dict, original: dict) -> dict:
        """
        Computes the proportional, read-only discount/cc/tax/amount for one
        return line from its original sale_invoice_item row -- NEVER
        re-entered by the user. Proportion is return_qty / original.qty.
        """
        return_qty = float(return_row["return_qty"])
        original_qty = float(original["qty"])
        proportion = return_qty / original_qty if original_qty else 0

        rate = float(original["rate"])
        discount_percent = float(original.get("discount_percent") or 0)
        discount_amount = round(float(original.get("discount_amount") or 0) * proportion, 2)
        cc_percent = float(original.get("cc_percent") or 0)
        cc_amount = round(float(original.get("cc_amount") or 0) * proportion, 2)
        tax_percent = float(original.get("tax_percent") or 0)
        tax_amount = round(float(original.get("tax_amount") or 0) * proportion, 2)
        amount = round((return_qty * rate) - discount_amount, 2)

        return {
            "sale_invoice_item_id": original["sale_invoice_item_id"],
            "item_id": original["item_id"],
            "item_batch_id": original["item_batch_id"],
            "batch_no": original["batch_no"],
            "expiry_month": original["expiry_month"],
            "expiry_year": original["expiry_year"],
            "return_qty": return_qty,
            "rate": rate,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "cc_percent": cc_percent,
            "cc_amount": cc_amount,
            "tax_percent": tax_percent,
            "tax_amount": tax_amount,
            "amount": amount,
            "remarks": return_row.get("remarks"),
        }

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_return(
        self,
        sale_invoice_id: int,
        customer_id: int,
        return_date_ad: date,
        return_reason: str,
        refund_mode: str,
        return_lines: list[dict],       # each: {"sale_invoice_item_id", "return_qty", "remarks"?}
        created_by: int,
        remarks: Optional[str] = None,
        status: str = "Posted",
    ) -> SaleReturnDTO:
        # 1. Load the original invoice's returnable lines -- single source of truth
        invoice = self._sale_invoice_model.get_by_id(sale_invoice_id)
        if invoice is None:
            raise RecordNotFoundError(f"Sale Invoice {sale_invoice_id} not found.")

        returnable_items = self._sale_invoice_model.get_returnable_items(sale_invoice_id)
        invoice_item_lookup = {row["sale_invoice_item_id"]: row for row in returnable_items}

        # 2. Validate header + lines BEFORE any computation
        header_data = {
            "sale_invoice_id": sale_invoice_id,
            "customer_id": customer_id,
            "return_date_bs": self._stamp_bs_date(return_date_ad),
            "return_reason": return_reason,
            "refund_mode": refund_mode,
            "status": status,
        }
        header_result = self._validator.validate_header(header_data)
        if not header_result.is_valid:
            raise ValidationError("; ".join(header_result.errors))

        lines_result = self._validator.validate_lines(return_lines, invoice_item_lookup)
        if not lines_result.is_valid:
            raise ValidationError("; ".join(lines_result.errors))

        # 3. Build computed, read-only line rows
        computed_lines = [
            self._build_line_from_original(row, invoice_item_lookup[row["sale_invoice_item_id"]])
            for row in return_lines
        ]

        # 4. Roll up header totals
        total_qty = sum(l["return_qty"] for l in computed_lines)
        total_gross_amount = round(sum(l["return_qty"] * l["rate"] for l in computed_lines), 2)
        total_discount_amount = round(sum(l["discount_amount"] for l in computed_lines), 2)
        total_cc_amount = round(sum(l["cc_amount"] for l in computed_lines), 2)
        total_tax_amount = round(sum(l["tax_amount"] for l in computed_lines), 2)
        grand_total = round(
            total_gross_amount - total_discount_amount + total_cc_amount + total_tax_amount, 2
        )

        # 5. Generate return_number, verify uniqueness (defensive re-check)
        return_number = self._generate_return_number()
        number_result = self._validator.validate_return_number_unique(return_number)
        if not number_result.is_valid:
            raise DuplicateRecordError("; ".join(number_result.errors))

        now_ad = datetime.now(timezone.utc)
        header_data.update({
            "return_number": return_number,
            "return_date_ad": return_date_ad,
            "total_qty": total_qty,
            "total_gross_amount": total_gross_amount,
            "total_discount_amount": total_discount_amount,
            "total_cc_amount": total_cc_amount,
            "total_tax_amount": total_tax_amount,
            "round_off": 0,
            "grand_total": grand_total,
            "remarks": remarks,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        })

        # 6. Persist header + lines in one transaction
        sale_return_id = self._model.insert_with_items(header_data, computed_lines)

        # 7. Only a Posted return moves stock
        if status == "Posted":
            for line in computed_lines:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=line["return_qty"],
                    transaction_type="SALE_RETURN",
                    reference_id=sale_return_id,
                    created_by=created_by,
                )

        return self.get_by_id(sale_return_id)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, sale_return_id: int) -> Optional[SaleReturnDTO]:
        row = self._model.get_by_id(sale_return_id)
        if row is None:
            return None
        item_rows = self._model.get_items_by_return_id(sale_return_id)
        lines = [SaleReturnLineDTO.from_row(r) for r in item_rows]
        return SaleReturnDTO.from_row(row, lines=lines)

    def search(self, filters: SaleReturnSearchFilters) -> list[SaleReturnDTO]:
        rows = self._model.search(filters)
        return [SaleReturnDTO.from_row(row) for row in rows]

    def get_returnable_lines(self, sale_invoice_id: int) -> list[dict]:
        """Convenience pass-through for the Screen -- remaining returnable qty per line."""
        rows = self._sale_invoice_model.get_returnable_items(sale_invoice_id)
        for row in rows:
            row["remaining_returnable_qty"] = float(row["qty"]) - float(row["already_returned_qty"])
        return rows

    # ------------------------------------------------------------------ #
    # CANCEL -- reversal posting, never an edit of history
    # ------------------------------------------------------------------ #
    def cancel_return(self, sale_return_id: int, cancellation_reason: str, updated_by: int) -> SaleReturnDTO:
        existing = self._model.get_by_id(sale_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Sale Return {sale_return_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("This Sale Return is already Cancelled.")

        reason_result = self._validator.validate_cancellation(cancellation_reason)
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        # Reverse the stock effect ONLY if it was Posted (a Draft never moved stock)
        if existing["status"] == "Posted":
            item_rows = self._model.get_items_by_return_id(sale_return_id)
            for line in item_rows:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=-float(line["return_qty"]),
                    transaction_type="SALE_RETURN_CANCEL",
                    reference_id=sale_return_id,
                    created_by=updated_by,
                )

        now_ad = datetime.now(timezone.utc)
        self._model.cancel(
            sale_return_id=sale_return_id,
            cancellation_reason=cancellation_reason,
            updated_by=updated_by,
            updated_at_ad=now_ad,
            updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(sale_return_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE -- Draft only (a Posted or Cancelled return is never deleted, only cancelled)
    # ------------------------------------------------------------------ #
    def delete_draft(self, sale_return_id: int, deleted_by: int) -> None:
        existing = self._model.get_by_id(sale_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Sale Return {sale_return_id} not found.")
        if existing["status"] != "Draft":
            raise ValidationError("Only a Draft Sale Return can be deleted. Use Cancel for a Posted return.")

        now_ad = datetime.now(timezone.utc)
        self._model.soft_delete(
            sale_return_id=sale_return_id,
            deleted_by=deleted_by,
            deleted_at_ad=now_ad,
            deleted_at_bs=self._stamp_bs_date(now_ad.date()),
        )