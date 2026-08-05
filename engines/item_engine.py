"""
engines/item_engine.py

Item Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - decides defaults (Purchase Rate/Sale Rate/MRP/Minimum Stock = 0,
      Status = Active, Tax Mode = 'country_default')
    - generates Item Codes
    - orchestrates validation (utils/item_validator.py) before touching
      the database (models/item_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - resolves an item's EFFECTIVE tax (resolve_item_tax) per the
      MASTER_BLUEPRINT_ItemMaster_TaxAndDropdowns.md redesign
    - orchestrates Opening/Purchase batch entries (item_batch) and their
      contribution to total stock
    - enforces soft-delete-only semantics on `item`

ZERO-QTY ITEM CREATION IS VALID (confirmed decision): creating an item
with no batches at all is a normal, supported case -- e.g. a brand-new
item added to the Master before its first Purchase entry arrives. This
Engine never requires at least one batch to exist.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.item_model import ITEM_COLUMNS, ItemBatchModel, ItemModel, ItemSearchFilters
from models.stock_transaction_model import StockTransactionModel
from utils.item_validator import ItemValidator, validate_batch_entry

logger = logging.getLogger(__name__)

DEFAULT_ITEM_CODE_PREFIX = "ITM-"
DEFAULT_ITEM_CODE_PADDING = 4  # ITM-0001

# Type alias for the injected country-tax lookup: given a country name,
# returns (vat_percent, custom_percent). Must never raise -- return (0, 0)
# for an unconfigured/unknown/missing country, per the blueprint.
CountryTaxLookupFn = Callable[[str], tuple[float, float]]

# Type alias for the injected Manufacturer lookup: given a manufacturer_id,
# returns a dict with at least a "country" key, or None if not found /
# not selected. Manufacturer has its own dedicated module -- this Engine
# never queries its table directly.
ManufacturerLookupFn = Callable[[Optional[int]], Optional[dict]]


def _load_date_engine():
    try:
        from engines.date_engine import ad_to_bs, DateEngineError
        return ad_to_bs, DateEngineError
    except ImportError:
        logger.warning("engines.date_engine not importable; created_at_bs/updated_at_bs will be left blank.")
        return None, None


def _load_settings_engine():
    """Same lazy-import pattern as engines/manufacturer_engine.py's
    _load_settings_engine() -- settings_engine exposes a module-level
    get_setting(key, default), not a class."""
    try:
        from engines import settings_engine
        return settings_engine
    except ImportError:
        logger.warning("engines.settings_engine not importable; ItemEngine will use the built-in default for item.code_prefix.")
        return None


def _default_country_tax_lookup(_country: str) -> tuple[float, float]:
    """
    Fallback used only if no real lookup is injected yet (Country Tax
    Settings module not wired in). Never raises -- always (0, 0), matching
    the blueprint's "unconfigured country -> (0, 0)" rule.
    """
    return 0.0, 0.0


def _default_manufacturer_lookup(_manufacturer_id: Optional[int]) -> Optional[dict]:
    """Fallback used only if the Manufacturer module isn't wired in yet."""
    return None


@dataclass
class ItemDTO:
    """Read-facing representation returned by the Engine to callers."""
    item_id: int
    item_code: str
    item_name: str
    category_id: Optional[int]
    sub_category_id: Optional[int]
    item_group_id: Optional[int]
    manufacturer_id: Optional[int]
    generic_id: Optional[int]
    unit_id: int
    purchase_unit_id: Optional[int]
    purchase_rate: float
    sale_rate: float
    mrp: float
    minimum_stock: float
    tax_mode: str
    item_vat_checked: bool
    item_vat_percent: Optional[float]
    item_custom_checked: bool
    item_custom_percent: Optional[float]
    status: str
    remarks: Optional[str]
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
    total_stock: float = 0.0
    nearest_batch_no: Optional[str] = None
    nearest_expiry_display: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "ItemDTO":
        known = {
            k: row.get(k) for k in cls.__dataclass_fields__.keys()
            if k not in ("total_stock", "nearest_batch_no", "nearest_expiry_display")
        }
        known["total_stock"] = float(row.get("total_stock", 0) or 0)
        known["nearest_batch_no"] = row.get("nearest_batch_no")
        known["nearest_expiry_display"] = row.get("nearest_expiry_display")
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ItemBatchDTO:
    item_batch_id: int
    item_id: int
    batch_no: str
    expiry_year: int
    expiry_month: int
    expiry_display: str
    batch_qty: float
    batch_purchase_rate: float
    remarks: Optional[str]
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "ItemBatchDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


