"""
utils/country_tax_form_helpers.py

Pure data-marshalling helpers used by screens/country_tax_list_screen.py and
screens/country_tax_form_screen.py. No Qt import, no SQL, no business rules
-- matches the pattern in utils/manufacturer_form_helpers.py so this logic
stays unit-testable and isn't duplicated between the two screens.
"""

from __future__ import annotations

from typing import Any, Optional


def parse_percent(text: Optional[str], field_label: str) -> float:
    """Parses a form text field into a float percent. Blank -> 0.0."""
    cleaned = (text or "").strip().replace("%", "").replace(",", "")
    if cleaned == "":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"{field_label} must be a valid number.") from None


def build_country_tax_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """
    Converts raw widget values (as read straight off the Country Tax Form's
    controls) into the payload shape CountryTaxEngine.create_country_tax /
    update_country_tax expect.

    Expected keys in `form_values`: country, vat_percent_text,
    custom_percent_text, remarks, status (already the combo box's
    selected text).
    """
    return {
        "country": (form_values.get("country") or "").strip(),
        "vat_percent": parse_percent(form_values.get("vat_percent_text"), "VAT %"),
        "custom_percent": parse_percent(form_values.get("custom_percent_text"), "Custom %"),
        "remarks": (form_values.get("remarks") or "").strip(),
        "status": form_values.get("status") or "Active",
    }


def dto_to_table_row(dto: Any) -> list[str]:
    """
    Formats a CountryTaxDTO into display strings for one QTableWidget row,
    in the exact column order defined in ui/country_tax_list.ui:
    Country, VAT %, Custom %, Status.
    """
    return [
        dto.country or "",
        f"{float(dto.vat_percent or 0):.2f}",
        f"{float(dto.custom_percent or 0):.2f}",
        "Deleted" if dto.is_deleted else (dto.status or ""),
    ]


def status_filter_value(combo_text: Optional[str]) -> Optional[str]:
    """Maps the Status Filter combo's displayed text to the Engine's
    `status` search parameter ('All' -> None, meaning "don't filter")."""
    text = (combo_text or "").strip()
    if text in ("", "All"):
        return None
    return text
