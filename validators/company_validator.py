"""
=========================================================
Medical ERP V2
Company Validator
---------------------------------------------------------
Pure input validation only. No SQL. No business decisions
(e.g. duplicate-name checks against the DB belong to the
Engine, since that requires a model lookup).
=========================================================
"""

import re
from typing import Dict, Any, List

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{6,20}$")


def validate_company_data(data: Dict[str, Any]) -> List[str]:
    """
    Returns a list of human-readable error messages.
    Empty list means the data is valid.
    """
    errors: List[str] = []

    companyname = (data.get("companyname") or "").strip()
    if not companyname:
        errors.append("Company Name is required.")
    elif len(companyname) < 2:
        errors.append("Company Name must be at least 2 characters.")
    elif len(companyname) > 150:
        errors.append("Company Name must not exceed 150 characters.")

    email = (data.get("email") or "").strip()
    if email and not EMAIL_PATTERN.match(email):
        errors.append("Email format is invalid.")

    phone = (data.get("phone") or "").strip()
    if phone and not PHONE_PATTERN.match(phone):
        errors.append("Phone number format is invalid.")

    mobileno = (data.get("mobileno") or "").strip()
    if mobileno and not PHONE_PATTERN.match(mobileno):
        errors.append("Mobile number format is invalid.")

    for field, label, maxlen in [
        ("address", "Address", 255),
        ("panno", "PAN/VAT Number", 50),
        ("registrationno", "Registration Number", 50),
        ("contactperson", "Contact Person", 100),
        ("remarks", "Remarks", 500),
    ]:
        value = (data.get(field) or "")
        if len(value) > maxlen:
            errors.append(f"{label} must not exceed {maxlen} characters.")

    return errors
