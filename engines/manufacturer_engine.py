"""
engines/manufacturer_engine.py

Manufacturer Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - decides default values (Status=Active)
    - generates Manufacturer Codes (Settings-driven prefix)
    - generates Manufacturer Short Names (first word of the name) and
      resolves duplicates as Name / Name1 / Name2 ...
    - orchestrates validation (utils/manufacturer_validator.py) before
      touching the database (models/manufacturer_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete-only semantics

Integration with the existing V2 foundation (module-level function APIs,
NOT classes -- confirmed by reading engines/date_engine.py and
engines/settings_engine.py directly rather than assuming their shape):
    - engines.date_engine.ad_to_bs(date) / engines.date_engine.DateEngineError
    - engines.settings_engine.get_setting(key, default)
Both are imported lazily/defensively so this file can still be imported and
unit-tested (with injected fakes) in isolation even if those modules are not
on the current PYTHONPATH.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.manufacturer_model import ManufacturerModel, ManufacturerSearchFilters
from utils.manufacturer_validator import ManufacturerValidator

logger = logging.getLogger(__name__)

DEFAULT_MANUFACTURER_CODE_PREFIX = "MFG-"
DEFAULT_MANUFACTURER_CODE_PADDING = 4  # MFG-0001
MAX_SHORT_NAME_SUFFIX_ATTEMPTS = 999   # safety ceiling against a runaway loop


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning(
            "engines.date_engine not importable; ManufacturerEngine will fall "
            "back to a minimal AD-only stamp (created_at_bs/updated_at_bs left "
            "blank) until the Date Engine is wired in. Inject a date_engine "
            "explicitly to avoid this in tests."
        )
        return None


def _load_settings_engine():
    try:
        from engines import settings_engine
        return settings_engine
    except ImportError:
        logger.warning(
            "engines.settings_engine not importable; ManufacturerEngine will use "
            "the built-in default for manufacturer.code_prefix. Inject a "
            "settings_engine explicitly to avoid this in tests."
        )
        return None


def generate_short_name_base(manufacturer_name: str) -> str:
    """
    Pure function: the FIRST WORD of the manufacturer name, per the
    Manufacturer Master Blueprint's Short Name rule. No DB access, no
    de-duplication -- see ManufacturerEngine._resolve_unique_short_name()
    for the Sun / Sun1 / Sun2 collision-handling step.
    """
    words = (manufacturer_name or "").strip().split()
    return words[0] if words else ""


@dataclass
class ManufacturerDTO:
    """Read-facing representation returned by the Engine to callers (Screens/tests)."""
    manufacturer_id: int
    manufacturer_code: str
    manufacturer_name: str
    manufacturer_short_name: str
    country: Optional[str]
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
    def from_row(cls, row: dict) -> "ManufacturerDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})

    def to_dict(self) -> dict:
        return asdict(self)


class ManufacturerEngine:
    """Business-rule orchestration for the Manufacturer Master."""

    def __init__(
        self,
        model: Optional[ManufacturerModel] = None,
        date_engine: Optional[Any] = None,
        settings_engine: Optional[Any] = None,
    ) -> None:
        self._model = model or ManufacturerModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._settings_engine = settings_engine if settings_engine is not None else _load_settings_engine()
        self._validator = ManufacturerValidator(
            name_exists_fn=self._model.exists_by_name,
            code_exists_fn=self._model.exists_by_code,
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
                "date_engine.ad_to_bs() could not find today's date in the "
                "bscalendar reference table; created_at_bs/updated_at_bs will "
                "be left blank for this operation."
            )
            return None

    def _code_prefix(self) -> str:
        if self._settings_engine is not None:
            try:
                return self._settings_engine.get_setting("manufacturer.code_prefix", DEFAULT_MANUFACTURER_CODE_PREFIX)
            except Exception:  # noqa: BLE001 - settings engine must never break manufacturer creation
                logger.exception("Failed to read manufacturer.code_prefix setting; using default.")
        return DEFAULT_MANUFACTURER_CODE_PREFIX

    def generate_manufacturer_code(self) -> str:
        """
        Generates the next sequential manufacturer code, e.g. MFG-0001,
        MFG-0002. The prefix is Settings-driven (falls back to 'MFG-'); the
        sequence is derived from the highest existing numeric suffix in the
        table (including soft-deleted rows, so codes are never reused).
        """
        prefix = self._code_prefix()
        last_seq = self._model.get_last_code_sequence(prefix)
        next_seq = last_seq + 1
        return f"{prefix}{str(next_seq).zfill(DEFAULT_MANUFACTURER_CODE_PADDING)}"

    def _resolve_unique_short_name(self, manufacturer_name: str, exclude_id: Optional[int] = None) -> str:
        """
        Business Rule (Blueprint): Short Name = first word of the
        Manufacturer Name. If that short name is already taken by another
        active manufacturer, suffix it with an incrementing number:
        Sun -> Sun1 -> Sun2 -> ...
        """
        base = generate_short_name_base(manufacturer_name)
        if not base:
            return base  # empty name already fails ManufacturerValidator; nothing to resolve

        if not self._model.exists_by_short_name(base, exclude_id):
            return base

        for suffix in range(1, MAX_SHORT_NAME_SUFFIX_ATTEMPTS + 1):
            candidate = f"{base}{suffix}"
            if not self._model.exists_by_short_name(candidate, exclude_id):
                return candidate

        # Practically unreachable, but never leave a duplicate short name
        # silently unresolved -- the DB's partial unique index would reject
        # it anyway, so fail loudly and clearly instead.
        raise ValidationError([f"Could not generate a unique Short Name for '{base}' after {MAX_SHORT_NAME_SUFFIX_ATTEMPTS} attempts."])

    def _clean_payload(self, payload: dict) -> dict:
        """Applies default values and trims strings. Never touches uniqueness/DB."""
        data = dict(payload)
        data["manufacturer_name"] = (data.get("manufacturer_name") or "").strip()
        data["country"] = (data.get("country") or "").strip() or None
        data["status"] = data.get("status") or "Active"
        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_manufacturer(self, payload: dict, current_user_id: int) -> ManufacturerDTO:
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        manufacturer_code = (data.get("manufacturer_code") or "").strip()
        if manufacturer_code:
            code_check = self._validator.validate_manufacturer_code_unique(manufacturer_code)
            if not code_check.is_valid:
                raise ValidationError(code_check.errors)
        else:
            manufacturer_code = self.generate_manufacturer_code()

        short_name = self._resolve_unique_short_name(data["manufacturer_name"])

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "manufacturer_code": manufacturer_code,
            "manufacturer_name": data["manufacturer_name"],
            "manufacturer_short_name": short_name,
            "country": data["country"],
            "status": data["status"],
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            # Catches a race-condition unique-constraint violation that slipped
            # past the pre-checks above (two users saving the same name/short
            # name at once).
            if _is_unique_violation(exc):
                raise DuplicateRecordError(
                    "Manufacturer Name, Code, or Short Name already exists (concurrent save detected)."
                ) from exc
            logger.exception("Unexpected error inserting manufacturer.")
            raise

        row = self._model.get_by_id(new_id)
        return ManufacturerDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_manufacturer(self, manufacturer_id: int, payload: dict, current_user_id: int) -> ManufacturerDTO:
        existing = self._model.get_by_id(manufacturer_id)
        if existing is None:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found or has been deleted.")

        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(manufacturer_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        short_name = self._resolve_unique_short_name(data["manufacturer_name"], exclude_id=manufacturer_id)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        update_data = {
            "manufacturer_name": data["manufacturer_name"],
            "manufacturer_short_name": short_name,
            "country": data["country"],
            "status": data["status"],
            "updated_by": current_user_id,
            "updated_at_ad": now_ad,
            "updated_at_bs": now_bs,
        }

        try:
            updated = self._model.update(manufacturer_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Manufacturer Name or Short Name already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error updating manufacturer %s.", manufacturer_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found or has been deleted.")

        row = self._model.get_by_id(manufacturer_id)
        return ManufacturerDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_manufacturer(self, manufacturer_id: int, include_deleted: bool = False) -> ManufacturerDTO:
        row = self._model.get_by_id(manufacturer_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found.")
        return ManufacturerDTO.from_row(row)

    def search_manufacturers(
        self,
        search_text: Optional[str] = None,
        status: Optional[str] = None,
        country: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ManufacturerDTO], int]:
        filters = ManufacturerSearchFilters(
            search_text=search_text,
            status=status,
            country=country,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [ManufacturerDTO.from_row(r) for r in rows], total_count

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECKS (exposed for Screens to call live, e.g. on-blur checks)
    # ------------------------------------------------------------------ #
    def is_name_taken(self, manufacturer_name: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_name(manufacturer_name, exclude_id)

    def is_code_taken(self, manufacturer_code: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_code(manufacturer_code, exclude_id)

    def preview_short_name(self, manufacturer_name: str, exclude_id: Optional[int] = None) -> str:
        """Live-preview hook for the Form screen (e.g. update a read-only
        label as the user types the Manufacturer Name), without saving."""
        return self._resolve_unique_short_name(manufacturer_name, exclude_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_manufacturer(self, manufacturer_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(manufacturer_id)
        if existing is None:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found or already deleted.")

        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.soft_delete(manufacturer_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found or already deleted.")
        logger.info("Manufacturer %s soft-deleted by user %s.", manufacturer_id, current_user_id)

    def restore_manufacturer(self, manufacturer_id: int, current_user_id: int) -> ManufacturerDTO:
        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.restore(manufacturer_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Manufacturer {manufacturer_id} not found or was not deleted.")
        logger.info("Manufacturer %s restored by user %s.", manufacturer_id, current_user_id)
        row = self._model.get_by_id(manufacturer_id)
        return ManufacturerDTO.from_row(row)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) without a hard
    psycopg2 import dependency at module scope, so this helper stays reusable
    even in unit tests that stub the model layer entirely."""
    pgcode = getattr(exc, "pgcode", None)
    return pgcode == "23505"
