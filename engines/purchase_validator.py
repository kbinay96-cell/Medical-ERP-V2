# engines/purchase_validator.py
from __future__ import annotations

from typing import Any


class PurchaseValidator:
    """Validates a Purchase Invoice payload BEFORE it reaches the Engine's
    save logic. Pure logic — no DB, no UI. Uniqueness (supplier+billno) is
    NOT checked here (needs a DB round-trip) — the Engine checks that via
    PurchaseInvoiceModel.exists_by_supplier_and_billno()."""

    # --- header ---------------------------------------------------------

    @staticmethod
    def validate_invoice_header(data: dict[str, Any]) -> tuple[bool, str]:
        """Checks: supplier_id present, invoice_number non-empty,
        invoice_date_bs valid format, at least one line item present.
        Returns (is_valid, error_message)."""
        if not data.get("supplier_id"):
            return False, "Supplier is required."

        invoice_number = data.get("invoice_number")
        if not invoice_number or not str(invoice_number).strip():
            return False, "Invoice number is required."

        is_valid_date, date_error = PurchaseValidator._validate_bs_date(
            data.get("invoice_date_bs"), field_label="Invoice date"
        )
        if not is_valid_date:
            return False, date_error

        lines = data.get("lines") or []
        if not lines:
            return False, "At least one line item is required."

        return True, ""

    # --- lines ------------------------------------------------------------

    @staticmethod
    def validate_invoice_line(line: dict[str, Any]) -> tuple[bool, str]:
        """Checks per line: item_id present, qty > 0 OR free_qty > 0
        (both cannot be zero), purchase_rate >= 0, discount_percent in
        [0,100], expiry_month in [1,12], expiry_year plausible (>= current
        BS year), mrp >= 0, batch_no non-empty."""
        if not line.get("item_id"):
            return False, "Item is required on every line."

        qty = PurchaseValidator._to_float(line.get("qty"), default=0.0)
        free_qty = PurchaseValidator._to_float(line.get("free_qty"), default=0.0)
        if qty <= 0 and free_qty <= 0:
            return False, "Either quantity or free quantity must be greater than zero."

        purchase_rate = PurchaseValidator._to_float(line.get("purchase_rate"), default=None)
        if purchase_rate is None or purchase_rate < 0:
            return False, "Purchase rate must be zero or a positive number."

        discount_percent = PurchaseValidator._to_float(line.get("discount_percent"), default=0.0)
        if discount_percent < 0 or discount_percent > 100:
            return False, "Discount percent must be between 0 and 100."

        expiry_month = line.get("expiry_month")
        try:
            expiry_month = int(expiry_month)
        except (TypeError, ValueError):
            return False, "Expiry month is required."
        if expiry_month < 1 or expiry_month > 12:
            return False, "Expiry month must be between 1 and 12."

        expiry_year = line.get("expiry_year")
        try:
            expiry_year = int(expiry_year)
        except (TypeError, ValueError):
            return False, "Expiry year is required."

        current_bs_year = PurchaseValidator._current_bs_year()
        if current_bs_year is not None and expiry_year < current_bs_year:
            return False, "Expiry year cannot be in the past."

        mrp = PurchaseValidator._to_float(line.get("mrp"), default=None)
        if mrp is None or mrp < 0:
            return False, "MRP must be zero or a positive number."

        batch_no = line.get("batch_no")
        if not batch_no or not str(batch_no).strip():
            return False, "Batch number is required."

        return True, ""

    @staticmethod
    def validate_free_qty_rate(line: dict[str, Any]) -> tuple[bool, str]:
        """Business rule (glossary): free_qty lines MUST have purchase_rate
        contribution of 0 for that portion — this checks the payload isn't
        trying to price free units."""
        free_qty = PurchaseValidator._to_float(line.get("free_qty"), default=0.0)
        if free_qty <= 0:
            return True, ""

        # free_qty_rate is the (optional) explicit rate the payload may carry
        # for the free-quantity portion of the line. It must be exactly 0 if
        # present at all — free units are never priced.
        free_qty_rate = line.get("free_qty_rate")
        if free_qty_rate is not None:
            free_qty_rate_value = PurchaseValidator._to_float(free_qty_rate, default=None)
            if free_qty_rate_value is None or free_qty_rate_value != 0:
                return False, "Free quantity cannot carry a purchase rate — it must be priced at zero."

        return True, ""

    # --- internal helpers -------------------------------------------------

    @staticmethod
    def _validate_bs_date(value: Any, field_label: str = "Date") -> tuple[bool, str]:
        """Validates a BS date string is present and shaped like YYYY-MM-DD
        with a real calendar month/day-of-month range. Delegates the actual
        BS calendar bounds (days-in-month per BS year) to engines.date_engine
        when available; falls back to a loose shape check if that engine
        can't be imported (e.g. when this validator is unit-tested in
        isolation), since this stays pure logic with no hard DB dependency."""
        if not value or not str(value).strip():
            return False, f"{field_label} is required."

        value = str(value).strip()
        parts = value.split("-")
        if len(parts) != 3:
            return False, f"{field_label} must be in YYYY-MM-DD (BS) format."

        year_str, month_str, day_str = parts
        try:
            year, month, day = int(year_str), int(month_str), int(day_str)
        except ValueError:
            return False, f"{field_label} must be in YYYY-MM-DD (BS) format."

        if month < 1 or month > 12:
            return False, f"{field_label} has an invalid month."
        if day < 1 or day > 32:
            # 32 is the widest possible BS month length; exact bounds are
            # enforced by engines.date_engine when available (see below).
            return False, f"{field_label} has an invalid day."

        try:
            from engines.date_engine import is_valid_bs_date  # lazy import

            if not is_valid_bs_date(year, month, day):
                return False, f"{field_label} is not a valid BS calendar date."
        except ImportError:
            pass

        return True, ""

    @staticmethod
    def _current_bs_year() -> int | None:
        """Best-effort current BS year via engines.date_engine (lazy import,
        same defensive pattern used across the project's other engines).
        Returns None if unavailable, in which case the caller skips the
        'not in the past' check rather than guessing."""
        try:
            from engines.date_engine import ad_to_bs
            from datetime import date

            today_bs = ad_to_bs(date.today())
            # ad_to_bs is expected to return either a (year, month, day)
            # tuple or an object exposing a .year attribute.
            if isinstance(today_bs, tuple):
                return today_bs[0]
            return getattr(today_bs, "year", None)
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any, default: float | None) -> float | None:
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


class PurchaseOrderValidator:
    """Validates a Purchase Order payload — pure logic, no DB."""

    @staticmethod
    def validate_order_header(data: dict[str, Any]) -> tuple[bool, str]:
        """Checks: supplier_id present, order_date_bs valid, at least one
        line item present (manual or auto-suggested)."""
        if not data.get("supplier_id"):
            return False, "Supplier is required."

        is_valid_date, date_error = PurchaseValidator._validate_bs_date(
            data.get("order_date_bs"), field_label="Order date"
        )
        if not is_valid_date:
            return False, date_error

        lines = data.get("lines") or []
        if not lines:
            return False, "At least one line item is required."

        return True, ""

    @staticmethod
    def validate_order_line(line: dict[str, Any]) -> tuple[bool, str]:
        """Checks: item_id present, ordered_qty > 0. rate is optional
        (estimate only, not enforced)."""
        if not line.get("item_id"):
            return False, "Item is required on every line."

        ordered_qty = PurchaseValidator._to_float(line.get("ordered_qty"), default=0.0)
        if ordered_qty is None or ordered_qty <= 0:
            return False, "Ordered quantity must be greater than zero."

        return True, ""