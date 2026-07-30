"""
utils/company_form_helpers.py

Pure helper functions for the Company Master screens - no SQL, no
business rules (those belong to CompanyEngine / company_validator).
Mirrors utils/supplier_form_helpers.py.
"""

from __future__ import annotations

from typing import List


def build_company_payload(raw: dict) -> dict:
    """
    Cleans raw form-field strings into the dict shape
    CompanyEngine.create_company / update_company expect.
    Raises ValueError on structurally bad input (mirrors how
    build_supplier_payload signals bad numeric/text input to
    the Form screen, which catches ValueError).
    """
    company_name = (raw.get("companyname") or "").strip()
    if not company_name:
        raise ValueError("Company Name is required.")

    return {
        "companyname": company_name,
        "address": (raw.get("address") or "").strip(),
        "contactperson": (raw.get("contactperson") or "").strip(),
        "mobileno": (raw.get("mobileno") or "").strip(),
        "phone": (raw.get("phone") or "").strip(),
        "email": (raw.get("email") or "").strip(),
        "panno": (raw.get("panno") or "").strip(),
        "registrationno": (raw.get("registrationno") or "").strip(),
        "remarks": (raw.get("remarks") or "").strip(),
        "status": raw.get("status") or "Active",
    }


def dto_to_table_row(dto) -> List[str]:
    """Column order must match ui/ui_company_list.py's table headers."""
    return [
        dto.company_id or "",
        dto.company_name or "",
        dto.contact_person or "",
        dto.mobile_no or "",
        dto.phone_no or "",
        dto.email or "",
        dto.status or "",
    ]


def status_filter_value(combo_text: str):
    """Maps the list screen's status-filter combo text to the value
    CompanyEngine.search_companies expects ('Active' / 'Inactive' / None for All)."""
    if combo_text == "Active":
        return "Active"
    if combo_text == "Inactive":
        return "Inactive"
    return None
