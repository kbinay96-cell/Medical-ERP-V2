# engines/sale_validator.py
from __future__ import annotations

from typing import Any


class SaleValidator:
    """Pure validation for a Sales Invoice payload. No DB, no UI."""

    VALID_PAYMENT_MODES = ("Cash", "Credit", "Partial")

    @staticmethod
    def validate_invoice_header(data: dict[str, Any]) -> tuple[bool, str]:
        if not data.get("customer_id"):
            return False, "Customer is required."

        is_valid_date, date_error = SaleValidator._validate_bs_date(
            data.get("invoice_date_bs"), field_label="Invoice date"
        )
        if not is_valid_date:
            return False, date_error

        payment_mode = (data.get("payment_mode") or "Cash").strip()
        if payment_mode not in SaleValidator.VALID_PAYMENT_MODES:
            return False, "Payment mode must be Cash, Credit, or Partial."

        lines = data.get("lines") or []
        if not lines:
            return False, "At least one line item is required."

        paid_amount = SaleValidator._to_float(data.get("paid_amount"), default=0.0)
        if paid_amount < 0:
            return False, "Paid amount cannot be negative."

        if payment_mode == "Cash" and paid_amount < 0:
            return False, "Paid amount cannot be negative."

        return True, ""

    @staticmethod
    def validate_invoice_line(line: dict[str, Any]) -> tuple[bool, str]:
        if not line.get("item_id"):
            return False, "Item is required on every line."

        if not line.get("item_batch_id"):
            return False, "Batch is required on every line."

        qty = SaleValidator._to_float(line.get("qty"), default=0.0)
        free_qty = SaleValidator._to_float(line.get("free_qty"), default=0.0)
        if qty <= 0 and free_qty <= 0:
            return False, "Either quantity or free quantity must be greater than zero."

        rate = SaleValidator._to_float(line.get("rate"), default=None)
        if rate is None or rate < 0:
            return False, "Sale rate must be zero or a positive number."

        discount_percent = SaleValidator._to_float(line.get("discount_percent"), default=0.0)
        if discount_percent < 0 or discount_percent > 100:
            return False, "Discount percent must be between 0 and 100."

        return True, ""

    @staticmethod
    def _validate_bs_date(value: Any, field_label: str = "Date") -> tuple[bool, str]:
        if not value or not str(value).strip():
            return False, f"{field_label} is required."
        text = str(value).strip()
        parts = text.split("-")
        if len(parts) != 3:
            return False, f"{field_label} must be YYYY-MM-DD (BS)."
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return False, f"{field_label} must be YYYY-MM-DD (BS)."
        if month < 1 or month > 12 or day < 1 or day > 32:
            return False, f"{field_label} is not a valid BS date."
        try:
            from engines.date_engine import validate_bs_date
            ok, message = validate_bs_date(text)
            if not ok:
                return False, message or f"{field_label} is not a valid BS date."
        except Exception:
            pass
        if year < 2000:
            return False, f"{field_label} year looks invalid."
        return True, ""

    @staticmethod
    def _to_float(value: Any, default=0.0):
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
