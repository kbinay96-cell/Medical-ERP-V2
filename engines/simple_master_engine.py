"""
engines/simple_master_engine.py

Generic Simple Master Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONE reusable Engine that drives Category, Sub Category, Item Group, Unit,
and Generic -- five tables sharing an identical shape (see
database/schema_simple_masters.sql). It owns:
    - Mandatory-field / length validation
    - Case-insensitive uniqueness (scoped to a parent for Sub Category)
    - BS-first audit stamping via the shared Date Engine
    - Soft-delete-only lifecycle

Manufacturer is DELIBERATELY NOT included here -- it has its own dedicated
engine (Country, auto short-name generation, Settings-driven code prefix,
future VAT/Custom tax integration are all business rules this generic
Engine has no business deciding).

This file is also the ONLY place `screens/master_manage_screen.py` talks
to for any of these five tables (via the factory functions at the bottom),
and it is what Item Master's own Engine will call to resolve Category /
Sub Category / Item Group / Unit / Generic lookups.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.simple_master_model import MasterTableConfig, SimpleMasterModel

logger = logging.getLogger(__name__)

MAX_CODE_LENGTH = 20
MAX_NAME_LENGTH = 150


def _load_date_engine():
    """Lazy import -- keeps this module importable in unit tests on a
    machine without database/db.py wired up yet, same reasoning already
    used in engines/supplier_engine.py."""
    try:
        from engines.date_engine import ad_to_bs, DateEngineError
        return ad_to_bs, DateEngineError
    except ImportError:
        logger.warning(
            "engines.date_engine not importable; created_at_bs/updated_at_bs "
            "will be left blank until it is wired in."
        )
        return None, None


def _load_settings_engine():
    """Same lazy-import pattern as engines/manufacturer_engine.py's
    _load_settings_engine() -- settings_engine exposes a module-level
    get_setting(key, default), not a class."""
    try:
        from engines import settings_engine
        return settings_engine
    except ImportError:
        logger.warning(
            "engines.settings_engine not importable; SimpleMasterEngine will "
            "use each table's built-in default code prefix."
        )
        return None


@dataclass
class MasterDTO:
    """Read-facing representation returned by SimpleMasterEngine to callers
    (Screens, MasterManageDialog, other Engines' lookup resolution)."""
    id: int
    code: str
    name: str
    status: str
    remarks: Optional[str]
    is_deleted: bool
    extra: dict[str, Any] = field(default_factory=dict)


class SimpleMasterEngine:
    """Business-rule orchestration shared by every simple lookup master."""

    def __init__(self, config: MasterTableConfig, model: Optional[SimpleMasterModel] = None) -> None:
        self.config = config
        self._model = model or SimpleMasterModel(config)
        self._ad_to_bs, self._DateEngineError = _load_date_engine()
        self._settings_engine = _load_settings_engine()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _now_ad(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_bs(self) -> Optional[str]:
        if self._ad_to_bs is None:
            return None
        try:
            return self._ad_to_bs(date.today())
        except self._DateEngineError:
            logger.warning("ad_to_bs() could not resolve today's date; BS audit field left blank.")
            return None

    def _row_to_dto(self, row: dict) -> MasterDTO:
        cfg = self.config
        extra: dict[str, Any] = {}
        if cfg.scope_column:
            extra[cfg.scope_column] = row.get(cfg.scope_column)
        return MasterDTO(
            id=row[cfg.id_column],
            code=row.get("code"),
            name=row.get("name"),
            status=row.get("status") or "Active",
            remarks=row.get("remarks"),
            is_deleted=bool(row.get("is_deleted")),
            extra=extra,
        )

    def _code_prefix(self) -> str:
        """Same pattern as engines/manufacturer_engine.py's _code_prefix():
        Settings-driven, falls back to the table's built-in default."""
        cfg = self.config
        if self._settings_engine is not None and cfg.code_prefix_setting_key:
            try:
                return self._settings_engine.get_setting(cfg.code_prefix_setting_key, cfg.code_prefix)
            except Exception:  # noqa: BLE001 - settings engine must never break creation
                logger.exception("Failed to read %s setting; using default.", cfg.code_prefix_setting_key)
        return cfg.code_prefix

    def generate_code(self) -> str:
        """Generates the next sequential code for this table, e.g.
        CAT-0001, SUB-0001 -- same pattern as ItemEngine.generate_item_code()
        and ManufacturerEngine.generate_manufacturer_code()."""
        prefix = self._code_prefix()
        last_seq = self._model.get_last_code_sequence(prefix)
        next_seq = last_seq + 1
        return f"{prefix}{str(next_seq).zfill(4)}"

    def _validate_fields(self, code: str, name: str) -> list[str]:
        errors: list[str] = []
        label = self.config.table_name.replace("_", " ").title()

        if not name:
            errors.append(f"{label} Name is mandatory.")
        elif len(name) > MAX_NAME_LENGTH:
            errors.append(f"{label} Name must not exceed {MAX_NAME_LENGTH} characters.")

        if code and len(code) > MAX_CODE_LENGTH:
            errors.append(f"{label} Code must not exceed {MAX_CODE_LENGTH} characters.")

        return errors

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create(self, payload: dict[str, Any], current_user_id: int, scope_id: Optional[int] = None) -> MasterDTO:
        cfg = self.config

        if cfg.scope_column and scope_id is None:
            raise ValidationError(["A parent selection is required before saving."])

        code = (payload.get("code") or "").strip()
        name = (payload.get("name") or "").strip()
        status = payload.get("status") or "Active"
        remarks = (payload.get("remarks") or "").strip() or None

        errors = self._validate_fields(code, name)
        if errors:
            raise ValidationError(errors)

        if self._model.exists_by_name(name, scope_id=scope_id):
            raise DuplicateRecordError(f"'{name}' already exists.")

        if code:
            if self._model.exists_by_code(code, scope_id=scope_id):
                raise DuplicateRecordError(f"Code '{code}' already exists.")
        else:
            # Left blank -- auto-generate (e.g. CAT-0001), same UX as
            # Item Master's own Item Code field.
            code = self.generate_code()

        insert_data: dict[str, Any] = {
            "code": code,
            "name": name,
            "status": status,
            "remarks": remarks,
            "created_by": current_user_id,
            "created_at_ad": self._now_ad(),
            "created_at_bs": self._now_bs(),
        }
        if cfg.scope_column:
            insert_data[cfg.scope_column] = scope_id

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError(f"'{name}' already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting into %s.", cfg.table_name)
            raise

        row = self._model.get_by_id(new_id)
        return self._row_to_dto(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update(
        self, record_id: int, payload: dict[str, Any], current_user_id: int, scope_id: Optional[int] = None
    ) -> MasterDTO:
        cfg = self.config
        existing = self._model.get_by_id(record_id)
        if existing is None:
            raise RecordNotFoundError(f"Record {record_id} not found or has been deleted.")

        if cfg.scope_column and scope_id is None:
            raise ValidationError(["A parent selection is required before saving."])

        code = (payload.get("code") or "").strip()
        name = (payload.get("name") or "").strip()
        status = payload.get("status") or "Active"
        remarks = (payload.get("remarks") or "").strip() or None

        errors = self._validate_fields(code, name)
        if errors:
            raise ValidationError(errors)

        if self._model.exists_by_name(name, exclude_id=record_id, scope_id=scope_id):
            raise DuplicateRecordError(f"'{name}' already exists.")

        if code:
            if self._model.exists_by_code(code, exclude_id=record_id, scope_id=scope_id):
                raise DuplicateRecordError(f"Code '{code}' already exists.")
        else:
            # Left blank on edit too -- keep the record's existing code
            # rather than writing another blank (which would collide with
            # any other blank-code row at the DB's unique index).
            code = existing.get("code") or self.generate_code()

        update_data: dict[str, Any] = {
            "code": code,
            "name": name,
            "status": status,
            "remarks": remarks,
            "updated_by": current_user_id,
            "updated_at_ad": self._now_ad(),
            "updated_at_bs": self._now_bs(),
        }
        if cfg.scope_column:
            update_data[cfg.scope_column] = scope_id

        try:
            updated = self._model.update(record_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError(f"'{name}' already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error updating %s %s.", cfg.table_name, record_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Record {record_id} not found or has been deleted.")

        row = self._model.get_by_id(record_id)
        return self._row_to_dto(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get(self, record_id: int, include_deleted: bool = False) -> MasterDTO:
        row = self._model.get_by_id(record_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Record {record_id} not found.")
        return self._row_to_dto(row)

    def search(self, search_text: Optional[str] = None, include_deleted: bool = False) -> list[MasterDTO]:
        rows = self._model.search(search_text=search_text, include_deleted=include_deleted)
        return [self._row_to_dto(r) for r in rows]

    def list_active(self) -> list[MasterDTO]:
        rows = self._model.list_active()
        return [self._row_to_dto(r) for r in rows]

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete(self, record_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(record_id)
        if existing is None:
            raise RecordNotFoundError(f"Record {record_id} not found or already deleted.")
        ok = self._model.soft_delete(record_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Record {record_id} not found or already deleted.")
        logger.info("%s %s soft-deleted by user %s.", self.config.table_name, record_id, current_user_id)

    def restore(self, record_id: int, current_user_id: int) -> MasterDTO:
        ok = self._model.restore(record_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Record {record_id} not found or was not deleted.")
        logger.info("%s %s restored by user %s.", self.config.table_name, record_id, current_user_id)
        row = self._model.get_by_id(record_id)
        return self._row_to_dto(row)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) -- same
    helper already used in engines/supplier_engine.py."""
    return getattr(exc, "pgcode", None) == "23505"


# ------------------------------------------------------------------ #
# Factory functions -- one per concrete table. Every caller (Item Master
# screens, MasterManageDialog, other Engines) gets its SimpleMasterEngine
# through one of these rather than constructing MasterTableConfig itself,
# so the table name / id column / scope column are defined in exactly
# ONE place each.
# ------------------------------------------------------------------ #

def category_engine() -> SimpleMasterEngine:
    return SimpleMasterEngine(MasterTableConfig(
        table_name="category", id_column="category_id",
        code_prefix="CAT-", code_prefix_setting_key="category.code_prefix",
    ))


def sub_category_engine() -> SimpleMasterEngine:
    return SimpleMasterEngine(MasterTableConfig(
        table_name="sub_category", id_column="sub_category_id", scope_column="category_id",
        code_prefix="SUB-", code_prefix_setting_key="sub_category.code_prefix",
    ))


def item_group_engine() -> SimpleMasterEngine:
    return SimpleMasterEngine(MasterTableConfig(
        table_name="item_group", id_column="item_group_id",
        code_prefix="GRP-", code_prefix_setting_key="item_group.code_prefix",
    ))


def unit_engine() -> SimpleMasterEngine:
    return SimpleMasterEngine(MasterTableConfig(
        table_name="unit", id_column="unit_id",
        code_prefix="UNT-", code_prefix_setting_key="unit.code_prefix",
    ))


def generic_engine() -> SimpleMasterEngine:
    return SimpleMasterEngine(MasterTableConfig(
        table_name="generic", id_column="generic_id",
        code_prefix="GEN-", code_prefix_setting_key="generic.code_prefix",
    ))


__all__ = [
    "MasterDTO",
    "SimpleMasterEngine",
    "category_engine",
    "sub_category_engine",
    "item_group_engine",
    "unit_engine",
    "generic_engine",
]
