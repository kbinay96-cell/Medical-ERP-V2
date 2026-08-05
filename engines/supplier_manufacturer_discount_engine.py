"""
engines/supplier_manufacturer_discount_engine.py

Supplier-Manufacturer Discount Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - orchestrates validation (validators/supplier_manufacturer_discount_validator.py)
      before touching the database (models/supplier_manufacturer_discount_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete-only semantics
    - resolves the effective discount % for a (supplier, manufacturer) pair
      via get_discount() -- the ONLY method the future Purchase Engine
      should call for this lookup

Integration with the existing V2 foundation (module-level function API,
NOT a class -- confirmed by reading engines/date_engine.py directly rather
than assuming its shape):
    - engines.date_engine.ad_to_bs(date) / engines.date_engine.DateEngineError
Imported lazily/defensively so this file can still be imported and unit-
tested (with an injected fake) in isolation even if that module is not on
the current PYTHONPATH -- same pattern as engines/manufacturer_engine.py.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, List, Optional, Tuple

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.supplier_manufacturer_discount_model import (
    SupplierManufacturerDiscountModel,
    SupplierManufacturerDiscountSearchFilters,
)
from validators.supplier_manufacturer_discount_validator import SupplierManufacturerDiscountValidator

logger = logging.getLogger(__name__)


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning(
            "engines.date_engine not importable; SupplierManufacturerDiscountEngine will fall "
            "back to a minimal AD-only stamp (created_at_bs/updated_at_bs left blank) until the "
            "Date Engine is wired in. Inject a date_engine explicitly to avoid this in tests."
        )
        return None


@dataclass
class SupplierManufacturerDiscountDTO:
    """Read-facing representation returned by the Engine to callers (Screens/tests)."""
    id: int
    supplier_id: int
    manufacturer_id: int
    discount_percent: float
    remarks: Optional[str]
    supplier_name: Optional[str]
    manufacturer_name: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    updated_by: Optional[int]
    updated_at_ad: Any
    updated_at_bs: Optional[str]
    deleted_by: Optional[int]
    deleted_at_ad: Any
    deleted_at_bs: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "SupplierManufacturerDiscountDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})

    def to_dict(self) -> dict:
        return asdict(self)


class SupplierManufacturerDiscountEngine:
    """Business-rule orchestration for the Supplier-Manufacturer Discount mapping."""

    def __init__(
        self,
        model: Optional[SupplierManufacturerDiscountModel] = None,
        date_engine: Optional[Any] = None,
    ) -> None:
        self._model = model or SupplierManufacturerDiscountModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = SupplierManufacturerDiscountValidator(
            pair_exists_fn=self._model.exists_by_pair,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _now_ad(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_bs(self) -> Optional[str]:
        if self._date_engine is None:
            return None
        try:
            return self._date_engine.ad_to_bs(date.today())
        except self._date_engine.DateEngineError:
            logger.warning(
                "date_engine.ad_to_bs() could not resolve today's date; created_at_bs/"
                "updated_at_bs will be left blank for this operation."
            )
            return None

    def _clean_payload(self, payload: dict) -> dict:
        """Applies default values and trims strings. Never touches uniqueness/DB."""
        data = dict(payload)
        data["supplier_id"] = data.get("supplier_id") or None
        data["manufacturer_id"] = data.get("manufacturer_id") or None
        data["discount_percent"] = data.get("discount_percent", 0) or 0
        data["remarks"] = (data.get("remarks") or "").strip() or None
        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_discount(self, payload: dict, current_user_id: int) -> SupplierManufacturerDiscountDTO:
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "supplier_id": data["supplier_id"],
            "manufacturer_id": data["manufacturer_id"],
            "discount_percent": data["discount_percent"],
            "remarks": data["remarks"],
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            # Catches a race-condition unique-constraint violation that slipped
            # past the pre-check above (two users saving the same pair at once).
            if _is_unique_violation(exc):
                raise DuplicateRecordError(
                    "A discount mapping for this Supplier and Manufacturer combination "
                    "already exists (concurrent save detected)."
                ) from exc
            logger.exception("Unexpected error inserting supplier-manufacturer discount.")
            raise

        row = self._model.get_by_id(new_id)
        return SupplierManufacturerDiscountDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_discount(
        self, record_id: int, payload: dict, current_user_id: int
    ) -> SupplierManufacturerDiscountDTO:
        existing = self._model.get_by_id(record_id)
        if existing is None:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found or has been deleted.")

        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(record_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        update_data = {
            "supplier_id": data["supplier_id"],
            "manufacturer_id": data["manufacturer_id"],
            "discount_percent": data["discount_percent"],
            "remarks": data["remarks"],
            "updated_by": current_user_id,
            "updated_at_ad": now_ad,
            "updated_at_bs": now_bs,
        }

        try:
            updated = self._model.update(record_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError(
                    "A discount mapping for this Supplier and Manufacturer combination "
                    "already exists (concurrent save detected)."
                ) from exc
            logger.exception("Unexpected error updating supplier-manufacturer discount %s.", record_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found or has been deleted.")

        row = self._model.get_by_id(record_id)
        return SupplierManufacturerDiscountDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_discount_record(
        self, record_id: int, include_deleted: bool = False
    ) -> SupplierManufacturerDiscountDTO:
        row = self._model.get_by_id(record_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found.")
        return SupplierManufacturerDiscountDTO.from_row(row)

    def search_discounts(
        self,
        search_text: Optional[str] = None,
        supplier_id: Optional[int] = None,
        manufacturer_id: Optional[int] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SupplierManufacturerDiscountDTO], int]:
        filters = SupplierManufacturerDiscountSearchFilters(
            search_text=search_text,
            supplier_id=supplier_id,
            manufacturer_id=manufacturer_id,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [SupplierManufacturerDiscountDTO.from_row(r) for r in rows], total_count

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECK (exposed for Screens to call live, e.g. on-blur checks)
    # ------------------------------------------------------------------ #
    def is_pair_taken(
        self, supplier_id: int, manufacturer_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        return self._model.exists_by_pair(supplier_id, manufacturer_id, exclude_id)

    # ------------------------------------------------------------------ #
    # DISCOUNT RESOLUTION -- the ONLY method the future Purchase Engine
    # should call. NEVER raises: a missing mapping or any error resolves
    # to 0.0 (no discount), since Purchase entry must never be blocked or
    # crash because of a missing/broken discount configuration.
    # ------------------------------------------------------------------ #
    def get_discount(self, supplier_id: int, manufacturer_id: int) -> float:
        """
        Returns the effective discount % for a (supplier, manufacturer)
        pair. Returns 0.0 if no active mapping exists, or if any error
        occurs while resolving it -- this method must never raise.
        """
        try:
            row = self._model.get_by_pair(supplier_id, manufacturer_id)
        except Exception:  # noqa: BLE001 -- must never break a Purchase entry
            logger.exception(
                "get_discount: failed to resolve discount for supplier_id=%s manufacturer_id=%s; "
                "defaulting to 0.0.",
                supplier_id, manufacturer_id,
            )
            return 0.0

        if row is None:
            return 0.0

        try:
            return float(row.get("discount_percent") or 0.0)
        except (TypeError, ValueError):
            logger.warning(
                "get_discount: non-numeric discount_percent for supplier_id=%s manufacturer_id=%s; "
                "defaulting to 0.0.",
                supplier_id, manufacturer_id,
            )
            return 0.0

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_discount(self, record_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(record_id)
        if existing is None:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found or already deleted.")

        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.soft_delete(record_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found or already deleted.")
        logger.info("Discount mapping %s soft-deleted by user %s.", record_id, current_user_id)

    def restore_discount(self, record_id: int, current_user_id: int) -> SupplierManufacturerDiscountDTO:
        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.restore(record_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Discount mapping {record_id} not found or was not deleted.")
        logger.info("Discount mapping %s restored by user %s.", record_id, current_user_id)
        row = self._model.get_by_id(record_id)
        return SupplierManufacturerDiscountDTO.from_row(row)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) without a hard
    psycopg2 import dependency at module scope -- same helper already used
    in engines/manufacturer_engine.py and engines/supplier_engine.py."""
    return getattr(exc, "pgcode", None) == "23505"


__all__ = ["SupplierManufacturerDiscountEngine", "SupplierManufacturerDiscountDTO"]
