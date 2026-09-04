"""
utils/manufacturer_form_helpers.py

Pure data-marshalling helpers used by screens/manufacturer_list_screen.py
and screens/manufacturer_form_screen.py. No Qt import, no SQL, no business
rules -- matches the pattern in utils/supplier_form_helpers.py so this logic
stays unit-testable and isn't duplicated between the two screens.
"""

from __future__ import annotations

from typing import Any, Optional


def build_manufacturer_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """
    Converts raw widget values (as read straight off the Manufacturer Form's
    controls) into the payload shape ManufacturerEngine.create_manufacturer /
    update_manufacturer expect.

    Expected keys in `form_values`: manufacturer_code, manufacturer_name,
    country, status (already the combo box's selected text).
    """
    margin_text = (form_values.get("default_margin_percent_text") or "").strip()
    return {
        "manufacturer_code": (form_values.get("manufacturer_code") or "").strip(),
        "manufacturer_name": (form_values.get("manufacturer_name") or "").strip(),
        "country": (form_values.get("country") or "").strip(),
        "default_margin_percent": float(margin_text) if margin_text else None,
        "status": form_values.get("status") or "Active",
    }


def dto_to_table_row(dto: Any) -> list[str]:
    """
    Formats a ManufacturerDTO into display strings for one QTableWidget row,
    in the exact column order defined in ui/manufacturer_list.ui:
    Code, Manufacturer Name, Country, Status.
    """
    return [
        dto.manufacturer_code or "",
        dto.manufacturer_name or "",
        dto.country or "",
        "Deleted" if dto.is_deleted else (dto.status or ""),
    ]


def status_filter_value(combo_text: Optional[str]) -> Optional[str]:
    """Maps the Status Filter combo's displayed text to the Engine's
    `status` search parameter ('All' -> None, meaning "don't filter")."""
    text = (combo_text or "").strip()
    if text in ("", "All"):
        return None
    return text
