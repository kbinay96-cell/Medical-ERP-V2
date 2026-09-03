"""
engines/payment_validator.py

Payment Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Mirrors
engines/receipt_validator.py's shape exactly, applied to the supplier side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
MAX_LEN_REMARKS = 1000
VALID_PAYMENT_MODES = ("Cash", "Bank Transfer", "Cheque", "Card", "Other")
VALID_PAYMENT_STATUSES = ("Draft", "Posted", "Cancelled")
MODES_REQUIRING_REFERENCE = ("Bank Transfer", "Cheque", "Card")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class PaymentValidator:
    """Stateless validation rules for Payment header + allocations."""

    def __init__(self, payment_number_exists_fn: Callable[[str, Optional[int]], bool]) -> None:
        self._payment_number_exists_fn = payment_number_exists_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("supplier_id"):
            result.add("Supplier is mandatory.")

        if not data.get("payment_date_bs"):
            result.add("Payment Date (BS) is mandatory.")

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
        if status not in VALID_PAYMENT_STATUSES:
            result.add("Status must be one of Draft, Posted, Cancelled.")

        return result

    def validate_payment_number_unique(self, payment_number: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        number = (payment_number or "").strip()
        if not number:
            result.add("Payment Number is required.")
        elif self._payment_number_exists_fn(number, exclude_id):
            result.add(f"Payment Number '{number}' already exists.")
        return result

    def validate_allocations(self, allocation_rows: list[dict], amount: float,
                              outstanding_lookup: dict[int, float]) -> ValidationResult:
        """
        Validates a proposed allocation set against the payment's total
        `amount` and each invoice's `outstanding_lookup[purchase_invoice_id]`
        (already adjusted by the Engine to exclude this payment's OWN
        prior allocation during an edit).
        """
        result = ValidationResult()

        if allocation_rows is None:
            result.add("Allocation list cannot be None (pass an empty list for a pure-advance payment).")
            return result

        total_allocated = 0.0
        for index, row in enumerate(allocation_rows, start=1):
            prefix = f"Allocation {index}"
            invoice_id = row.get("purchase_invoice_id")
            if not invoice_id:
                result.add(f"{prefix}: Purchase Invoice reference is required.")
                continue
            if invoice_id not in outstanding_lookup:
                result.add(f"{prefix}: Invoice not found or not open for this supplier.")
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
                f"Total allocated ({round(total_allocated, 2)}) cannot exceed the payment amount ({amount})."
            )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Payment.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result