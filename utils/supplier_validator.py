"""
utils/supplier_validator.py

Supplier Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." This module
contains ONLY validation rules -- it never touches the database directly for
anything except the duplicate-check callbacks it is given (which the Engine
supplies, backed by the Model), and it never decides *what to do* about a
failure -- it only reports ValidationResult back to the Engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_SUPPLIER_CODE = 20
MAX_LEN_SUPPLIER_NAME = 150
MAX_LEN_CONTACT_PERSON = 100
MAX_LEN_PHONE = 20
MAX_LEN_EMAIL = 150
MAX_LEN_ADDRESS = 255
MAX_LEN_CITY = 100
MAX_LEN_PAN_VAT = 30

VALID_BALANCE_TYPES = ("Dr", "Cr")
VALID_STATUSES = ("Active", "Inactive")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MOBILE_RE = re.compile(r"^[0-9+\-\s()]{6,20}$")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class SupplierValidator:
    """
    Stateless validation rules for the Supplier Master.

    `name_exists_fn` / `code_exists_fn` are injected by the Engine (which owns
    the Model) so this class never imports the database layer directly --
    keeping validation testable in isolation with plain functions/mocks.
    """

    def __init__(
        self,
        name_exists_fn: Callable[[str, Optional[int]], bool],
        code_exists_fn: Callable[[str, Optional[int]], bool],
    ) -> None:
        self._name_exists_fn = name_exists_fn
        self._code_exists_fn = code_exists_fn

    # ------------------------------------------------------------------ #
    def validate_for_create(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_name_uniqueness(data.get("supplier_name", ""), result, exclude_id=None)
        return result

    def validate_for_update(self, supplier_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_name_uniqueness(data.get("supplier_name", ""), result, exclude_id=supplier_id)
        return result

    # ------------------------------------------------------------------ #
    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        name = (data.get("supplier_name") or "").strip()
        if not name:
            result.add("Supplier Name is mandatory.")
        elif len(name) > MAX_LEN_SUPPLIER_NAME:
            result.add(f"Supplier Name must not exceed {MAX_LEN_SUPPLIER_NAME} characters.")

        contact_person = data.get("contact_person") or ""
        if len(contact_person) > MAX_LEN_CONTACT_PERSON:
            result.add(f"Contact Person must not exceed {MAX_LEN_CONTACT_PERSON} characters.")

        mobile_no = (data.get("mobile_no") or "").strip()
        if mobile_no and not _MOBILE_RE.match(mobile_no):
            result.add("Mobile No. format is invalid.")
        if len(mobile_no) > MAX_LEN_PHONE:
            result.add(f"Mobile No. must not exceed {MAX_LEN_PHONE} characters.")

        phone_no = (data.get("phone_no") or "").strip()
        if phone_no and not _MOBILE_RE.match(phone_no):
            result.add("Phone No. format is invalid.")

        email = (data.get("email") or "").strip()
        if email and not _EMAIL_RE.match(email):
            result.add("Email format is invalid.")
        if len(email) > MAX_LEN_EMAIL:
            result.add(f"Email must not exceed {MAX_LEN_EMAIL} characters.")

        if len(data.get("address") or "") > MAX_LEN_ADDRESS:
            result.add(f"Address must not exceed {MAX_LEN_ADDRESS} characters.")

        if len(data.get("city") or "") > MAX_LEN_CITY:
            result.add(f"City must not exceed {MAX_LEN_CITY} characters.")

        if len(data.get("pan_vat_no") or "") > MAX_LEN_PAN_VAT:
            result.add(f"PAN/VAT No. must not exceed {MAX_LEN_PAN_VAT} characters.")

        opening_balance = data.get("opening_balance", 0)
        if opening_balance is not None:
            try:
                if float(opening_balance) < 0:
                    result.add("Opening Balance cannot be negative.")
            except (TypeError, ValueError):
                result.add("Opening Balance must be a valid number.")

        balance_type = data.get("balance_type", "Dr")
        if balance_type not in VALID_BALANCE_TYPES:
            result.add("Balance Type must be either 'Dr' or 'Cr'.")

        credit_limit = data.get("credit_limit", 0)
        if credit_limit is not None:
            try:
                if float(credit_limit) < 0:
                    result.add("Credit Limit cannot be negative.")
            except (TypeError, ValueError):
                result.add("Credit Limit must be a valid number.")

        credit_days = data.get("credit_days", 0)
        if credit_days is not None:
            try:
                if int(credit_days) < 0:
                    result.add("Credit Days cannot be negative.")
            except (TypeError, ValueError):
                result.add("Credit Days must be a valid whole number.")

        status = data.get("status", "Active")
        if status not in VALID_STATUSES:
            result.add("Status must be either 'Active' or 'Inactive'.")

    def _validate_name_uniqueness(
        self, supplier_name: str, result: ValidationResult, exclude_id: Optional[int]
    ) -> None:
        name = (supplier_name or "").strip()
        if not name:
            return  # mandatory-check already raised above; avoid a redundant duplicate lookup
        if self._name_exists_fn(name, exclude_id):
            result.add(f"Supplier Name '{name}' already exists.")

    def validate_supplier_code_unique(self, supplier_code: str, exclude_id: Optional[int] = None) -> ValidationResult:
        """Used by the Engine when a supplier code is supplied/edited manually."""
        result = ValidationResult()
        code = (supplier_code or "").strip()
        if not code:
            result.add("Supplier Code is required.")
        elif len(code) > MAX_LEN_SUPPLIER_CODE:
            result.add(f"Supplier Code must not exceed {MAX_LEN_SUPPLIER_CODE} characters.")
        elif self._code_exists_fn(code, exclude_id):
            result.add(f"Supplier Code '{code}' already exists.")
        return result
