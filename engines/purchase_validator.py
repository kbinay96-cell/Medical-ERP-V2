# engines/purchase_validator.py
from __future__ import annotations
from typing import Any, Tuple
from datetime import datetime


class PurchaseValidator:
    """Validates Purchase Invoice payloads (pure logic - no DB)."""

    @staticmethod
    def _is_non_empty_str(value: Any) -> bool:
        return isinstance(value, str) and value.strip() != ""

    @staticmethod
    def validate_invoice_header(data: dict[str, Any]) -> Tuple[bool, str]:
        if not data:
            return False, "Invoice payload is empty."
        if not data.get("supplier_id"):
            return False, "supplier_id is required."
        if not PurchaseValidator._is_non_empty_str(data.get("invoice_number")):
            return False, "invoice_number must be a non-empty string."
        if not PurchaseValidator._is_non_empty_str(data.get("invoice_date_bs")):
            return False, "invoice_date_bs must be provided (BS format)."
        lines = data.get("lines") or []
        if not isinstance(lines, list) or len(lines) == 0:
            return False, "At least one invoice line is required."
        return True, ""

    @staticmethod
    def validate_invoice_line(line: dict[str, Any]) -> Tuple[bool, str]:
        if not line:
            return False, "Invoice line is empty."
        if not line.get("item_id"):
            return False, "line.item_id is required."
        qty = line.get("qty", 0) or 0
        free_qty = line.get("free_qty", 0) or 0
        try:
            qty = float(qty)
            free_qty = float(free_qty)
        except Exception:
            return False, "line.qty and line.free_qty must be numeric."
        if qty <= 0 and free_qty <= 0:
            return False, "Either qty or free_qty must be greater than zero."
        purchase_rate = line.get("purchase_rate", 0)
        try:
            purchase_rate = float(purchase_rate)
        except Exception:
            return False, "line.purchase_rate must be numeric."
        if purchase_rate < 0:
            return False, "line.purchase_rate cannot be negative."
        discount_percent = line.get("discount_percent", 0) or 0
        try:
            discount_percent = float(discount_percent)
        except Exception:
            return False, "line.discount_percent must be numeric."
        if discount_percent < 0 or discount_percent > 100:
            return False, "line.discount_percent must be between 0 and 100."

        expiry_month = line.get("expiry_month")
        expiry_year = line.get("expiry_year")
        if expiry_month is None or expiry_year is None:
            return False, "expiry_month and expiry_year are required for invoice lines."
        try:
            em = int(expiry_month)
            ey = int(expiry_year)
        except Exception:
            return False, "expiry_month and expiry_year must be integers."
        if em < 1 or em > 12:
            return False, "expiry_month must be between 1 and 12."
        # Basic plausibility check: expiry_year not in the distant past (BS). Use current AD -> BS mapping is avoided here
        if ey < 2000:
            return False, "expiry_year looks invalid (too small)."

        if not PurchaseValidator._is_non_empty_str(line.get("batch_no")):
            return False, "line.batch_no is required."

        mrp = line.get("mrp", 0)
        try:
            mrp = float(mrp)
        except Exception:
            return False, "line.mrp must be numeric."
        if mrp < 0:
            return False, "line.mrp cannot be negative."

        return True, ""

    @staticmethod
    def validate_free_qty_rate(line: dict[str, Any]) -> Tuple[bool, str]:
        """Ensure that free_qty portion isn't being charged."""
        free_qty = float(line.get("free_qty", 0) or 0)
        if free_qty <= 0:
            return True, ""
        # If free_qty present, the business rule says free portion must not have a price contribution.
        # The payload shouldn't attempt to set per-free-unit price; we enforce purchase_rate applies to paid qty only.
        # We ensure purchase_rate is >= 0, and later calculations treat free_qty as zero-price.
        purchase_rate = float(line.get("purchase_rate", 0) or 0)
        if purchase_rate < 0:
            return False, "purchase_rate cannot be negative."
        # Nothing else to assert here — caller must ensure cc_amount basis uses paid-unit price, not free-unit price.
        return True, ""


class PurchaseOrderValidator:
    """Validates Purchase Order payloads (pure logic)."""

    @staticmethod
    def validate_order_header(data: dict[str, Any]) -> Tuple[bool, str]:
        if not data:
            return False, "Order payload is empty."
        if not data.get("supplier_id"):
            return False, "supplier_id is required for a Purchase Order."
        if not data.get("order_date_bs"):
            return False, "order_date_bs must be provided."
        lines = data.get("lines") or []
        if not isinstance(lines, list) or len(lines) == 0:
            return False, "At least one order line is required."
        return True, ""

    @staticmethod
    def validate_order_line(line: dict[str, Any]) -> Tuple[bool, str]:
        if not line:
            return False, "Order line is empty."
        if not line.get("item_id"):
            return False, "order line.item_id is required."
        try:
            ordered_qty = float(line.get("ordered_qty", 0) or 0)
        except Exception:
            return False, "ordered_qty must be numeric."
        if ordered_qty <= 0:
            return False, "ordered_qty must be greater than zero."
        # rate is optional
        return True, ""