class ItemEngine:
    """Business-rule orchestration for Item Master."""

    def __init__(
        self,
        model: Optional[ItemModel] = None,
        batch_model: Optional[ItemBatchModel] = None,
        stock_transaction_model: Optional[StockTransactionModel] = None,
        country_tax_lookup_fn: Optional[CountryTaxLookupFn] = None,
        manufacturer_lookup_fn: Optional[ManufacturerLookupFn] = None,
    ) -> None:
        self._model = model or ItemModel()
        self._batch_model = batch_model or ItemBatchModel()
        self._stock_transaction_model = stock_transaction_model or StockTransactionModel()
        self._country_tax_lookup_fn = country_tax_lookup_fn or _default_country_tax_lookup
        self._manufacturer_lookup_fn = manufacturer_lookup_fn or _default_manufacturer_lookup
        self._validator = ItemValidator(
            name_exists_fn=self._model.exists_by_name,
            code_exists_fn=self._model.exists_by_code,
        )
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

    def _code_prefix(self) -> str:
        """Same pattern as engines/manufacturer_engine.py's _code_prefix()."""
        if self._settings_engine is not None:
            try:
                return self._settings_engine.get_setting("item.code_prefix", DEFAULT_ITEM_CODE_PREFIX)
            except Exception:  # noqa: BLE001 - settings engine must never break item creation
                logger.exception("Failed to read item.code_prefix setting; using default.")
        return DEFAULT_ITEM_CODE_PREFIX

    def generate_item_code(self) -> str:
        """Generates the next sequential item code, e.g. ITM-0001, ITM-0002.
        Prefix is Settings-driven (falls back to 'ITM-')."""
        prefix = self._code_prefix()
        last_seq = self._model.get_last_code_sequence(prefix)
        next_seq = last_seq + 1
        return f"{prefix}{str(next_seq).zfill(DEFAULT_ITEM_CODE_PADDING)}"

    def _clean_payload(self, payload: dict) -> dict:
        """Applies default values and trims strings. Never touches uniqueness/DB."""
        data = {k: payload.get(k) for k in ITEM_COLUMNS}
        data["item_name"] = (data.get("item_name") or "").strip()
        data["item_code"] = (data.get("item_code") or "").strip()
        data["remarks"] = (data.get("remarks") or "").strip() or None

        data["purchase_rate"] = data.get("purchase_rate") or 0
        data["sale_rate"] = data.get("sale_rate") or 0
        data["mrp"] = data.get("mrp") or 0
        data["minimum_stock"] = data.get("minimum_stock") or 0
        data["status"] = data.get("status") or "Active"
        data["tax_mode"] = data.get("tax_mode") or "country_default"
        data["item_vat_checked"] = bool(data.get("item_vat_checked"))
        data["item_custom_checked"] = bool(data.get("item_custom_checked"))

        # Under country_default mode, the four individual-tax columns are
        # inert -- clear them on save so a mode switch never leaves stale
        # individual values lying around invisibly.
        if data["tax_mode"] != "individual":
            data["item_vat_checked"] = False
            data["item_vat_percent"] = None
            data["item_custom_checked"] = False
            data["item_custom_percent"] = None
        else:
            if not data["item_vat_checked"]:
                data["item_vat_percent"] = None
            if not data["item_custom_checked"]:
                data["item_custom_percent"] = None

        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_item(self, payload: dict, current_user_id: int) -> ItemDTO:
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        item_code = data["item_code"]
        if item_code:
            code_check = self._validator.validate_item_code_unique(item_code)
            if not code_check.is_valid:
                raise ValidationError(code_check.errors)
        else:
            item_code = self.generate_item_code()
            data["item_code"] = item_code

        insert_data = dict(data)
        insert_data["created_by"] = current_user_id
        insert_data["created_at_ad"] = self._now_ad()
        insert_data["created_at_bs"] = self._now_bs()

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Item Name or Code already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting item.")
            raise

        row = self._model.get_by_id(new_id)
        row["total_stock"] = 0.0  # brand-new item, zero batches -- valid, confirmed design
        return ItemDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_item(self, item_id: int, payload: dict, current_user_id: int) -> ItemDTO:
        existing = self._model.get_by_id(item_id)
        if existing is None:
            raise RecordNotFoundError(f"Item {item_id} not found or has been deleted.")

        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(item_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        update_data = dict(data)
        update_data["updated_by"] = current_user_id
        update_data["updated_at_ad"] = self._now_ad()
        update_data["updated_at_bs"] = self._now_bs()

        try:
            updated = self._model.update(item_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Item Name already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error updating item %s.", item_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Item {item_id} not found or has been deleted.")

        row = self._model.get_by_id(item_id)
        row["total_stock"] = self._model.get_total_stock(item_id)
        return ItemDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_item(self, item_id: int, include_deleted: bool = False) -> ItemDTO:
        row = self._model.get_by_id(item_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Item {item_id} not found.")
        row["total_stock"] = self._model.get_total_stock(item_id)
        return ItemDTO.from_row(row)

    def search_items(
        self,
        search_text: Optional[str] = None,
        category_id: Optional[int] = None,
        manufacturer_id: Optional[int] = None,
        item_group_id: Optional[int] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ItemDTO], int]:
        filters = ItemSearchFilters(
            search_text=search_text, category_id=category_id, manufacturer_id=manufacturer_id,
            item_group_id=item_group_id, status=status, include_deleted=include_deleted,
            page=page, page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [ItemDTO.from_row(r) for r in rows], total_count

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECKS (for on-blur checks from the Screen)
    # ------------------------------------------------------------------ #
    def is_name_taken(self, item_name: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_name(item_name, exclude_id)

    def is_code_taken(self, item_code: str, exclude_id: Optional[int] = None) -> bool:
        return self._model.exists_by_code(item_code, exclude_id)

    # ------------------------------------------------------------------ #
    # TAX RESOLUTION (per MASTER_BLUEPRINT_ItemMaster_TaxAndDropdowns.md)
    # ------------------------------------------------------------------ #
    def resolve_item_tax(self, item_id: int) -> tuple[float, float]:
        """
        Returns the item's EFFECTIVE (vat_percent, custom_percent) right
        now. LIVE, not frozen: for a country_default item, this always
        reflects the Country Tax Settings' CURRENT values -- editing that
        setting later retroactively changes what this returns for every
        item in that mode, old and new. Never raises; degrades to (0, 0)
        for any unresolved input, matching the blueprint's rule.
        """
        row = self._model.get_by_id(item_id)
        if row is None:
            return 0.0, 0.0
        return self._resolve_tax_for_row(row)

    def _resolve_tax_for_row(self, item_row: dict) -> tuple[float, float]:
        tax_mode = item_row.get("tax_mode") or "country_default"

        if tax_mode == "individual":
            vat = item_row.get("item_vat_percent") if item_row.get("item_vat_checked") else 0
            custom = item_row.get("item_custom_percent") if item_row.get("item_custom_checked") else 0
            return float(vat or 0), float(custom or 0)

        # country_default mode
        manufacturer_id = item_row.get("manufacturer_id")
        manufacturer_row = self._manufacturer_lookup_fn(manufacturer_id) if manufacturer_id else None
        country = (manufacturer_row or {}).get("country")
        if not country:
            return 0.0, 0.0

        try:
            vat, custom = self._country_tax_lookup_fn(country)
            return float(vat or 0), float(custom or 0)
        except Exception:  # noqa: BLE001 -- tax lookup must never break item resolution
            logger.exception("country_tax_lookup_fn failed for country '%s'; defaulting to (0, 0).", country)
            return 0.0, 0.0

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_item(self, item_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(item_id)
        if existing is None:
            raise RecordNotFoundError(f"Item {item_id} not found or already deleted.")
        ok = self._model.soft_delete(item_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Item {item_id} not found or already deleted.")
        logger.info("Item %s soft-deleted by user %s.", item_id, current_user_id)

    def restore_item(self, item_id: int, current_user_id: int) -> ItemDTO:
        ok = self._model.restore(item_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Item {item_id} not found or was not deleted.")
        logger.info("Item %s restored by user %s.", item_id, current_user_id)
        row = self._model.get_by_id(item_id)
        row["total_stock"] = self._model.get_total_stock(item_id)
        return ItemDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # BATCH ORCHESTRATION (Opening Stock today; Purchase module will call
    # add_batch() the same way once it is built -- same "never mutate an
    # old batch, always insert a new one" rule holds for both callers)
    # ------------------------------------------------------------------ #
    def add_batch(
        self,
        item_id: int,
        batch_payload: dict,
        current_user_id: int,
        transaction_type: str = "OPENING",
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> ItemBatchDTO:
        """
        Creates a brand-new batch for an item AND logs its starting
        quantity to stock_ledger, atomically (see
        ItemBatchModel.insert_with_ledger()). `transaction_type` defaults
        to 'OPENING' (today's only real caller -- the Item Form's Opening
        Stock fields and the "Add Batch" button); a future Purchase module
        adding a brand-new lot would call this the same way with
        transaction_type='PURCHASE' and reference_type='purchase',
        reference_id=<purchase_id>.
        """
        item_row = self._model.get_by_id(item_id)
        if item_row is None:
            raise RecordNotFoundError(f"Item {item_id} not found or has been deleted.")

        batch_no = (batch_payload.get("batch_no") or "").strip()
        expiry_year = batch_payload.get("expiry_year")
        expiry_month = batch_payload.get("expiry_month")
        batch_qty = batch_payload.get("batch_qty", 0)
        batch_purchase_rate = batch_payload.get("batch_purchase_rate", 0)
        remarks = (batch_payload.get("remarks") or "").strip() or None

        validation = validate_batch_entry(batch_no, expiry_year, expiry_month, batch_qty, batch_purchase_rate)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        if self._batch_model.exists_batch_no(item_id, batch_no):
            raise DuplicateRecordError(f"Batch No. '{batch_no}' already exists for this item.")

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "item_id": item_id,
            "batch_no": batch_no,
            "expiry_year": int(expiry_year),
            "expiry_month": int(expiry_month),
            "batch_qty": float(batch_qty),
            "batch_purchase_rate": float(batch_purchase_rate),
            "remarks": remarks,
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        # A new batch has no prior balance -- its starting qty IS both the
        # movement amount and the resulting balance.
        ledger_data = {
            "item_id": item_id,
            "transaction_type": transaction_type,
            "quantity_change": float(batch_qty),
            "balance_after": float(batch_qty),
            "reference_type": reference_type,
            "reference_id": reference_id,
            "remarks": remarks,
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._batch_model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError(f"Batch No. '{batch_no}' already exists for this item (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting batch for item %s.", item_id)
            raise

        # Every batch entry (Opening Stock today; Purchase will call add_batch()
        # the same way once built) is also recorded in the append-only stock
        # ledger, so stock movement history exists from day one -- never rely
        # on item_batch.batch_qty alone as "why did the stock become this".
        try:
            self._stock_transaction_model.insert({
                "item_id": item_id,
                "item_batch_id": new_id,
                "transaction_type": "Opening",
                "quantity_in": float(batch_qty),
                "quantity_out": 0,
                "reference_table": "item_batch",
                "reference_id": new_id,
                "remarks": "Opening stock entry via Item Master.",
                "created_by": current_user_id,
                "created_at_ad": self._now_ad(),
                "created_at_bs": self._now_bs(),
            })
        except Exception:  # noqa: BLE001 -- ledger failure must never roll back a successful batch save
            logger.exception("Failed to write stock_transaction ledger entry for batch %s (item %s). Batch itself was saved successfully.", new_id, item_id)

        rows = self._batch_model.get_by_item(item_id)
        row = next(r for r in rows if r["item_batch_id"] == new_id)
        return ItemBatchDTO.from_row(row)

    def post_stock_movement(
        self,
        item_batch_id: int,
        transaction_type: str,
        quantity_change: float,
        current_user_id: int,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        remarks: Optional[str] = None,
    ) -> ItemBatchDTO:
        """
        FOR FUTURE PURCHASE/SALE MODULES: adjusts an EXISTING batch's
        balance and logs the movement to stock_ledger, atomically.
        Positive quantity_change = stock IN (e.g. Purchase adding to an
        existing lot, a Sale Return); negative = stock OUT (e.g. a Sale,
        a Purchase Return, a downward Adjustment).

        Not called anywhere in this repo today -- built now so those
        future modules have ONE safe, shared entry point for changing an
        existing batch's quantity, instead of each writing its own
        item_batch UPDATE statement (which is exactly how batch_qty and
        stock_ledger would eventually drift apart).
        """
        valid_types = ("PURCHASE", "SALE", "SALE_RETURN", "PURCHASE_RETURN", "ADJUSTMENT")
        if transaction_type not in valid_types:
            raise ValidationError([f"transaction_type must be one of {valid_types}."])

        batch_row = self._batch_model.get_by_id(item_batch_id)
        if batch_row is None:
            raise RecordNotFoundError(f"Batch {item_batch_id} not found.")

        prospective_balance = float(batch_row["batch_qty"]) + quantity_change
        if prospective_balance < 0:
            raise ValidationError([
                f"This movement would take batch '{batch_row['batch_no']}' below zero "
                f"(current: {batch_row['batch_qty']}, change: {quantity_change})."
            ])

        ledger_data = {
            "item_id": batch_row["item_id"],
            "transaction_type": transaction_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "remarks": remarks,
            "created_by": current_user_id,
            "created_at_ad": self._now_ad(),
            "created_at_bs": self._now_bs(),
        }

        self._batch_model.update_qty_with_ledger(item_batch_id, quantity_change, ledger_data)

        updated_row = self._batch_model.get_by_id(item_batch_id)
        return ItemBatchDTO.from_row(updated_row)

    def get_stock_ledger(self, item_id: int) -> list[dict]:
        """Raw ledger rows for an item, newest first -- for a future
        "Stock History" view. Returned as plain dicts (no DTO wrapper
        yet -- add one if/when a Screen needs to display this)."""
        from models.item_model import StockLedgerModel
        return StockLedgerModel().get_by_item(item_id)

    def get_batches(self, item_id: int) -> list[ItemBatchDTO]:
        rows = self._batch_model.get_by_item(item_id)
        return [ItemBatchDTO.from_row(r) for r in rows]

    def get_total_stock(self, item_id: int) -> float:
        return self._model.get_total_stock(item_id)


def _is_unique_violation(exc: Exception) -> bool:
    """Detects a PostgreSQL unique-violation (SQLSTATE 23505) -- same
    helper already used in engines/supplier_engine.py."""
    return getattr(exc, "pgcode", None) == "23505"


__all__ = ["ItemEngine", "ItemDTO", "ItemBatchDTO"]
