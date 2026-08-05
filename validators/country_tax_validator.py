"""
validators/country_tax_validator.py

Country Tax Settings Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Contains ONLY
validation rules -- it never touches the database directly except through
the uniqueness-check callback injected by the Engine, and never decides
*what to do* about a failure -- it only reports ValidationResult back.

Mirrors validators/manufacturer_validator.py's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_COUNTRY = 100
MAX_LEN_REMARKS = 1000

MIN_PERCENT = 0
MAX_PERCENT = 100

VALID_STATUSES = ("Active", "Inactive")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class CountryTaxValidator:
    """
    Stateless validation rules for Country Tax Settings.

    `country_exists_fn` is injected by the Engine (which owns the Model) so
    this class never imports the database layer directly -- keeping
    validation testable in isolation.
    """

    def __init__(self, country_exists_fn: Callable[[str, Optional[int]], bool]) -> None:
        self._country_exists_fn = country_exists_fn

    # ------------------------------------------------------------------ #
    def validate_for_create(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_country_uniqueness(data.get("country", ""), result, exclude_id=None)
        return result

    def validate_for_update(self, country_tax_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_country_uniqueness(data.get("country", ""), result, exclude_id=country_tax_id)
        return result

    # ------------------------------------------------------------------ #
    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        country = (data.get("country") or "").strip()
        if not country:
            result.add("Country is mandatory.")
        elif len(country) > MAX_LEN_COUNTRY:
            result.add(f"Country must not exceed {MAX_LEN_COUNTRY} characters.")

        remarks = data.get("remarks") or ""
        if len(remarks) > MAX_LEN_REMARKS:
            result.add(f"Remarks must not exceed {MAX_LEN_REMARKS} characters.")

        self._validate_percent(data.get("vat_percent", 0), "VAT %", result)
        self._validate_percent(data.get("custom_percent", 0), "Custom %", result)

        status = data.get("status", "Active")
        if status not in VALID_STATUSES:
            result.add("Status must be either 'Active' or 'Inactive'.")

    @staticmethod
    def _validate_percent(value, field_label: str, result: ValidationResult) -> None:
        try:
            amount = float(value) if value not in (None, "") else 0.0
        except (TypeError, ValueError):
            result.add(f"{field_label} must be a valid number.")
            return

        if amount < MIN_PERCENT or amount > MAX_PERCENT:
            result.add(f"{field_label} must be between {MIN_PERCENT} and {MAX_PERCENT}.")

    def _validate_country_uniqueness(
        self, country: str, result: ValidationResult, exclude_id: Optional[int]
    ) -> None:
        name = (country or "").strip()
        if not name:
            return  # mandatory-check already raised above; avoid a redundant duplicate lookup
        if self._country_exists_fn(name, exclude_id):
            result.add(f"Country '{name}' already exists.")


__all__ = ["CountryTaxValidator", "ValidationResult"]
