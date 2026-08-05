"""
utils/supplier_manufacturer_discount_form_helpers.py

Pure data-marshalling helpers used by
screens/supplier_manufacturer_discount_list_screen.py and
screens/supplier_manufacturer_discount_form_screen.py. No Qt import, no
SQL, no business rules -- matches the pattern in
utils/manufacturer_form_helpers.py so this logic stays unit-testable and
isn't duplicated between the two screens.
"""

from __future__ import annotations

from typing import Any, Optional


def parse_decimal(text: Optional[str], field_label: str) -> float:
    """Parses a form text field into a float. Blank -> 0.0. Raises ValueError
    with a user-facing message (never a raw Python exception) on bad input."""
    cleaned = (text or "").strip().replace(",", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"{field_label} must be a valid number.") from None


def combo_id_value(current_data: Any) -> Optional[int]:
    """QComboBox.currentData() is None for an unselected/blank row; this
    normalizes that into a clean Optional[int] for payload building."""
    if current_data in (None, "", 0) and current_data != 0:
        return None
    try:
        return int(current_data)
    except (TypeError, ValueError):
        return None


def build_discount_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """
    Converts raw widget values (as read straight off the Discount Form's
    controls) into the payload shape SupplierManufacturerDiscountEngine.
    create_discount / update_discount expect.

    Expected keys in `form_values`:
        supplier_id, manufacturer_id (already combo box currentData()),
        discount_percent_text, remarks

    Raises ValueError (safe to show the user directly) on bad numeric
    input -- range/uniqueness/mandatory checks are the Engine's job, not
    this function's.
    """
    return {
        "supplier_id": combo_id_value(form_values.get("supplier_id")),
        "manufacturer_id": combo_id_value(form_values.get("manufacturer_id")),
        "discount_percent": parse_decimal(form_values.get("discount_percent_text"), "Discount %"),
        "remarks": (form_values.get("remarks") or "").strip(),
    }


def format_percent(value: Any) -> str:
    """Formats a numeric percentage for table/label display, e.g. 12.5 -> '12.50%'."""
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "0.00%"


def dto_to_table_row(dto: Any) -> list[str]:
    """
    Formats a SupplierManufacturerDiscountDTO into display strings for one
    QTableWidget row, in the exact column order defined in
    ui/supplier_manufacturer_discount_list.ui:
    Supplier Name, Manufacturer Name, Discount %, Status.
    """
    return [
        dto.supplier_name or "",
        dto.manufacturer_name or "",
        format_percent(dto.discount_percent),
        "Deleted" if dto.is_deleted else "Active",
    ]


__all__ = [
    "parse_decimal",
    "combo_id_value",
    "build_discount_payload",
    "format_percent",
    "dto_to_table_row",
]
