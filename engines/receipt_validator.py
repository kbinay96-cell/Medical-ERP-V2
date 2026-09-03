"""
engines/receipt_validator.py

Receipt Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only. No FIFO decisions, no advance computation --
that's the Engine's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
MAX_LEN_REMARKS = 1000
VALID_PAYMENT_MODES = ("Cash", "Bank Transfer", "Cheque", "Card", "Other")
VALID_RECEIPT_STATUSES = ("Draft", "Posted", "Cancelled")
MODES_REQUIRING_REFERENCE = ("Bank Transfer", "Cheque", "Card")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class ReceiptValidator:
    """Stateless validation rules for Receipt header + allocations."""

    def __init__(self, receipt_number_exists_fn: Callable[[str, Optional[int]], bool]) -> None:
        self._receipt_number_exists_fn = receipt_number_exists_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("customer_id"):
            result.add("Customer is mandatory.")

        if not data.get("receipt_date_bs"):
            result.add("Receipt Date (BS) is mandatory.")

        payment_mode = data.get("payment_mode")
        if payment_mode not in VALID_PAYMENT_MODES:
            result.add(f"Payment Mode must be one of {VALID_PAYMENT_MODES}.")
        elif payment_mode in MODES_REQUIRING_REFERENCE and not (data.get("reference_no") or "").strip():
            result.add(f"Reference No. is required for payment mode '{payment_mode}'.")

        try:
            amount = float(data.get("amount"))
            if amount <= 0:
                result.add("Amount must be greater than zero.")
        except (TypeError, ValueError):
            result.add("Amount must be a valid number.")

        remarks = data.get("remarks")
        if remarks and len(remarks) > MAX_LEN_REMARKS:
            result.add(f"Remarks must not exceed {MAX_LEN_REMARKS} characters.")

        status = data.get("status", "Posted")
        if status not in VALID_RECEIPT_STATUSES:
            result.add("Status must be one of Draft, Posted, Cancelled.")

        return result

    def validate_receipt_number_unique(self, receipt_number: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        number = (receipt_number or "").strip()
        if not number:
            result.add("Receipt Number is required.")
        elif self._receipt_number_exists_fn(number, exclude_id):
            result.add(f"Receipt Number '{number}' already exists.")
        return result

    def validate_allocations(self, allocation_rows: list[dict], amount: float,
                              outstanding_lookup: dict[int, float]) -> ValidationResult:
        """
        Validates a proposed allocation set against the receipt's total
        `amount` and each invoice's `outstanding_lookup[sale_invoice_id]`
        (an amount already adjusted by the Engine to exclude this
        receipt's OWN prior allocation, so editing an existing receipt
        doesn't double-count itself as "already paid").

        Allocations are optional (a receipt can be pure advance with
        zero allocations) -- this method does NOT require at least one
        allocation row, unlike Sale/Purchase Return's line requirement.
        """
        result = ValidationResult()

        if allocation_rows is None:
            result.add("Allocation list cannot be None (pass an empty list for a pure-advance receipt).")
            return result

        total_allocated = 0.0
        for index, row in enumerate(allocation_rows, start=1):
            prefix = f"Allocation {index}"
            invoice_id = row.get("sale_invoice_id")
            if not invoice_id:
                result.add(f"{prefix}: Sale Invoice reference is required.")
                continue
            if invoice_id not in outstanding_lookup:
                result.add(f"{prefix}: Invoice not found or not open for this customer.")
                continue

            try:
                allocated_amount = float(row.get("allocated_amount"))
                if allocated_amount <= 0:
                    result.add(f"{prefix}: Allocated amount must be greater than zero.")
                    continue
            except (TypeError, ValueError):
                result.add(f"{prefix}: Allocated amount must be a valid number.")
                continue

            outstanding = outstanding_lookup[invoice_id]
            if allocated_amount > outstanding:
                result.add(
                    f"{prefix}: Allocated amount ({allocated_amount}) exceeds this invoice's "
                    f"outstanding balance ({outstanding})."
                )
            total_allocated += allocated_amount

        if total_allocated > amount:
            result.add(
                f"Total allocated ({round(total_allocated, 2)}) cannot exceed the receipt amount ({amount})."
            )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Receipt.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result