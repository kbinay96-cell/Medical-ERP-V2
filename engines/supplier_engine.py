"""
engines/supplier_engine.py

Supplier Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the ONLY
place that:
    - decides default values (Opening Balance=0, Balance Type=Dr, Status=Active)
    - generates Supplier Codes
    - orchestrates validation (utils/supplier_validator.py) before touching
      the database (models/supplier_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete-only semantics

Integration with existing V2 foundation:
    - engines/date_engine.py  -> DateEngine (centralized BS<->AD engine)
    - engines/settings_engine.py -> SettingsEngine (e.g. supplier code prefix)
  Both are imported lazily/defensively so this file can still be imported and
  unit-tested (with injected fakes) in isolation even if those modules are not
  on the current PYTHONPATH.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date,datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.supplier_model import SupplierModel, SupplierSearchFilters
from utils import image_manager
from utils.supplier_validator import SupplierValidator

logger = logging.getLogger(__name__)

DEFAULT_SUPPLIER_CODE_PREFIX = "SUP-"
DEFAULT_SUPPLIER_CODE_PADDING = 4  # SUP-0001


def _load_date_engine():
    """
    Loads the centralized, LOCKED Date Engine module
    (engines/date_engine.py). That module is function-based
    (ad_to_bs, DateEngineError) -- it is NOT a class -- so we
    return the module object itself, not an instance.
    """
    try:
        import engines.date_engine as date_engine_module
        return date_engine_module
    except ImportError:
        logger.warning(
            "engines.date_engine module not found on PYTHONPATH; "
            "SupplierEngine will fall back to a minimal AD-only stamp "
            "(created_at_bs/updated_at_bs will be left blank) until the "
            "real Date Engine is wired in. Inject a date_engine explicitly "
            "to avoid this in tests."
        )
        return None


def _load_settings_engine():
    try:
        from engines import settings_engine
        return settings_engine
    except ImportError:
        logger.warning(
            "engines.settings_engine not importable; SupplierEngine will use "
            "the built-in default for supplier.code_prefix. Inject a "
            "settings_engine explicitly to avoid this in tests."
        )
        return None


@dataclass
class SupplierDTO:
    """Read-facing representation returned by the Engine to callers (Screens/tests)."""
    supplier_id: int
    supplier_code: str
    supplier_name: str
    contact_person: Optional[str]
    mobile_no: Optional[str]
    phone_no: Optional[str]
    email: Optional[str]
    address: Optional[str]
    city: Optional[str]
    pan_vat_no: Optional[str]
    opening_balance: float
    balance_type: str
    credit_limit: float
    credit_days: int
    status: str
    remarks: Optional[str]
    company_id: Optional[int]
    photo_path: Optional[str]
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
    def from_row(cls, row: dict) -> "SupplierDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})

    def to_dict(self) -> dict:
        return asdict(self)


class SupplierEngine:
    """Business-rule orchestration for the Supplier Master."""

    def __init__(
        self,
        model: Optional[SupplierModel] = None,
        date_engine: Optional[Any] = None,
        settings_engine: Optional[Any] = None,
    ) -> None:
        self._model = model or SupplierModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._settings_engine = settings_engine if settings_engine is not None else _load_settings_engine()
        self._validator = SupplierValidator(
            name_exists_fn=self._model.exists_by_name,
            code_exists_fn=self._model.exists_by_code,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _now_ad(self) -> datetime:
        return datetime.now(timezone.utc)

    def _load_date_engine():
        try:
            from engines import date_engine
            return date_engine
        except ImportError:
            logger.warning(
                "engines.date_engine not importable; SupplierEngine will fall "
                "back to a minimal AD-only stamp (created_at_bs/updated_at_bs "
                "left blank) until the Date Engine is wired in. Inject a "
                "date_engine explicitly to avoid this in tests."
            )
            return None

    def _now_bs(self) -> Optional[str]:
        """
        Returns today's date in BS ('YYYY-MM-DD'), via the centralized
        Date Engine. Returns None only if the Date Engine module itself
        is unavailable, or if today's AD date isn't found in the
        bscalendar reference table yet (see date_engine.DateEngineError).
        """
        if self._date_engine is None:
            return None
        try:
            return self._date_engine.ad_to_bs(self._now_ad().date())
        except self._date_engine.DateEngineError as e:
            logger.warning(f"_now_bs: BS conversion unavailable ({e}). created_at_bs will be blank.")
            return None

    def _code_prefix(self) -> str:
        if self._settings_engine is not None:
            try:
                return self._settings_engine.get_setting("supplier.code_prefix", DEFAULT_SUPPLIER_CODE_PREFIX)
            except Exception:  # noqa: BLE001 - settings engine must never break supplier creation
                logger.exception("Failed to read supplier.code_prefix setting; using default.")
        return DEFAULT_SUPPLIER_CODE_PREFIX

    def generate_supplier_code(self) -> str:
        """
        Generates the next sequential supplier code, e.g. SUP-0001, SUP-0002.
        The prefix is Settings-driven (falls back to 'SUP-') per the project's
        "zero hardcoded values" philosophy; the sequence itself is derived
        from the highest existing numeric suffix in the table (including
        soft-deleted rows, so codes are never reused).
        """
        prefix = self._code_prefix()
        last_seq = self._model.get_last_code_sequence(prefix)
        next_seq = last_seq + 1
        return f"{prefix}{str(next_seq).zfill(DEFAULT_SUPPLIER_CODE_PADDING)}"

    def _clean_payload(self, payload: dict) -> dict:
        """Applies default values and trims strings. Never touches uniqueness/DB."""
        data = dict(payload)
        data["supplier_name"] = (data.get("supplier_name") or "").strip()
        data["contact_person"] = (data.get("contact_person") or "").strip() or None
        data["mobile_no"] = (data.get("mobile_no") or "").strip() or None
        data["phone_no"] = (data.get("phone_no") or "").strip() or None
        data["email"] = (data.get("email") or "").strip() or None
        data["address"] = (data.get("address") or "").strip() or None
        data["city"] = (data.get("city") or "").strip() or None
        data["pan_vat_no"] = (data.get("pan_vat_no") or "").strip() or None
        data["remarks"] = (data.get("remarks") or "").strip() or None
        data["company_id"] = data.get("company_id") or None

        data["opening_balance"] = data.get("opening_balance", 0) or 0
        data["balance_type"] = data.get("balance_type") or "Dr"
        data["credit_limit"] = data.get("credit_limit", 0) or 0
        data["credit_days"] = data.get("credit_days", 0) or 0
        data["status"] = data.get("status") or "Active"
        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_supplier(self, payload: dict, current_user_id: int) -> SupplierDTO:
        payload = dict(payload)
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        supplier_code = (data.get("supplier_code") or "").strip()
        if supplier_code:
            code_check = self._validator.validate_supplier_code_unique(supplier_code)
            if not code_check.is_valid:
                raise ValidationError(code_check.errors)
        else:
            supplier_code = self.generate_supplier_code()

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "supplier_code": supplier_code,
            "supplier_name": data["supplier_name"],
            "contact_person": data["contact_person"],
            "mobile_no": data["mobile_no"],
            "phone_no": data["phone_no"],
            "email": data["email"],
            "address": data["address"],
            "city": data["city"],
            "pan_vat_no": data["pan_vat_no"],
            "opening_balance": data["opening_balance"],
            "balance_type": data["balance_type"],
            "credit_limit": data["credit_limit"],
            "credit_days": data["credit_days"],
            "status": data["status"],
            "remarks": data["remarks"],
            "company_id": data["company_id"],
            "photo_path": image_manager.apply_entity_photo(
                payload, existing_path=None, subfolder="suppliers", filename_stem=supplier_code,
            ),
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            # Catches a race-condition unique-constraint violation that slipped
            # past the pre-check above (two users saving the same name at once).
            if _is_unique_violation(exc):
                raise DuplicateRecordError(
                    f"Supplier Name or Code already exists (concurrent save detected)."
                ) from exc
            logger.exception("Unexpected error inserting supplier.")
            raise

        row = self._model.get_by_id(new_id)
        return SupplierDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_supplier(self, supplier_id: int, payload: dict, current_user_id: int) -> SupplierDTO:
        existing = self._model.get_by_id(supplier_id)
        if existing is None:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found or has been deleted.")

        payload = dict(payload)
        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(supplier_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        update_data = {
            "supplier_name": data["supplier_name"],
            "contact_person": data["contact_person"],
            "mobile_no": data["mobile_no"],
            "phone_no": data["phone_no"],
            "email": data["email"],
            "address": data["address"],
            "city": data["city"],
            "pan_vat_no": data["pan_vat_no"],
            "opening_balance": data["opening_balance"],
            "balance_type": data["balance_type"],
            "credit_limit": data["credit_limit"],
            "credit_days": data["credit_days"],
            "status": data["status"],
            "remarks": data["remarks"],
            "company_id": data["company_id"],
            "photo_path": image_manager.apply_entity_photo(
                payload,
                existing_path=existing.get("photo_path"),
                subfolder="suppliers",
                filename_stem=existing.get("supplier_code") or data.get("supplier_code") or str(supplier_id),
            ),
            "updated_by": current_user_id,
            "updated_at_ad": now_ad,
            "updated_at_bs": now_bs,
        }

        try:
            updated = self._model.update(supplier_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Supplier Name already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error updating supplier %s.", supplier_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found or has been deleted.")

        row = self._model.get_by_id(supplier_id)
        return SupplierDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_supplier(self, supplier_id: int, include_deleted: bool = False) -> SupplierDTO:
        row = self._model.get_by_id(supplier_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found.")
        return SupplierDTO.from_row(row)

    def get_current_balance(self, supplier_id: int) -> float:
        """Placeholder until the full Supplier Ledger (invoices minus
        payments) exists. Returns opening_balance for now. Callers (e.g.
        the Purchase Invoice View dialog) should always call this method
        rather than reading opening_balance directly, so the real
        calculation can replace this internal logic later without any
        other file needing to change."""
        supplier = self.get_supplier(supplier_id)
        return supplier.opening_balance or 0.0

    def search_suppliers(
        self,
        search_text: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[SupplierDTO], int]:
        filters = SupplierSearchFilters(
            search_text=search_text,
            status=status,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [SupplierDTO.from_row(r) for r in rows], total_count

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECKS (exposed for Screens to call live, e.g. on-blur checks)
    # ------------------------------------------------------------------ #
    def is_name_taken(self, supplier_name: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_name(supplier_name, exclude_id)

    def is_code_taken(self, supplier_code: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_code(supplier_code, exclude_id)

    # ------------------------------------------------------------------ #
    # ACTIVE SUPPLIERS
    # ------------------------------------------------------------------ #
    def get_active_suppliers(self, include_deleted: bool = False) -> list[SupplierDTO]:
        """
        Returns a list of active suppliers (status='Active').
        This is the ONLY function screens should call when they need
        a selection list of suppliers (e.g., for purchase entries).
        """
        try:
            filters = SupplierSearchFilters(
                status="Active",
                include_deleted=include_deleted,
                page=1,
                page_size=1000,  # large enough to get all active suppliers
            )
            rows, _ = self._model.search(filters)
            return [SupplierDTO.from_row(r) for r in rows]
        except Exception as e:
            logger.exception("get_active_suppliers: database error.")
            return []

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_supplier(self, supplier_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(supplier_id)
        if existing is None:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found or already deleted.")

        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.soft_delete(supplier_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found or already deleted.")
        logger.info("Supplier %s soft-deleted by user %s.", supplier_id, current_user_id)

    def restore_supplier(self, supplier_id: int, current_user_id: int) -> SupplierDTO:
        now_ad = self._now_ad()
        now_bs = self._now_bs()
        ok = self._model.restore(supplier_id, current_user_id, now_ad, now_bs)
        if not ok:
            raise RecordNotFoundError(f"Supplier {supplier_id} not found or was not deleted.")
        logger.info("Supplier %s restored by user %s.", supplier_id, current_user_id)
        row = self._model.get_by_id(supplier_id)
        return SupplierDTO.from_row(row)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) without a hard
    psycopg2 import dependency at module scope, so this helper stays reusable
    even in unit tests that stub the model layer entirely."""
    pgcode = getattr(exc, "pgcode", None)
    return pgcode == "23505"
