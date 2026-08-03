"""
utils/item_form_helpers.py

Pure data-marshalling helpers used by screens/item_list_screen.py and
screens/item_form_screen.py. No SQL, no business rules -- mirrors
utils/supplier_form_helpers.py's shape and reasoning exactly.
"""

from __future__ import annotations

from typing import Any, Optional


def parse_decimal(text: Optional[str], field_label: str) -> float:
    cleaned = (text or "").strip().replace(",", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"{field_label} must be a valid number.") from None


def parse_int(text: Optional[str], field_label: str) -> int:
    cleaned = (text or "").strip().replace(",", "")
    if cleaned == "":
        return 0
    try:
        return int(cleaned)
    except ValueError:
        raise ValueError(f"{field_label} must be a whole number.") from None


def combo_id_value(current_data: Any) -> Optional[int]:
    """QComboBox.currentData() is None for an unselected/blank row; this
    just normalizes that into a clean Optional[int] for payload building."""
    if current_data in (None, "", 0) and current_data != 0:
        return None
    try:
        return int(current_data)
    except (TypeError, ValueError):
        return None


def build_item_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """
    Converts raw widget values (as read straight off the Item Form's
    controls) into the payload shape ItemEngine.create_item /
    update_item expect. Raises ValueError (safe to show the user
    directly) on bad numeric input -- range/uniqueness/mandatory checks
    are the Engine's job, not this function's.
    """
    return {
        "item_code": (form_values.get("item_code") or "").strip(),
        "item_name": (form_values.get("item_name") or "").strip(),
        "category_id": combo_id_value(form_values.get("category_id")),
        "sub_category_id": combo_id_value(form_values.get("sub_category_id")),
        "item_group_id": combo_id_value(form_values.get("item_group_id")),
        "manufacturer_id": combo_id_value(form_values.get("manufacturer_id")),
        "generic_id": combo_id_value(form_values.get("generic_id")),
        "unit_id": combo_id_value(form_values.get("unit_id")),
        "purchase_unit_id": combo_id_value(form_values.get("purchase_unit_id")),
        "purchase_rate": parse_decimal(form_values.get("purchase_rate_text"), "Purchase Rate"),
        "sale_rate": parse_decimal(form_values.get("sale_rate_text"), "Sale Rate"),
        "mrp": parse_decimal(form_values.get("mrp_text"), "MRP"),
        "minimum_stock": parse_decimal(form_values.get("minimum_stock_text"), "Minimum Stock"),
        "tax_mode": form_values.get("tax_mode") or "country_default",
        "item_vat_checked": bool(form_values.get("item_vat_checked")),
        "item_vat_percent": (
            parse_decimal(form_values.get("item_vat_percent_text"), "VAT %")
            if form_values.get("item_vat_checked") else None
        ),
        "item_custom_checked": bool(form_values.get("item_custom_checked")),
        "item_custom_percent": (
            parse_decimal(form_values.get("item_custom_percent_text"), "Custom %")
            if form_values.get("item_custom_checked") else None
        ),
        "status": form_values.get("status") or "Active",
        "remarks": (form_values.get("remarks") or "").strip(),
    }


def build_batch_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """Converts raw Opening Batch dialog values into ItemEngine.add_batch()'s
    expected payload shape."""
    return {
        "batch_no": (form_values.get("batch_no") or "").strip(),
        "expiry_year": parse_int(form_values.get("expiry_year_text"), "Expiry Year"),
        "expiry_month": parse_int(form_values.get("expiry_month_text"), "Expiry Month"),
        "batch_qty": parse_decimal(form_values.get("batch_qty_text"), "Batch Quantity"),
        "batch_purchase_rate": parse_decimal(form_values.get("batch_purchase_rate_text"), "Batch Purchase Rate"),
        "remarks": (form_values.get("remarks") or "").strip(),
    }


def format_amount(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def format_qty(value: Any) -> str:
    try:
        return f"{float(value):,.3f}".rstrip("0").rstrip(".") or "0"
    except (TypeError, ValueError):
        return "0"


def dto_to_table_row(dto: Any) -> list[str]:
    """
    Formats an ItemDTO into display strings for one QTableWidget row, in
    the exact column order defined in ui/ui_item_list.py:
    Code, Name, Category, Manufacturer, Unit, Purchase Rate, Sale Rate,
    MRP, Total Stock, Minimum Stock, Status.

    NOTE: category_name / manufacturer_name are NOT on ItemDTO itself
    (ItemDTO only carries the foreign-key ids) -- the Screen resolves
    those display names from its already-loaded lookup dict before
    calling this, and passes them in via the `lookup_names` argument.
    """
    return [
        dto.item_code or "",
        dto.item_name or "",
        format_amount(dto.purchase_rate),
        format_amount(dto.sale_rate),
        format_amount(dto.mrp),
        format_qty(dto.total_stock),
        format_qty(dto.minimum_stock),
        "Deleted" if dto.is_deleted else (dto.status or ""),
    ]


def status_filter_value(combo_text: Optional[str]) -> Optional[str]:
    text = (combo_text or "").strip()
    if text in ("", "All"):
        return None
    return text


def format_expiry_display(expiry_year: Any, expiry_month: Any) -> str:
    """MM/YYYY display -- mirrors the generated column in item_batch."""
    try:
        return f"{int(expiry_month):02d}/{int(expiry_year)}"
    except (TypeError, ValueError):
        return ""


__all__ = [
    "parse_decimal", "parse_int", "combo_id_value",
    "build_item_payload", "build_batch_payload",
    "format_amount", "format_qty", "dto_to_table_row",
    "status_filter_value", "format_expiry_display",
]
