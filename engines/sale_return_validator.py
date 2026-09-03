"""
engines/sale_return_validator.py

Sale Return Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- never touches the database directly except via
injected callback functions from the Engine (which owns the Model).
Mirrors engines/sale_validator.py's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
VALID_REFUND_MODES = ("Adjust Against Invoice", "Advance", "Cash Refund")
VALID_RETURN_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class SaleReturnValidator:
    """
    Stateless validation rules for Sale Return header + lines. Does NOT
    compute anything (no proportional discount/cc/tax math, no stock
    posting) -- it only checks that what the Engine is about to save is
    structurally sound and within the remaining returnable quantity.
    All computation lives in SaleReturnEngine, same separation used
    between SaleInvoiceValidator and SaleEngine.
    """

    def __init__(
        self,
        return_number_exists_fn: Callable[[str, Optional[int]], bool],
        returned_qty_fn: Callable[[int], float],
    ) -> None:
        self._return_number_exists_fn = return_number_exists_fn
        # returned_qty_fn(sale_invoice_item_id) -> already-returned qty,
        # injected so the Validator never touches the Model directly.
        self._returned_qty_fn = returned_qty_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("sale_invoice_id"):
            result.add("Original Sale Invoice is mandatory.")

        if not data.get("customer_id"):
            result.add("Customer is mandatory.")

        if not data.get("return_date_bs"):
            result.add("Return Date (BS) is mandatory.")

        return_reason = (data.get("return_reason") or "").strip()
        if not return_reason:
            result.add("Return Reason is mandatory.")
        elif len(return_reason) > MAX_LEN_REASON:
            result.add(f"Return Reason must not exceed {MAX_LEN_REASON} characters.")

        refund_mode = data.get("refund_mode", "Adjust Against Invoice")
        if refund_mode not in VALID_REFUND_MODES:
            result.add(f"Refund Mode must be one of {VALID_REFUND_MODES}.")

        status = data.get("status", "Posted")
        if status not in VALID_RETURN_STATUSES:
            result.add("Status must be one of Draft, Posted, Cancelled.")

        return result

    def validate_return_number_unique(self, return_number: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        number = (return_number or "").strip()
        if not number:
            result.add("Return Number is required.")
        elif self._return_number_exists_fn(number, exclude_id):
            result.add(f"Return Number '{number}' already exists.")
        return result

    def validate_lines(self, line_rows: list[dict], invoice_item_lookup: dict[int, dict]) -> ValidationResult:
        """
        Validates the whole return-line list at once against the original
        invoice's lines. `invoice_item_lookup` maps
        sale_invoice_item_id -> that line's original row (from
        SaleInvoiceModel.get_returnable_items()), so this method never
        queries the database itself.

        Called by the Engine BEFORE any proportional discount/cc/tax
        computation runs -- a structurally bad or over-quantity line list
        is rejected early, never partially computed or partially posted.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("At least one return line is required.")
            return result

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"
            invoice_item_id = row.get("sale_invoice_item_id")

            if not invoice_item_id:
                result.add(f"{prefix}: Original invoice line reference is required.")
                continue

            original = invoice_item_lookup.get(invoice_item_id)
            if original is None:
                result.add(f"{prefix}: Original invoice line not found on this invoice.")
                continue

            return_qty = row.get("return_qty")
            try:
                return_qty = float(return_qty)
                if return_qty <= 0:
                    result.add(f"{prefix}: Return Qty must be greater than zero.")
                    continue
            except (TypeError, ValueError):
                result.add(f"{prefix}: Return Qty must be a valid number.")
                continue

            already_returned = self._returned_qty_fn(invoice_item_id)
            original_qty = float(original.get("qty", 0))
            remaining = original_qty - already_returned

            if return_qty > remaining:
                result.add(
                    f"{prefix}: Return Qty ({return_qty}) exceeds remaining returnable "
                    f"quantity ({remaining}) for this line -- already returned {already_returned} "
                    f"of {original_qty}."
                )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Sale Return.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result