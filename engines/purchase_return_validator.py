"""
engines/purchase_return_validator.py

Purchase Return Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- mirrors engines/sale_return_validator.py's
shape, adapted for the independent paid-qty / free-qty cumulative checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
VALID_SETTLEMENT_MODES = ("Adjust Against Payable", "Supplier Advance", "Cash Refund")
VALID_RETURN_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class PurchaseReturnValidator:
    """
    Stateless validation rules for Purchase Return header + lines. Does
    NOT compute anything (no proportional discount/cc math, no stock
    posting) -- that lives in PurchaseReturnEngine, same separation used
    between PurchaseValidator and PurchaseEngine.
    """

    def __init__(
        self,
        return_number_exists_fn: Callable[[str, Optional[int]], bool],
        returned_qty_fn: Callable[[int], dict[str, float]],
    ) -> None:
        self._return_number_exists_fn = return_number_exists_fn
        # returned_qty_fn(purchase_invoice_item_id) ->
        # {"returned_qty": ..., "returned_free_qty": ...}, injected so the
        # Validator never touches the Model directly.
        self._returned_qty_fn = returned_qty_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("purchase_invoice_id"):
            result.add("Original Purchase Invoice is mandatory.")

        if not data.get("supplier_id"):
            result.add("Supplier is mandatory.")

        if not data.get("return_date_bs"):
            result.add("Return Date (BS) is mandatory.")

        return_reason = (data.get("return_reason") or "").strip()
        if not return_reason:
            result.add("Return Reason is mandatory.")
        elif len(return_reason) > MAX_LEN_REASON:
            result.add(f"Return Reason must not exceed {MAX_LEN_REASON} characters.")

        settlement_mode = data.get("settlement_mode", "Adjust Against Payable")
        if settlement_mode not in VALID_SETTLEMENT_MODES:
            result.add(f"Settlement Mode must be one of {VALID_SETTLEMENT_MODES}.")

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
        Validates the whole return-line list against the original
        invoice's lines. `invoice_item_lookup` maps
        purchase_invoice_item_id -> that line's original row (from
        PurchaseInvoiceModel.get_returnable_items()), so this method
        never queries the database itself.

        Called by the Engine BEFORE any proportional discount/cc
        computation runs -- a structurally bad or over-quantity line
        list is rejected early, never partially computed or posted.

        Paid qty and free qty are checked INDEPENDENTLY -- a line can be
        fully returned on one side while still having remaining
        returnable quantity on the other.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("At least one return line is required.")
            return result

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"
            invoice_item_id = row.get("purchase_invoice_item_id")

            if not invoice_item_id:
                result.add(f"{prefix}: Original invoice line reference is required.")
                continue

            original = invoice_item_lookup.get(invoice_item_id)
            if original is None:
                result.add(f"{prefix}: Original invoice line not found on this invoice.")
                continue

            try:
                return_qty = float(row.get("return_qty") or 0)
                return_free_qty = float(row.get("return_free_qty") or 0)
            except (TypeError, ValueError):
                result.add(f"{prefix}: Return Qty and Return Free Qty must be valid numbers.")
                continue

            if return_qty < 0 or return_free_qty < 0:
                result.add(f"{prefix}: Return Qty and Return Free Qty cannot be negative.")
                continue

            if return_qty == 0 and return_free_qty == 0:
                result.add(f"{prefix}: Enter a Return Qty and/or a Return Free Qty greater than zero.")
                continue

            already = self._returned_qty_fn(invoice_item_id)
            original_qty = float(original.get("qty", 0))
            original_free_qty = float(original.get("free_qty", 0))
            remaining_qty = original_qty - already["returned_qty"]
            remaining_free_qty = original_free_qty - already["returned_free_qty"]

            if return_qty > remaining_qty:
                result.add(
                    f"{prefix}: Return Qty ({return_qty}) exceeds remaining returnable paid "
                    f"quantity ({remaining_qty}) -- already returned {already['returned_qty']} "
                    f"of {original_qty}."
                )
            if return_free_qty > remaining_free_qty:
                result.add(
                    f"{prefix}: Return Free Qty ({return_free_qty}) exceeds remaining returnable "
                    f"free quantity ({remaining_free_qty}) -- already returned "
                    f"{already['returned_free_qty']} of {original_free_qty}."
                )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Purchase Return.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result