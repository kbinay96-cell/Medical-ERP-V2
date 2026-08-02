"""
utils/manufacturer_validator.py

Manufacturer Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Contains ONLY
validation rules -- it never touches the database directly except through
the duplicate-check callbacks injected by the Engine, and never decides
*what to do* about a failure -- it only reports ValidationResult back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_MANUFACTURER_CODE = 20
MAX_LEN_MANUFACTURER_NAME = 150
MAX_LEN_SHORT_NAME = 50
MAX_LEN_COUNTRY = 100

VALID_STATUSES = ("Active", "Inactive")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class ManufacturerValidator:
    """
    Stateless validation rules for the Manufacturer Master.

    `name_exists_fn` / `code_exists_fn` are injected by the Engine (which
    owns the Model) so this class never imports the database layer
    directly -- keeping validation testable in isolation.
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
        self._validate_name_uniqueness(data.get("manufacturer_name", ""), result, exclude_id=None)
        return result

    def validate_for_update(self, manufacturer_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_name_uniqueness(data.get("manufacturer_name", ""), result, exclude_id=manufacturer_id)
        return result

    # ------------------------------------------------------------------ #
    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        name = (data.get("manufacturer_name") or "").strip()
        if not name:
            result.add("Manufacturer Name is mandatory.")
        elif len(name) > MAX_LEN_MANUFACTURER_NAME:
            result.add(f"Manufacturer Name must not exceed {MAX_LEN_MANUFACTURER_NAME} characters.")
        elif not any(ch.isalnum() for ch in name):
            result.add("Manufacturer Name must contain at least one letter or digit.")

        country = data.get("country") or ""
        if len(country) > MAX_LEN_COUNTRY:
            result.add(f"Country must not exceed {MAX_LEN_COUNTRY} characters.")

        status = data.get("status", "Active")
        if status not in VALID_STATUSES:
            result.add("Status must be either 'Active' or 'Inactive'.")

    def _validate_name_uniqueness(
        self, manufacturer_name: str, result: ValidationResult, exclude_id: Optional[int]
    ) -> None:
        name = (manufacturer_name or "").strip()
        if not name:
            return  # mandatory-check already raised above; avoid a redundant duplicate lookup
        if self._name_exists_fn(name, exclude_id):
            result.add(f"Manufacturer Name '{name}' already exists.")

    def validate_manufacturer_code_unique(
        self, manufacturer_code: str, exclude_id: Optional[int] = None
    ) -> ValidationResult:
        """Used by the Engine when a manufacturer code is supplied/edited manually."""
        result = ValidationResult()
        code = (manufacturer_code or "").strip()
        if not code:
            result.add("Manufacturer Code is required.")
        elif len(code) > MAX_LEN_MANUFACTURER_CODE:
            result.add(f"Manufacturer Code must not exceed {MAX_LEN_MANUFACTURER_CODE} characters.")
        elif self._code_exists_fn(code, exclude_id):
            result.add(f"Manufacturer Code '{code}' already exists.")
        return result
