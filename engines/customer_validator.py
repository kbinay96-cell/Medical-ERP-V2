"""
=========================================================
Medical ERP V2
Customer Validator
---------------------------------------------------------
Purpose:
    Validates a proposed Customer record BEFORE it is saved
    (create or update). Pure logic - no DB, no UI. Uniqueness
    (name/code) is NOT checked here because that requires a
    database round-trip; the Customer Engine checks that via
    customer_model before calling this validator's checks.
=========================================================
"""

import re

VALID_BALANCE_TYPES = ("Dr", "Cr")
VALID_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Loose on purpose: accepts optional leading + and 7-15 digits,
# so it doesn't reject legitimate international numbers.
_MOBILE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_customer(data: dict) -> tuple[bool, str]:
    """
    Validates the full set of fields for a Customer record.
    `data` uses the same keys as models.customer_model's
    create_customer()/update_customer() functions.

    Returns (is_valid, error_message). error_message is empty
    when is_valid is True. Checks stop at the first failure,
    same pattern as settings_validator.validate_setting_value.
    """
    ok, msg = _validate_customer_name(data.get("customer_name"))
    if not ok:
        return ok, msg

    ok, msg = _validate_mobile(data.get("mobile"))
    if not ok:
        return ok, msg

    ok, msg = _validate_mobile(data.get("alternate_mobile"), field_label="Alternate mobile")
    if not ok:
        return ok, msg

    ok, msg = _validate_email(data.get("email"))
    if not ok:
        return ok, msg

    ok, msg = _validate_non_negative(data.get("credit_limit", 0), "Credit limit")
    if not ok:
        return ok, msg

    ok, msg = _validate_non_negative_int(data.get("credit_days", 0), "Credit days")
    if not ok:
        return ok, msg

    ok, msg = _validate_non_negative(data.get("opening_balance", 0), "Opening balance")
    if not ok:
        return ok, msg

    ok, msg = _validate_balance_type(data.get("balance_type", "Dr"))
    if not ok:
        return ok, msg

    ok, msg = _validate_photo_path(data.get("photo_path"))
    if not ok:
        return ok, msg

    return True, ""


def _validate_customer_name(name) -> tuple[bool, str]:
    if not name or not str(name).strip():
        return False, "Customer Name is required."
    return True, ""


def _validate_mobile(value, field_label: str = "Mobile") -> tuple[bool, str]:
    if value is None or str(value).strip() == "":
        return True, ""  # optional

    if not _MOBILE_PATTERN.match(str(value).strip()):
        return False, f"{field_label} must contain 7-15 digits only (an optional leading + is allowed)."
    return True, ""


def _validate_email(value) -> tuple[bool, str]:
    if value is None or str(value).strip() == "":
        return True, ""  # optional

    if not _EMAIL_PATTERN.match(str(value).strip()):
        return False, "Email is not a valid email address."
    return True, ""


def _validate_non_negative(value, field_label: str) -> tuple[bool, str]:
    try:
        amount = float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return False, f"{field_label} must be a number."

    if amount < 0:
        return False, f"{field_label} cannot be negative."
    return True, ""


def _validate_non_negative_int(value, field_label: str) -> tuple[bool, str]:
    try:
        amount = int(value) if value not in (None, "") else 0
    except (TypeError, ValueError):
        return False, f"{field_label} must be a whole number."

    if amount < 0:
        return False, f"{field_label} cannot be negative."
    return True, ""


def _validate_balance_type(value) -> tuple[bool, str]:
    if str(value).strip() not in VALID_BALANCE_TYPES:
        return False, "Balance Type must be Dr or Cr."
    return True, ""


def _validate_photo_path(value) -> tuple[bool, str]:
    if value is None or str(value).strip() == "":
        return True, ""  # optional

    lowered = str(value).strip().lower()
    if not lowered.endswith(VALID_PHOTO_EXTENSIONS):
        return False, "Customer photo must be one of: jpg, jpeg, png, webp."
    return True, ""
