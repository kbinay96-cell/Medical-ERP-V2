"""
validators/supplier_manufacturer_discount_validator.py

Supplier-Manufacturer Discount Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Contains ONLY
validation rules -- it never touches the database directly except through
the duplicate-pair-check callback injected by the Engine, and never decides
*what to do* about a failure -- it only reports ValidationResult back.

Mirrors utils/manufacturer_validator.py's shape exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REMARKS = 500

MIN_DISCOUNT_PERCENT = 0
MAX_DISCOUNT_PERCENT = 100


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class SupplierManufacturerDiscountValidator:
    """
    Stateless validation rules for the Supplier-Manufacturer Discount mapping.

    `pair_exists_fn` is injected by the Engine (which owns the Model) so this
    class never imports the database layer directly -- keeping validation
    testable in isolation, same pattern as ManufacturerValidator's
    name_exists_fn/code_exists_fn.
    """

    def __init__(
        self,
        pair_exists_fn: Callable[[int, int, Optional[int]], bool],
    ) -> None:
        self._pair_exists_fn = pair_exists_fn

    # ------------------------------------------------------------------ #
    def validate_for_create(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_pair_uniqueness(
            data.get("supplier_id"), data.get("manufacturer_id"), result, exclude_id=None
        )
        return result

    def validate_for_update(self, record_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_pair_uniqueness(
            data.get("supplier_id"), data.get("manufacturer_id"), result, exclude_id=record_id
        )
        return result

    # ------------------------------------------------------------------ #
    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        supplier_id = data.get("supplier_id")
        if not supplier_id:
            result.add("Supplier is mandatory.")

        manufacturer_id = data.get("manufacturer_id")
        if not manufacturer_id:
            result.add("Manufacturer is mandatory.")

        discount_percent = data.get("discount_percent")
        if discount_percent is None:
            result.add("Discount % is mandatory.")
        else:
            try:
                value = float(discount_percent)
            except (TypeError, ValueError):
                result.add("Discount % must be a valid number.")
            else:
                if value < MIN_DISCOUNT_PERCENT or value > MAX_DISCOUNT_PERCENT:
                    result.add(
                        f"Discount % must be between {MIN_DISCOUNT_PERCENT} and {MAX_DISCOUNT_PERCENT}."
                    )

        remarks = data.get("remarks") or ""
        if len(remarks) > MAX_LEN_REMARKS:
            result.add(f"Remarks must not exceed {MAX_LEN_REMARKS} characters.")

    def _validate_pair_uniqueness(
        self,
        supplier_id: Optional[int],
        manufacturer_id: Optional[int],
        result: ValidationResult,
        exclude_id: Optional[int],
    ) -> None:
        if not supplier_id or not manufacturer_id:
            return  # mandatory-checks already raised above; avoid a redundant duplicate lookup
        if self._pair_exists_fn(supplier_id, manufacturer_id, exclude_id):
            result.add(
                "A discount mapping for this Supplier and Manufacturer combination already exists."
            )


__all__ = ["SupplierManufacturerDiscountValidator", "ValidationResult"]
