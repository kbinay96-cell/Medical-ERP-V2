"""
engines/country_tax_engine.py

Country Tax Settings Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - decides default values (Status=Active, VAT %/Custom %=0)
    - orchestrates validation (validators/country_tax_validator.py) before
      touching the database (models/country_tax_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete-only semantics
    - resolves get_tax_for_country() -- the lookup engines/item_lookup_registry.py's
      country_tax_lookup() (and, later, the Purchase Engine) call for a
      country's effective (vat_percent, custom_percent)

Integration with the existing V2 foundation (module-level function APIs,
NOT classes -- confirmed by reading engines/date_engine.py directly),
mirrors engines/manufacturer_engine.py's shape exactly, minus the code /
short-name generation machinery this module has no use for.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.country_tax_model import CountryTaxModel, CountryTaxSearchFilters
from validators.country_tax_validator import CountryTaxValidator

logger = logging.getLogger(__name__)

DEFAULT_TAX_FOR_UNCONFIGURED_COUNTRY: tuple[float, float] = (0.0, 0.0)


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning(
            "engines.date_engine not importable; CountryTaxEngine will fall "
            "back to a minimal AD-only stamp (created_at_bs/updated_at_bs "
            "left blank) until the Date Engine is wired in. Inject a "
            "date_engine explicitly to avoid this in tests."
        )
        return None


@dataclass
class CountryTaxDTO:
    """Read-facing representation returned by the Engine to callers (Screens/tests)."""
    country_tax_id: int
    country: str
    vat_percent: float
    custom_percent: float
    remarks: Optional[str]
    status: str
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
    def from_row(cls, row: dict) -> "CountryTaxDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})

    def to_dict(self) -> dict:
        return asdict(self)


class CountryTaxEngine:
    """Business-rule orchestration for Country Tax Settings."""

    def __init__(
        self,
        model: Optional[CountryTaxModel] = None,
        date_engine: Optional[Any] = None,
    ) -> None:
        self._model = model or CountryTaxModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = CountryTaxValidator(country_exists_fn=self._model.exists_by_country)

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
                "date_engine.ad_to_bs() could not resolve today's date; "
                "created_at_bs/updated_at_bs will be left blank for this operation."
            )
            return None

    def _clean_payload(self, payload: dict) -> dict:
        """Applies default values and trims strings. Never touches uniqueness/DB."""
        data = dict(payload)
        data["country"] = (data.get("country") or "").strip()
        data["remarks"] = (data.get("remarks") or "").strip() or None
        data["vat_percent"] = data.get("vat_percent") if data.get("vat_percent") not in (None, "") else 0
        data["custom_percent"] = data.get("custom_percent") if data.get("custom_percent") not in (None, "") else 0
        data["status"] = data.get("status") or "Active"
        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_tax(self, payload: dict, current_user_id: int) -> CountryTaxDTO:
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "country": data["country"],
            "vat_percent": data["vat_percent"],
            "custom_percent": data["custom_percent"],
            "remarks": data["remarks"],
            "status": data["status"],
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError(
                    f"Country '{data['country']}' already exists (concurrent save detected)."
                ) from exc
            logger.exception("Unexpected error inserting country tax.")
            raise

        row = self._model.get_by_id(new_id)
        return CountryTaxDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_tax(self, country_tax_id: int, payload: dict, current_user_id: int) -> CountryTaxDTO:
        existing = self._model.get_by_id(country_tax_id)
        if existing is None:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found or has been deleted.")

        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(country_tax_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        update_data = {
            "country": data["country"],
            "vat_percent": data["vat_percent"],
            "custom_percent": data["custom_percent"],
            "remarks": data["remarks"],
            "status": data["status"],
            "updated_by": current_user_id,
            "updated_at_ad": now_ad,
            "updated_at_bs": now_bs,
        }

        try:
            updated = self._model.update(country_tax_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Country already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error updating country tax %s.", country_tax_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found or has been deleted.")

        row = self._model.get_by_id(country_tax_id)
        return CountryTaxDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_tax_record(self, country_tax_id: int, include_deleted: bool = False) -> CountryTaxDTO:
        row = self._model.get_by_id(country_tax_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found.")
        return CountryTaxDTO.from_row(row)

    def search_taxes(
        self,
        search_text: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CountryTaxDTO], int]:
        filters = CountryTaxSearchFilters(
            search_text=search_text,
            status=status,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [CountryTaxDTO.from_row(r) for r in rows], total_count

    def list_active(self) -> list[CountryTaxDTO]:
        rows = self._model.list_active()
        return [CountryTaxDTO.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECKS (exposed for Screens to call live, e.g. on-blur checks)
    # ------------------------------------------------------------------ #
    def is_country_taken(self, country: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_country(country, exclude_id)

    # ------------------------------------------------------------------ #
    # LOOKUP -- consumed by engines/item_lookup_registry.py's
    # country_tax_lookup() and the future Purchase Engine.
    # ------------------------------------------------------------------ #
    def get_tax_for_country(self, country: Optional[str]) -> tuple[float, float]:
        """
        Returns (vat_percent, custom_percent) for the given country. Never
        raises -- an unconfigured, unknown, missing, or Inactive country
        always resolves to (0.0, 0.0), matching the blueprint's rule
        already documented in engines/item_lookup_registry.py.
        """
        if not country:
            return DEFAULT_TAX_FOR_UNCONFIGURED_COUNTRY

        try:
            row = self._model.get_by_country(country)
        except Exception:  # noqa: BLE001 -- tax lookup must never break the caller
            logger.exception("get_tax_for_country: database error resolving '%s'.", country)
            return DEFAULT_TAX_FOR_UNCONFIGURED_COUNTRY

        if row is None or row.get("status") != "Active":
            return DEFAULT_TAX_FOR_UNCONFIGURED_COUNTRY

        try:
            return float(row.get("vat_percent") or 0), float(row.get("custom_percent") or 0)
        except (TypeError, ValueError):
            logger.warning("get_tax_for_country: non-numeric vat/custom percent for '%s'.", country)
            return DEFAULT_TAX_FOR_UNCONFIGURED_COUNTRY

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_tax(self, country_tax_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(country_tax_id)
        if existing is None:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found or already deleted.")

        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.soft_delete(country_tax_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found or already deleted.")
        logger.info("Country Tax %s soft-deleted by user %s.", country_tax_id, current_user_id)

    def restore_tax(self, country_tax_id: int, current_user_id: int) -> CountryTaxDTO:
        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.restore(country_tax_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Country Tax {country_tax_id} not found or was not deleted.")
        logger.info("Country Tax %s restored by user %s.", country_tax_id, current_user_id)
        row = self._model.get_by_id(country_tax_id)
        return CountryTaxDTO.from_row(row)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) -- same
    helper already used in engines/manufacturer_engine.py."""
    return getattr(exc, "pgcode", None) == "23505"


__all__ = ["CountryTaxEngine", "CountryTaxDTO"]
