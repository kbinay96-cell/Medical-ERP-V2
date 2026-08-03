"""
utils/item_validator.py

Item Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- never touches the database directly except the
duplicate-check callbacks injected by the Engine (which owns the Model).
Mirrors utils/supplier_validator.py's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_ITEM_CODE = 20
MAX_LEN_ITEM_NAME = 200
MAX_LEN_BATCH_NO = 50

VALID_STATUSES = ("Active", "Inactive")
VALID_TAX_MODES = ("country_default", "individual")

MIN_EXPIRY_YEAR = 2000
MAX_EXPIRY_YEAR = 2100


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class ItemValidator:
    """
    Stateless validation rules for Item Master.

    `name_exists_fn` / `code_exists_fn` are injected by the Engine (which
    owns the Model), same pattern as SupplierValidator, so this class never
    imports the database layer directly.
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
        self._validate_name_uniqueness(data.get("item_name", ""), result, exclude_id=None)
        return result

    def validate_for_update(self, item_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_name_uniqueness(data.get("item_name", ""), result, exclude_id=item_id)
        return result

    # ------------------------------------------------------------------ #
    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        name = (data.get("item_name") or "").strip()
        if not name:
            result.add("Item Name is mandatory.")
        elif len(name) > MAX_LEN_ITEM_NAME:
            result.add(f"Item Name must not exceed {MAX_LEN_ITEM_NAME} characters.")

        if not data.get("unit_id"):
            result.add("Unit is mandatory.")

        for field_name, label in [
            ("purchase_rate", "Purchase Rate"),
            ("sale_rate", "Sale Rate"),
            ("mrp", "MRP"),
            ("minimum_stock", "Minimum Stock"),
        ]:
            value = data.get(field_name, 0)
            try:
                if float(value) < 0:
                    result.add(f"{label} cannot be negative.")
            except (TypeError, ValueError):
                result.add(f"{label} must be a valid number.")

        status = data.get("status", "Active")
        if status not in VALID_STATUSES:
            result.add("Status must be either 'Active' or 'Inactive'.")

        self._validate_tax_fields(data, result)

    def _validate_tax_fields(self, data: dict, result: ValidationResult) -> None:
        tax_mode = data.get("tax_mode", "country_default")
        if tax_mode not in VALID_TAX_MODES:
            result.add("Tax Mode must be either 'country_default' or 'individual'.")
            return

        if tax_mode != "individual":
            # Under country_default, the four individual-tax columns are
            # inert -- no validation needed, matching how is_serialized/
            # is_kit_item fields are treated elsewhere in the project.
            return

        vat_checked = bool(data.get("item_vat_checked"))
        if vat_checked:
            vat_percent = data.get("item_vat_percent")
            if vat_percent is None:
                result.add("VAT % is required when VAT is checked under Individual Tax mode.")
            else:
                try:
                    if float(vat_percent) < 0:
                        result.add("VAT % cannot be negative.")
                except (TypeError, ValueError):
                    result.add("VAT % must be a valid number.")

        custom_checked = bool(data.get("item_custom_checked"))
        if custom_checked:
            custom_percent = data.get("item_custom_percent")
            if custom_percent is None:
                result.add("Custom % is required when Custom is checked under Individual Tax mode.")
            else:
                try:
                    if float(custom_percent) < 0:
                        result.add("Custom % cannot be negative.")
                except (TypeError, ValueError):
                    result.add("Custom % must be a valid number.")

    def _validate_name_uniqueness(self, item_name: str, result: ValidationResult, exclude_id: Optional[int]) -> None:
        name = (item_name or "").strip()
        if not name:
            return  # mandatory-check already raised above
        if self._name_exists_fn(name, exclude_id):
            result.add(f"Item Name '{name}' already exists.")

    def validate_item_code_unique(self, item_code: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        code = (item_code or "").strip()
        if not code:
            result.add("Item Code is required.")
        elif len(code) > MAX_LEN_ITEM_CODE:
            result.add(f"Item Code must not exceed {MAX_LEN_ITEM_CODE} characters.")
        elif self._code_exists_fn(code, exclude_id):
            result.add(f"Item Code '{code}' already exists.")
        return result


def validate_batch_entry(batch_no: str, expiry_year, expiry_month, batch_qty, batch_purchase_rate) -> ValidationResult:
    """
    Pure validation for a single Opening/Purchase batch entry. Kept as a
    free function (rather than on ItemValidator) since it has no
    uniqueness-callback dependency of its own -- the Engine checks
    batch_no-per-item uniqueness itself via ItemBatchModel.exists_batch_no.
    """
    result = ValidationResult()

    batch_no = (batch_no or "").strip()
    if not batch_no:
        result.add("Batch No. is mandatory.")
    elif len(batch_no) > MAX_LEN_BATCH_NO:
        result.add(f"Batch No. must not exceed {MAX_LEN_BATCH_NO} characters.")

    try:
        year = int(expiry_year)
        if not (MIN_EXPIRY_YEAR <= year <= MAX_EXPIRY_YEAR):
            result.add("Expiry Year looks invalid.")
    except (TypeError, ValueError):
        result.add("Expiry Year must be a valid whole number.")

    try:
        month = int(expiry_month)
        if not (1 <= month <= 12):
            result.add("Expiry Month must be between 1 and 12.")
    except (TypeError, ValueError):
        result.add("Expiry Month must be a valid whole number.")

    try:
        if float(batch_qty) < 0:
            result.add("Batch Quantity cannot be negative.")
    except (TypeError, ValueError):
        result.add("Batch Quantity must be a valid number.")

    try:
        if float(batch_purchase_rate) < 0:
            result.add("Batch Purchase Rate cannot be negative.")
    except (TypeError, ValueError):
        result.add("Batch Purchase Rate must be a valid number.")

    return result


__all__ = ["ItemValidator", "ValidationResult", "validate_batch_entry"]
