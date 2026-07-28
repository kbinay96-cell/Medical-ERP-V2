"""
utils/supplier_form_helpers.py

Pure data-marshalling helpers used by screens/supplier_list_screen.py and
screens/supplier_form_screen.py.

Project rule check: the Screen/Controller layer must contain "No SQL. No
business logic." Converting raw widget text into typed values (e.g. the
string "1,000" into 1000.0) and converting an Engine DTO into a list of
display strings for a table row is UI data-marshalling, not a business
decision -- every business rule (what counts as valid, what the defaults
are, what's a duplicate) still lives only in engines/supplier_engine.py and
utils/supplier_validator.py. This module exists so that marshalling logic:

    1. Isn't duplicated between the List screen and the Form screen.
    2. Can be unit-tested with zero Qt/PySide6 dependency (see
       tests/test_supplier_module.py), since it never imports PySide6.
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


def parse_int(text: Optional[str], field_label: str) -> int:
    """Parses a form text field into an int. Blank -> 0."""
    cleaned = (text or "").strip().replace(",", "")
    if cleaned == "":
        return 0
    try:
        return int(cleaned)
    except ValueError:
        raise ValueError(f"{field_label} must be a whole number.") from None


def build_supplier_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    """
    Converts raw widget values (as read straight off the Supplier Form's
    controls) into the payload shape SupplierEngine.create_supplier /
    update_supplier expect.

    Expected keys in `form_values` (all raw strings, except balance_type
    and status which are already the combo box's selected text):
        supplier_code, supplier_name, contact_person, mobile_no, phone_no,
        email, address, city, pan_vat_no, opening_balance_text,
        balance_type, credit_limit_text, credit_days_text, status, remarks

    Raises ValueError (with a message safe to show the user directly) if
    a numeric field can't be parsed. This is input marshalling only --
    range/uniqueness/mandatory checks are the Engine's job, not this
    function's.
    """
    return {
        "supplier_code": (form_values.get("supplier_code") or "").strip(),
        "supplier_name": (form_values.get("supplier_name") or "").strip(),
        "contact_person": (form_values.get("contact_person") or "").strip(),
        "mobile_no": (form_values.get("mobile_no") or "").strip(),
        "phone_no": (form_values.get("phone_no") or "").strip(),
        "email": (form_values.get("email") or "").strip(),
        "address": (form_values.get("address") or "").strip(),
        "city": (form_values.get("city") or "").strip(),
        "pan_vat_no": (form_values.get("pan_vat_no") or "").strip(),
        "opening_balance": parse_decimal(form_values.get("opening_balance_text"), "Opening Balance"),
        "balance_type": form_values.get("balance_type") or "Dr",
        "credit_limit": parse_decimal(form_values.get("credit_limit_text"), "Credit Limit"),
        "credit_days": parse_int(form_values.get("credit_days_text"), "Credit Days"),
        "status": form_values.get("status") or "Active",
        "remarks": (form_values.get("remarks") or "").strip(),
    }


def format_amount(value: Any) -> str:
    """Formats a numeric value for table/label display, e.g. 1000 -> '1,000.00'."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def dto_to_table_row(dto: Any) -> list[str]:
    """
    Formats a SupplierDTO into display strings for one QTableWidget row, in
    the exact column order defined in ui/supplier_list.ui:
    Code, Name, Contact Person, Mobile, City, PAN/VAT, Opening Balance,
    Type, Credit Limit, Credit Days, Status.
    """
    return [
        dto.supplier_code or "",
        dto.supplier_name or "",
        dto.contact_person or "",
        dto.mobile_no or "",
        dto.city or "",
        dto.pan_vat_no or "",
        format_amount(dto.opening_balance),
        dto.balance_type or "",
        format_amount(dto.credit_limit),
        str(dto.credit_days if dto.credit_days is not None else 0),
        "Deleted" if dto.is_deleted else (dto.status or ""),
    ]


def status_filter_value(combo_text: Optional[str]) -> Optional[str]:
    """Maps the Status Filter combo's displayed text to the Engine's
    `status` search parameter ('All' -> None, meaning "don't filter")."""
    text = (combo_text or "").strip()
    if text in ("", "All"):
        return None
    return text
