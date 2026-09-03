# engines/sale_validator.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REMARKS = 1000
VALID_ENTRY_MODES = ("free_qty", "net_rate")
VALID_SALE_MODES = ("Retail", "Wholesale")
VALID_PAYMENT_TYPES = ("Cash", "Bank", "eSewa", "Khalti", "IPS")
VALID_INVOICE_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


# ====================================================================== #
# SALE INVOICE VALIDATOR
# ====================================================================== #
class SaleInvoiceValidator:
    """
    Stateless validation rules for Sale Invoice header + lines. Does NOT
    compute anything (no rate math, no CC, no stock checks) -- it only
    checks that what the Engine is about to save is structurally sound.
    All computation lives in SaleEngine itself, same separation already
    used between PurchaseValidator and PurchaseEngine.
    """

    def __init__(self, number_exists_fn: Callable[[str, Optional[int]], bool]) -> None:
        self._number_exists_fn = number_exists_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("customer_id"):
            result.add("Customer is mandatory.")

        if not data.get("invoice_date_bs"):
            result.add("Invoice Date (BS) is mandatory.")

        sale_mode = data.get("sale_mode", "Retail")
        if sale_mode not in VALID_SALE_MODES:
            result.add("Sale Mode must be either 'Retail' or 'Wholesale'.")

        payment_type = data.get("payment_type")
        if payment_type is not None and payment_type not in VALID_PAYMENT_TYPES:
            result.add(f"Payment Type must be one of {VALID_PAYMENT_TYPES}.")

        status = data.get("status", "Posted")
        if status not in VALID_INVOICE_STATUSES:
            result.add(f"Status must be one of {VALID_INVOICE_STATUSES}.")

        remarks = data.get("remarks")
        if remarks and len(str(remarks).strip()) > MAX_LEN_REMARKS:
            result.add(f"Remarks cannot exceed {MAX_LEN_REMARKS} characters.")

        amount_paid_now = float(data.get("amount_paid_now", 0) or 0)
        if amount_paid_now < 0:
            result.add("Amount paid now cannot be negative.")

        grand_total = float(data.get("grand_total", 0) or 0)
        if grand_total > 0 and amount_paid_now > grand_total:
            result.add("Amount paid now cannot exceed grand total.")

        invoice_number = data.get("invoice_number")
        if invoice_number and self._number_exists_fn(str(invoice_number), data.get("sale_invoice_id")):
            result.add("Invoice Number already exists.")

        return result

    # ------------------------------------------------------------------ #
    def validate_lines(self, raw_lines: list[dict]) -> ValidationResult:
        result = ValidationResult()

        if not raw_lines:
            result.add("At least one line item is required.")
            return result

        for idx, line in enumerate(raw_lines, start=1):
            prefix = f"Line {idx}"

            if not line.get("item_id"):
                result.add(f"{prefix}: Item is mandatory.")

            entry_mode = line.get("entry_mode", "free_qty")
            if entry_mode not in VALID_ENTRY_MODES:
                result.add(f"{prefix}: Entry mode must be one of {VALID_ENTRY_MODES}.")

            qty = float(line.get("qty", 0) or 0)
            free_qty = float(line.get("free_qty", 0) or 0)

            if qty <= 0 and free_qty <= 0:
                result.add(f"{prefix}: Either quantity or free quantity must be greater than zero.")

            rate = float(line.get("rate", 0) or 0)
            if rate < 0:
                result.add(f"{prefix}: Rate cannot be negative.")

            discount_percent = float(line.get("discount_percent", 0) or 0)
            if discount_percent < 0 or discount_percent > 100:
                result.add(f"{prefix}: Discount percent must be between 0 and 100.")

            if entry_mode == "net_rate" and free_qty > 0:
                result.add(f"{prefix}: Free Qty must be 0 in Net Rate mode.")

        return result


# ====================================================================== #
# ITEM FREE SCHEME VALIDATOR
# ====================================================================== #
class ItemFreeSchemeValidator:
    """
    Pure validation rules for the Sale Item Free Scheme master. No DB
    access -- duplicate checks are done via injected callback.
    """

    def __init__(self, scheme_exists_fn: Callable[[int, Optional[int]], bool]) -> None:
        self._scheme_exists_fn = scheme_exists_fn

    # ------------------------------------------------------------------ #
    def validate(self, data: dict, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()

        if not data.get("item_id"):
            result.add("Item is mandatory.")

        scheme_qty = float(data.get("scheme_qty", 0) or 0)
        if scheme_qty <= 0:
            result.add("Scheme qty (Buy Qty) must be greater than zero.")

        scheme_free = float(data.get("scheme_free", 0) or 0)
        if scheme_free <= 0:
            result.add("Scheme free (Free Qty) must be greater than zero.")

        item_id = data.get("item_id")
        if item_id and self._scheme_exists_fn(int(item_id), exclude_id):
            result.add("An active free scheme already exists for this item.")

        remarks = data.get("remarks")
        if remarks and len(str(remarks).strip()) > MAX_LEN_REMARKS:
            result.add(f"Remarks cannot exceed {MAX_LEN_REMARKS} characters.")

        return result

