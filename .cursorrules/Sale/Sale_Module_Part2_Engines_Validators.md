# Sale Module — Part 2: Validators + Engines Layer

**Project:** Medical ERP V2
**Layer:** Business Logic (Validators + Engines — "No SQL. Business logic lives ONLY here.")
**Depends on Part 1:** `sale_invoice`/`sale_invoice_item` tables, `item_free_scheme` table, `models/sale_invoice_model.py`, `models/item_free_scheme_model.py`, extensions to `customer_model.py`/`item_model.py`.
**Reuses (already built, unchanged):**
- `engines/item_engine.py` — `ItemEngine.get_batches()`, `.post_stock_movement()`, `.resolve_item_tax()`, `.get_item()`
- `engines/customer_engine.py` — customer lookups
- `engines/date_engine.py` — `ad_to_bs()`, `DateEngineError`
- `engines/settings_engine.py` — `get_setting()`
- `engines/exceptions.py` — `ValidationError`, `RecordNotFoundError`, `DuplicateRecordError`, `EngineError`

---

## 1. `engines/sale_validator.py`

Two validator classes in one file — mirrors how `purchase_validator.py` held both `PurchaseValidator` + `PurchaseOrderValidator` together. Here: `SaleInvoiceValidator` + `ItemFreeSchemeValidator`.

```python
"""
engines/sale_validator.py

Sale Invoice + Item Free Scheme Validators - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- never touches the database directly except via
injected callbacks from the Engine (which owns the Model). Mirrors
engines/purchase_validator.py's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REMARKS = 1000
VALID_ENTRY_MODES = ("free_qty", "net_rate")
VALID_SALE_MODES = ("Retail", "Wholesale")
VALID_PAYMENT_TYPES = ("Cash", "Bank", "eSewa", "Khalti", "IPS")
VALID_INVOICE_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


# ====================================================================== #
# SALE INVOICE VALIDATOR
# ====================================================================== #
class SaleInvoiceValidator:
    """
    Stateless validation rules for Sale Invoice header + lines. Does NOT
    compute anything (no rate math, no CC, no stock checks) -- it only
    checks that what the Engine is about to save is structurally sound.
    All computation lives in SaleEngine itself, same separation already
    used between PurchaseValidator and PurchaseEngine.
    """

    def __init__(self, number_exists_fn: Callable[[str, Optional[int]], bool]) -> None:
        self._number_exists_fn = number_exists_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("customer_id"):
            result.add("Customer is mandatory.")

        if not data.get("invoice_date_bs"):
            result.add("Invoice Date (BS) is mandatory.")

        sale_mode = data.get("sale_mode", "Retail")
        if sale_mode not in VALID_SALE_MODES:
            result.add("Sale Mode must be either 'Retail' or 'Wholesale'.")

        payment_type = data.get("payment_type")
        if payment_type is not None and payment_type not in VALID_PAYMENT_TYPES:
            result.add(f"Payment Type must be one of {VALID_PAYMENT_TYPES}.")

        amount_paid_now = data.get("amount_paid_now", 0) or 0
        try:
            if float(amount_paid_now) < 0:
                result.add("Amount Paid Now cannot be negative.")
        except (TypeError, ValueError):
            result.add("Amount Paid Now must be a valid number.")

        remarks = data.get("remarks") or ""
        if len(remarks) > MAX_LEN_REMARKS:
            result.add(f"Remarks must not exceed {MAX_LEN_REMARKS} characters.")

        status = data.get("status", "Posted")
        if status not in VALID_INVOICE_STATUSES:
            result.add("Status must be one of Draft, Posted, Cancelled.")

        return result

    def validate_invoice_number_unique(self, invoice_number: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        number = (invoice_number or "").strip()
        if not number:
            result.add("Invoice Number is required.")
        elif self._number_exists_fn(number, exclude_id):
            result.add(f"Invoice Number '{number}' already exists.")
        return result

    def validate_lines(self, line_rows: list[dict]) -> ValidationResult:
        """
        Validates the whole line-item list at once (so "at least one line"
        can be checked, not just per-row shape). Called by the Engine
        BEFORE any rate/CC/stock computation runs -- a structurally bad
        line list is rejected early, never partially computed.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("At least one item line is required.")
            return result

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"

            if not row.get("item_id"):
                result.add(f"{prefix}: Item is required.")

            entry_mode = row.get("entry_mode", "free_qty")
            if entry_mode not in VALID_ENTRY_MODES:
                result.add(f"{prefix}: Entry mode must be 'free_qty' or 'net_rate'.")

            qty = row.get("qty")
            try:
                if qty is None or float(qty) <= 0:
                    result.add(f"{prefix}: Qty must be greater than zero.")
            except (TypeError, ValueError):
                result.add(f"{prefix}: Qty must be a valid number.")

            free_qty = row.get("free_qty", 0) or 0
            try:
                if float(free_qty) < 0:
                    result.add(f"{prefix}: Free Qty cannot be negative.")
            except (TypeError, ValueError):
                result.add(f"{prefix}: Free Qty must be a valid number.")

            rate = row.get("rate")
            try:
                if rate is None or float(rate) < 0:
                    result.add(f"{prefix}: Rate cannot be negative.")
            except (TypeError, ValueError):
                result.add(f"{prefix}: Rate must be a valid number.")

            discount_percent = row.get("discount_percent", 0) or 0
            try:
                if not (0 <= float(discount_percent) <= 100):
                    result.add(f"{prefix}: Discount % must be between 0 and 100.")
            except (TypeError, ValueError):
                result.add(f"{prefix}: Discount % must be a valid number.")

        return result


# ====================================================================== #
# ITEM FREE SCHEME VALIDATOR
# ====================================================================== #
class ItemFreeSchemeValidator:
    """Stateless validation rules for the Item Free Scheme master. Mirrors
    validators/supplier_manufacturer_discount_validator.py's shape."""

    def __init__(self, active_scheme_exists_fn: Callable[[int, Optional[int]], bool]) -> None:
        self._active_scheme_exists_fn = active_scheme_exists_fn

    def validate_for_create(self, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_uniqueness(data.get("item_id"), result, exclude_id=None)
        return result

    def validate_for_update(self, item_free_scheme_id: int, data: dict) -> ValidationResult:
        result = ValidationResult()
        self._validate_common_fields(data, result)
        self._validate_uniqueness(data.get("item_id"), result, exclude_id=item_free_scheme_id)
        return result

    def _validate_common_fields(self, data: dict, result: ValidationResult) -> None:
        if not data.get("item_id"):
            result.add("Item is mandatory.")

        scheme_qty = data.get("scheme_qty")
        try:
            if scheme_qty is None or float(scheme_qty) <= 0:
                result.add("Buy Qty must be greater than zero.")
        except (TypeError, ValueError):
            result.add("Buy Qty must be a valid number.")

        scheme_free = data.get("scheme_free")
        try:
            if scheme_free is None or float(scheme_free) <= 0:
                result.add("Free Qty must be greater than zero.")
        except (TypeError, ValueError):
            result.add("Free Qty must be a valid number.")

        remarks = data.get("remarks") or ""
        if len(remarks) > MAX_LEN_REMARKS:
            result.add(f"Remarks must not exceed {MAX_LEN_REMARKS} characters.")

    def _validate_uniqueness(self, item_id, result: ValidationResult, exclude_id: Optional[int]) -> None:
        """Only ONE active scheme per item at a time -- matches the
        partial unique index in Part 1's schema. Editing an existing
        scheme's ratio is fine; creating a second active one is not."""
        if not item_id:
            return  # mandatory-check already raised above
        if self._active_scheme_exists_fn(item_id, exclude_id):
            result.add("This item already has an active Free Scheme. Edit the existing one instead of creating a new one.")


__all__ = ["SaleInvoiceValidator", "ItemFreeSchemeValidator", "ValidationResult"]
```

---

## 2. `engines/item_free_scheme_engine.py`

Small, standalone Engine (same size-class as `engines/supplier_manufacturer_discount_engine.py`) — owns the master table, and exposes the ONE lookup method `SaleEngine` calls per line.

```python
"""
engines/item_free_scheme_engine.py

Item Free Scheme Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - orchestrates validation (ItemFreeSchemeValidator) before touching
      the database (models/item_free_scheme_model.py)
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete + "one active scheme per item" semantics
    - resolves the effective free-scheme ratio for an item via
      get_scheme_for_item() -- the ONLY method SaleEngine should call
      for this lookup, mirroring
      SupplierManufacturerDiscountEngine.get_discount()'s "never raises,
      degrades to None/0" contract.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_validator import ItemFreeSchemeValidator
from models.item_free_scheme_model import ItemFreeSchemeModel

logger = logging.getLogger(__name__)


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; ItemFreeSchemeEngine falls back to AD-only stamps.")
        return None


@dataclass
class ItemFreeSchemeDTO:
    """Read-facing representation returned by the Engine to callers."""
    item_free_scheme_id: int
    item_id: int
    scheme_qty: float
    scheme_free: float
    is_active: bool
    remarks: Optional[str]
    item_name: Optional[str] = None      # only populated by search() (joined)
    item_code: Optional[str] = None      # only populated by search() (joined)
    is_deleted: bool = False
    created_by: Optional[int] = None
    created_at_ad: Any = None
    created_at_bs: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at_ad: Any = None
    updated_at_bs: Optional[str] = None
    deleted_by: Optional[int] = None
    deleted_at_ad: Any = None
    deleted_at_bs: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "ItemFreeSchemeDTO":
        known = {k: row.get(k) for k in cls.__dataclass_fields__.keys()}
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


class ItemFreeSchemeEngine:
    """Business-rule orchestration for the Item Free Scheme master."""

    def __init__(self, model: Optional[ItemFreeSchemeModel] = None, date_engine: Optional[Any] = None) -> None:
        self._model = model or ItemFreeSchemeModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = ItemFreeSchemeValidator(active_scheme_exists_fn=self._model.exists_active_for_item)

    # ------------------------------------------------------------------ #
    def _now_ad(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_bs(self) -> Optional[str]:
        if self._date_engine is None:
            return None
        try:
            return self._date_engine.ad_to_bs(date.today())
        except self._date_engine.DateEngineError:
            logger.warning("ad_to_bs() could not resolve today's date; BS audit field left blank.")
            return None

    def _clean_payload(self, payload: dict) -> dict:
        data = dict(payload)
        data["scheme_qty"] = data.get("scheme_qty")
        data["scheme_free"] = data.get("scheme_free")
        data["is_active"] = data.get("is_active", True)
        data["remarks"] = (data.get("remarks") or "").strip() or None
        return data

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_scheme(self, payload: dict, current_user_id: int) -> ItemFreeSchemeDTO:
        data = self._clean_payload(payload)

        validation = self._validator.validate_for_create(data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        now_ad = self._now_ad()
        now_bs = self._now_bs()

        insert_data = {
            "item_id": data["item_id"],
            "scheme_qty": data["scheme_qty"],
            "scheme_free": data["scheme_free"],
            "is_active": data["is_active"],
            "remarks": data["remarks"],
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert(insert_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("This item already has an active Free Scheme (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting item free scheme.")
            raise

        row = self._model.get_by_id(new_id)
        return ItemFreeSchemeDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # UPDATE
    # ------------------------------------------------------------------ #
    def update_scheme(self, item_free_scheme_id: int, payload: dict, current_user_id: int) -> ItemFreeSchemeDTO:
        existing = self._model.get_by_id(item_free_scheme_id)
        if existing is None:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found or has been deleted.")

        data = self._clean_payload(payload)
        validation = self._validator.validate_for_update(item_free_scheme_id, data)
        if not validation.is_valid:
            raise ValidationError(validation.errors)

        update_data = {
            "scheme_qty": data["scheme_qty"],
            "scheme_free": data["scheme_free"],
            "is_active": data["is_active"],
            "remarks": data["remarks"],
            "updated_by": current_user_id,
            "updated_at_ad": self._now_ad(),
            "updated_at_bs": self._now_bs(),
        }

        try:
            updated = self._model.update(item_free_scheme_id, update_data)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("This item already has an active Free Scheme (concurrent save detected).") from exc
            logger.exception("Unexpected error updating item free scheme %s.", item_free_scheme_id)
            raise

        if not updated:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found or has been deleted.")

        row = self._model.get_by_id(item_free_scheme_id)
        return ItemFreeSchemeDTO.from_row(row)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_scheme(self, item_free_scheme_id: int, include_deleted: bool = False) -> ItemFreeSchemeDTO:
        row = self._model.get_by_id(item_free_scheme_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found.")
        return ItemFreeSchemeDTO.from_row(row)

    def search_schemes(self, search_text: Optional[str] = None, include_deleted: bool = False) -> list[ItemFreeSchemeDTO]:
        rows = self._model.search(search_text=search_text, include_deleted=include_deleted)
        return [ItemFreeSchemeDTO.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # SCHEME RESOLUTION -- the ONLY method SaleEngine should call.
    # NEVER raises: no active scheme resolves to None, and SaleEngine
    # treats None as "no free scheme configured for this item" (free_qty
    # stays 0, net_rate mode is unavailable for this line).
    # ------------------------------------------------------------------ #
    def get_scheme_for_item(self, item_id: int) -> Optional[tuple[float, float]]:
        """
        Returns (scheme_qty, scheme_free) for the item's currently active
        Free Scheme, or None if no active scheme exists. Never raises --
        any lookup error degrades to None so a missing/broken scheme
        configuration can never block a Sale Invoice line from saving.
        """
        try:
            row = self._model.get_active_by_item(item_id)
        except Exception:  # noqa: BLE001 -- must never break a Sale Invoice line
            logger.exception("get_scheme_for_item: failed to resolve scheme for item_id=%s; defaulting to None.", item_id)
            return None

        if row is None:
            return None

        try:
            return float(row["scheme_qty"]), float(row["scheme_free"])
        except (TypeError, ValueError, KeyError):
            logger.warning("get_scheme_for_item: malformed scheme row for item_id=%s; defaulting to None.", item_id)
            return None

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def delete_scheme(self, item_free_scheme_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(item_free_scheme_id)
        if existing is None:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found or already deleted.")
        ok = self._model.soft_delete(item_free_scheme_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found or already deleted.")
        logger.info("Item Free Scheme %s soft-deleted by user %s.", item_free_scheme_id, current_user_id)

    def restore_scheme(self, item_free_scheme_id: int, current_user_id: int) -> ItemFreeSchemeDTO:
        ok = self._model.restore(item_free_scheme_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Free Scheme {item_free_scheme_id} not found or was not deleted.")
        logger.info("Item Free Scheme %s restored by user %s.", item_free_scheme_id, current_user_id)
        row = self._model.get_by_id(item_free_scheme_id)
        return ItemFreeSchemeDTO.from_row(row)


def _is_unique_violation(exc: Exception) -> bool:
    return getattr(exc, "pgcode", None) == "23505"


__all__ = ["ItemFreeSchemeEngine", "ItemFreeSchemeDTO"]
```

---

## 3. `engines/sale_engine.py` — The Core Engine

This is where the confirmed business rules (free-scheme resolution, Net Rate formula, CC-on-Purchase-Rate, minimum-1 auto-fill, half-free toggle, stock deduction) all live.

```python
"""
engines/sale_engine.py

Sale Invoice Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - decides defaults (Sale Mode from the Free-column Setting, Status,
      Payment Type)
    - generates Invoice Numbers
    - resolves the nearest-expiry batch per line (read-only in the UI,
      per confirmed scope -- ItemEngine.get_batches() is already
      expiry-ascending, reused as-is)
    - resolves each line's Free Scheme via ItemFreeSchemeEngine and
      computes free_qty (Free Qty mode) or the blended Net Rate
      (Net Rate mode), per Bijay's confirmed formulas
    - computes CC on Free Goods (Wholesale mode only, on Purchase Rate,
      never MRP) via country_tax_engine/manufacturer_engine, exactly
      mirroring the Purchase-side CC concept
    - orchestrates validation (SaleInvoiceValidator) before touching the
      database (models/sale_invoice_model.py)
    - posts stock deduction through the EXISTING
      ItemEngine.post_stock_movement() -- no new stock-writing code
    - stamps BS-first audit fields via the shared Date Engine
    - enforces soft-delete-only (Cancel) semantics -- Sale Invoices are
      add-only, corrections go through Sale Return (Phase-3), same
      accounting-best-practice rule Purchase Invoices already follow
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_validator import SaleInvoiceValidator
from models.sale_invoice_model import SaleInvoiceModel, SaleInvoiceSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_INVOICE_PREFIX = "SINV-"
DEFAULT_INVOICE_PADDING = 4  # SINV-0001

# Type aliases for injected lookups -- same "never raises, degrade to a
# safe default" contract already used throughout engines/item_engine.py.
CountryTaxLookupFn = Callable[[str], tuple[float, float]]           # -> (vat_percent, custom_percent)
ManufacturerLookupFn = Callable[[Optional[int]], Optional[dict]]     # -> {"country": ...} or None


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; SaleEngine falls back to AD-only stamps.")
        return None


def _load_settings_engine():
    try:
        from engines import settings_engine
        return settings_engine
    except ImportError:
        logger.warning("engines.settings_engine not importable; SaleEngine uses built-in defaults for all sale.* settings.")
        return None


@dataclass
class SaleInvoiceLineDTO:
    """Read-facing representation of one posted Sale Invoice line."""
    sale_invoice_item_id: int
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    entry_mode: str
    qty: float
    free_qty: float
    current_rate: float
    rate: float
    discount_percent: float
    discount_amount: float
    cc_percent: float
    cc_amount: float
    tax_percent: float
    tax_amount: float
    amount: float
    mrp: float
    remarks: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "SaleInvoiceLineDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


@dataclass
class SaleInvoiceDTO:
    """Read-facing representation returned by the Engine to callers."""
    sale_invoice_id: int
    invoice_number: str
    customer_id: int
    area_id: Optional[int]
    price_level_id: Optional[int]
    invoice_date_ad: Any
    invoice_date_bs: str
    sale_mode: str
    total_qty: float
    total_free_qty: float
    total_gross_amount: float
    total_discount_amount: float
    total_cc_amount: float
    total_tax_amount: float
    round_off: float
    grand_total: float
    payment_type: Optional[str]
    amount_paid_now: float
    status: str
    remarks: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    customer_name: Optional[str] = None    # only populated by search() (joined)
    area_name: Optional[str] = None        # only populated by search() (joined)
    lines: list[SaleInvoiceLineDTO] = None

    @classmethod
    def from_row(cls, row: dict, lines: Optional[list[SaleInvoiceLineDTO]] = None) -> "SaleInvoiceDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "lines"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, lines=lines or [])

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


class SaleEngine:
    """Business-rule orchestration for the Sale Invoice module."""

    def __init__(
        self,
        model: Optional[SaleInvoiceModel] = None,
        date_engine: Optional[Any] = None,
        settings_engine: Optional[Any] = None,
        item_engine=None,                      # engines.item_engine.ItemEngine -- REQUIRED, injected (shared instance)
        item_free_scheme_engine=None,          # engines.item_free_scheme_engine.ItemFreeSchemeEngine -- REQUIRED, injected
        country_tax_lookup_fn: Optional[CountryTaxLookupFn] = None,
        manufacturer_lookup_fn: Optional[ManufacturerLookupFn] = None,
    ) -> None:
        if item_engine is None:
            raise ValueError("SaleEngine requires an item_engine instance (shared with the rest of the app).")
        if item_free_scheme_engine is None:
            raise ValueError("SaleEngine requires an item_free_scheme_engine instance.")

        self._model = model or SaleInvoiceModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._settings_engine = settings_engine if settings_engine is not None else _load_settings_engine()
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._country_tax_lookup_fn = country_tax_lookup_fn
        self._manufacturer_lookup_fn = manufacturer_lookup_fn
        self._validator = SaleInvoiceValidator(number_exists_fn=self._model.exists_by_number)

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
            logger.warning("ad_to_bs() could not resolve today's date; BS audit field left blank.")
            return None

    def _get_setting(self, key: str, default):
        if self._settings_engine is None:
            return default
        try:
            return self._settings_engine.get_setting(key, default)
        except Exception:  # noqa: BLE001 -- a broken settings lookup must never block a sale
            logger.exception("Failed to read setting '%s'; using default %r.", key, default)
            return default

    def _invoice_prefix(self) -> str:
        return self._get_setting("sale.invoice_prefix", DEFAULT_INVOICE_PREFIX)

    def generate_invoice_number(self) -> str:
        prefix = self._invoice_prefix()
        last_seq = self._model.get_last_number_sequence(prefix)
        next_seq = last_seq + 1
        return f"{prefix}{str(next_seq).zfill(DEFAULT_INVOICE_PADDING)}"

    def is_wholesale_mode(self) -> bool:
        """Sale Mode is derived from the SAME Setting that shows/hides the
        Free column (confirmed: 'Free column hidden = Retail, free-scheme
        never applies'). This is the single source of truth the Screen's
        column visibility and the Engine's free-scheme logic both read."""
        return bool(self._get_setting("sale.column_show_free", False))

    # ------------------------------------------------------------------ #
    # LINE COMPUTATION -- the confirmed free-scheme + Net Rate + CC rules
    # ------------------------------------------------------------------ #
    def compute_line(self, line_input: dict, is_wholesale: bool) -> dict:
        """
        Takes a raw line input (item_id, entry_mode, qty, optionally a
        user-overridden rate/free_qty) and returns a fully computed line
        dict ready for SaleInvoiceModel.insert_with_items() -- batch
        auto-picked, free_qty/rate resolved per the confirmed formulas,
        CC computed (Wholesale only), amount totalled.

        This is pure computation -- it does NOT touch the database beyond
        the read-only lookups needed (batch pick, item info, free scheme,
        tax, manufacturer/country). It does NOT deduct stock -- that
        happens once per line in create_sale_invoice(), AFTER the whole
        invoice has passed validation, so a bad line never leaves a
        partial stock deduction behind.
        """
        item_id = line_input["item_id"]
        entry_mode = line_input.get("entry_mode", "free_qty")
        qty = float(line_input["qty"])

        # ---- 1. Item + batch (read-only auto-pick, per confirmed scope) ----
        item_dto = self._item_engine.get_item(item_id)
        batch = self._pick_nearest_expiry_batch(item_id)
        if batch is None:
            raise ValidationError([f"Item '{item_dto.item_name}' has no available stock to sell."])

        current_rate = float(item_dto.sale_rate or 0)
        rate = float(line_input.get("rate") if line_input.get("rate") is not None else current_rate)
        mrp = float(item_dto.mrp or 0)

        # ---- 2. Free scheme resolution (Wholesale only) ----
        free_qty = 0.0
        if is_wholesale:
            scheme = self._item_free_scheme_engine.get_scheme_for_item(item_id)
            if scheme is not None:
                scheme_qty, scheme_free = scheme

                if entry_mode == "net_rate":
                    # Net Rate mode: qty is the BLENDED total; rate is
                    # auto-reduced unless the user already overrode it.
                    if line_input.get("rate") is None:
                        rate = self._compute_net_rate(current_rate, scheme_qty, scheme_free)
                    # free_qty stays 0 in net_rate mode -- the benefit is
                    # baked into `rate`, not shown as a separate free unit.
                else:
                    # Free Qty mode: compute free_qty from the ratio,
                    # honouring the minimum-auto-fill and half-free settings.
                    if line_input.get("free_qty") is None:
                        free_qty = self._compute_auto_free_qty(qty, scheme_qty, scheme_free)
                    else:
                        free_qty = float(line_input["free_qty"])

        # ---- 3. Discount ----
        discount_percent = float(line_input.get("discount_percent", 0) or 0)
        gross = qty * rate
        discount_amount = gross * discount_percent / 100

        # ---- 4. CC on Free Goods (Wholesale only, on PURCHASE RATE, never MRP) ----
        cc_percent = 0.0
        cc_amount = 0.0
        if is_wholesale and free_qty > 0:
            cc_percent = self._resolve_cc_percent(item_dto.manufacturer_id)
            purchase_rate = float(item_dto.purchase_rate or 0)
            cc_amount = free_qty * purchase_rate * cc_percent / 100

        # ---- 5. Tax (reuses the exact same resolver Item Master already exposes) ----
        tax_percent = 0.0
        tax_amount = 0.0
        if self._get_setting("sale.column_show_tax", False):
            vat_percent, custom_percent = self._item_engine.resolve_item_tax(item_id)
            tax_percent = vat_percent  # VAT is the sale-relevant tax component; custom_percent is a purchase-cost concept, not re-applied here
            tax_amount = gross * tax_percent / 100

        amount = gross - discount_amount

        return {
            "item_id": item_id,
            "item_batch_id": batch["item_batch_id"],
            "batch_no": batch["batch_no"],
            "expiry_month": batch["expiry_month"],
            "expiry_year": batch["expiry_year"],
            "entry_mode": entry_mode,
            "qty": qty,
            "free_qty": free_qty,
            "current_rate": current_rate,
            "rate": rate,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "cc_percent": cc_percent,
            "cc_amount": cc_amount,
            "tax_percent": tax_percent,
            "tax_amount": tax_amount,
            "amount": amount,
            "mrp": mrp,
            "remarks": (line_input.get("remarks") or "").strip() or None,
        }

    def _pick_nearest_expiry_batch(self, item_id: int) -> Optional[dict]:
        """Reuses ItemEngine.get_batches() (already expiry-ascending) rather
        than duplicating the ordering logic -- takes the first non-zero-qty
        batch. No new sorting code, per project's 'No Duplicate Logic' rule."""
        batches = self._item_engine.get_batches(item_id)
        for batch_dto in batches:
            if batch_dto.batch_qty > 0:
                return batch_dto.to_dict() if hasattr(batch_dto, "to_dict") else vars(batch_dto)
        return None

    def _compute_auto_free_qty(self, qty: float, scheme_qty: float, scheme_free: float) -> float:
        """
        Confirmed formula: free = floor(qty / scheme_qty) * scheme_free,
        UNLESS sale.allow_half_free is on, in which case the exact
        proportional (fractional) free is used instead of flooring.
        Auto-fill only happens if the result >= sale.minimum_auto_free_qty
        (default 1) -- otherwise the line gets free_qty = 0 and the user
        may set it manually.
        """
        allow_half_free = bool(self._get_setting("sale.allow_half_free", False))
        minimum_auto_free = float(self._get_setting("sale.minimum_auto_free_qty", 1))

        if allow_half_free:
            computed_free = (qty / scheme_qty) * scheme_free
        else:
            import math
            multiples = math.floor(qty / scheme_qty)
            computed_free = multiples * scheme_free

        if computed_free < minimum_auto_free:
            return 0.0
        return computed_free

    @staticmethod
    def _compute_net_rate(current_rate: float, scheme_qty: float, scheme_free: float) -> float:
        """Confirmed formula: Net Rate = Current Rate x scheme_qty / (scheme_qty + scheme_free).
        E.g. rate=100, scheme=5+1 -> Net Rate = 100 x 5/6 = 83.33."""
        denominator = scheme_qty + scheme_free
        if denominator <= 0:
            return current_rate
        return current_rate * scheme_qty / denominator

    def _resolve_cc_percent(self, manufacturer_id: Optional[int]) -> float:
        """Same manufacturer -> country -> custom_percent chain the
        Purchase side already uses (ItemEngine._resolve_tax_for_row's
        country_default path), reused here read-only. Never raises --
        degrades to 0 for any unresolved input."""
        if manufacturer_id is None or self._manufacturer_lookup_fn is None or self._country_tax_lookup_fn is None:
            return 0.0
        try:
            manufacturer_row = self._manufacturer_lookup_fn(manufacturer_id)
            country = (manufacturer_row or {}).get("country")
            if not country:
                return 0.0
            _vat_percent, custom_percent = self._country_tax_lookup_fn(country)
            return float(custom_percent or 0)
        except Exception:  # noqa: BLE001
            logger.exception("_resolve_cc_percent failed for manufacturer_id=%s; defaulting to 0.", manufacturer_id)
            return 0.0

    # ------------------------------------------------------------------ #
    # CREATE (header + lines + stock deduction, one logical operation)
    # ------------------------------------------------------------------ #
    def create_sale_invoice(self, payload: dict, current_user_id: int) -> SaleInvoiceDTO:
        """
        payload keys:
            customer_id, area_id, price_level_id, invoice_date_bs,
            payment_type, amount_paid_now, remarks,
            lines: list[{item_id, entry_mode, qty, rate?, free_qty?,
                         discount_percent?, remarks?}]

        Flow:
            1. Determine is_wholesale via the Free-column Setting.
            2. Validate the header (SaleInvoiceValidator.validate_header).
            3. Validate the raw line shapes (SaleInvoiceValidator.validate_lines)
               BEFORE any computation -- structural problems are rejected
               immediately.
            4. compute_line() for every row -- batch pick, free-scheme
               resolution, Net Rate, CC, tax, amount.
            5. Sum invoice-level totals from the computed lines.
            6. Generate invoice_number, insert header+lines in ONE
               transaction (SaleInvoiceModel.insert_with_items).
            7. Deduct stock for every line via the EXISTING
               ItemEngine.post_stock_movement() (transaction_type='SALE',
               quantity_change = -(qty + free_qty) -- both paid and free
               units physically leave stock). If any post_stock_movement
               call fails after the invoice row is already saved, the
               failure is logged and surfaced to the caller distinctly
               (invoice exists, but stock needs manual reconciliation) --
               mirrors the exact "item saved, batch failed separately"
               pattern already used in ItemFormScreen._on_save_clicked().
        """
        is_wholesale = self.is_wholesale_mode()

        header_errors = self._validator.validate_header(payload)
        if not header_errors.is_valid:
            raise ValidationError(header_errors.errors)

        raw_lines = payload.get("lines") or []
        line_errors = self._validator.validate_lines(raw_lines)
        if not line_errors.is_valid:
            raise ValidationError(line_errors.errors)

        computed_lines = [self.compute_line(line, is_wholesale) for line in raw_lines]

        total_qty = sum(l["qty"] for l in computed_lines)
        total_free_qty = sum(l["free_qty"] for l in computed_lines)
        total_gross_amount = sum(l["qty"] * l["rate"] for l in computed_lines)
        total_discount_amount = sum(l["discount_amount"] for l in computed_lines)
        total_cc_amount = sum(l["cc_amount"] for l in computed_lines)
        total_tax_amount = sum(l["tax_amount"] for l in computed_lines)
        subtotal = sum(l["amount"] for l in computed_lines) + total_cc_amount + total_tax_amount
        grand_total_raw = subtotal
        grand_total = round(grand_total_raw)
        round_off = grand_total - grand_total_raw

        invoice_number = self.generate_invoice_number()
        now_ad = self._now_ad()
        now_bs = self._now_bs()

        header_data = {
            "invoice_number": invoice_number,
            "customer_id": payload["customer_id"],
            "area_id": payload.get("area_id"),
            "price_level_id": payload.get("price_level_id"),
            "invoice_date_ad": payload.get("invoice_date_ad") or now_ad.date(),
            "invoice_date_bs": payload["invoice_date_bs"],
            "sale_mode": "Wholesale" if is_wholesale else "Retail",
            "total_qty": total_qty,
            "total_free_qty": total_free_qty,
            "total_gross_amount": total_gross_amount,
            "total_discount_amount": total_discount_amount,
            "total_cc_amount": total_cc_amount,
            "total_tax_amount": total_tax_amount,
            "round_off": round_off,
            "grand_total": grand_total,
            "payment_type": payload.get("payment_type"),
            "amount_paid_now": payload.get("amount_paid_now", 0) or 0,
            "status": payload.get("status", "Posted"),
            "remarks": (payload.get("remarks") or "").strip() or None,
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }

        try:
            new_id = self._model.insert_with_items(header_data, computed_lines)
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise DuplicateRecordError("Invoice Number already exists (concurrent save detected).") from exc
            logger.exception("Unexpected error inserting sale invoice.")
            raise

        # ---- Stock deduction, per line, via the EXISTING mechanism ----
        stock_errors: list[str] = []
        for line in computed_lines:
            total_deduction = line["qty"] + line["free_qty"]
            try:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    transaction_type="SALE",
                    quantity_change=-total_deduction,
                    current_user_id=current_user_id,
                    reference_type="sale_invoice",
                    reference_id=new_id,
                    remarks=f"Sale Invoice {invoice_number}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Sale invoice %s saved but stock deduction failed for item_batch_id=%s: %s",
                    invoice_number, line["item_batch_id"], exc,
                )
                stock_errors.append(f"Batch {line['batch_no']}: {exc}")

        row = self._model.get_by_id(new_id)
        item_rows = self._model.get_items_by_invoice(new_id)
        lines_dto = [SaleInvoiceLineDTO.from_row(r) for r in item_rows]
        dto = SaleInvoiceDTO.from_row(row, lines=lines_dto)

        if stock_errors:
            # Invoice is real and saved -- but stock reconciliation needs
            # manual attention. Raised as a distinct, catchable error so
            # the Screen can tell the user "invoice X was created, but: ..."
            # rather than silently hiding a partial-stock situation.
            raise EngineErrorWithInvoice(dto, stock_errors)

        return dto

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_sale_invoice(self, sale_invoice_id: int, include_deleted: bool = False) -> SaleInvoiceDTO:
        row = self._model.get_by_id(sale_invoice_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Sale Invoice {sale_invoice_id} not found.")
        item_rows = self._model.get_items_by_invoice(sale_invoice_id)
        lines_dto = [SaleInvoiceLineDTO.from_row(r) for r in item_rows]
        return SaleInvoiceDTO.from_row(row, lines=lines_dto)

    def search_sale_invoices(
        self,
        search_text: Optional[str] = None,
        customer_id: Optional[int] = None,
        area_id: Optional[int] = None,
        status: Optional[str] = None,
        sale_mode: Optional[str] = None,
        date_from_ad=None,
        date_to_ad=None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[SaleInvoiceDTO], int]:
        filters = SaleInvoiceSearchFilters(
            search_text=search_text, customer_id=customer_id, area_id=area_id,
            status=status, sale_mode=sale_mode, date_from_ad=date_from_ad, date_to_ad=date_to_ad,
            include_deleted=include_deleted, page=page, page_size=page_size,
        )
        rows, total_count = self._model.search(filters)
        return [SaleInvoiceDTO.from_row(r) for r in rows], total_count

    # ------------------------------------------------------------------ #
    # CANCEL (soft delete -- add-only document, per confirmed scope)
    # ------------------------------------------------------------------ #
    def cancel_sale_invoice(self, sale_invoice_id: int, current_user_id: int) -> None:
        """
        Cancels (soft-deletes) a Sale Invoice. Does NOT automatically
        reverse stock -- per the same reasoning already documented for
        Purchase: a cancellation is a status change, not an inventory
        event. Physical stock correction, if needed, goes through Sale
        Return (Phase-3) so there is always an auditable ledger entry
        rather than a silent reversal.
        """
        existing = self._model.get_by_id(sale_invoice_id)
        if existing is None:
            raise RecordNotFoundError(f"Sale Invoice {sale_invoice_id} not found or already cancelled.")
        ok = self._model.soft_delete(sale_invoice_id, current_user_id, self._now_ad(), self._now_bs())
        if not ok:
            raise RecordNotFoundError(f"Sale Invoice {sale_invoice_id} not found or already cancelled.")
        logger.info("Sale Invoice %s cancelled by user %s.", sale_invoice_id, current_user_id)


class EngineErrorWithInvoice(Exception):
    """
    Raised by create_sale_invoice() when the invoice itself saved
    successfully but one or more stock deductions failed. Carries the
    already-created DTO so the caller can still show/use the invoice,
    plus the list of per-line stock error messages -- mirrors the exact
    partial-success pattern ItemFormScreen already uses for
    item-saved-but-batch-failed.
    """
    def __init__(self, dto: SaleInvoiceDTO, stock_errors: list[str]) -> None:
        self.dto = dto
        self.stock_errors = stock_errors
        super().__init__(f"Sale Invoice {dto.invoice_number} saved, but stock deduction failed for {len(stock_errors)} line(s).")


def _is_unique_violation(exc: Exception) -> bool:
    return getattr(exc, "pgcode", None) == "23505"


__all__ = ["SaleEngine", "SaleInvoiceDTO", "SaleInvoiceLineDTO", "EngineErrorWithInvoice"]
```

---

## 4. Wiring Notes (for Part 3)

```python
# Construction order matters -- SaleEngine depends on BOTH item_engine
# (already exists app-wide) AND item_free_scheme_engine (new, built first).

from models.item_free_scheme_model import ItemFreeSchemeModel
from models.sale_invoice_model import SaleInvoiceModel
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.sale_engine import SaleEngine
from engines.item_lookup_registry import manufacturer_lookup, country_tax_lookup

# 1. ItemFreeSchemeEngine built FIRST
item_free_scheme_engine = ItemFreeSchemeEngine(model=ItemFreeSchemeModel())

# 2. SaleEngine built SECOND -- needs item_engine (shared/existing) + item_free_scheme_engine
sale_engine = SaleEngine(
    model=SaleInvoiceModel(),
    item_engine=item_engine_instance,               # the SAME ItemEngine already used app-wide
    item_free_scheme_engine=item_free_scheme_engine, # from step 1
    country_tax_lookup_fn=country_tax_lookup,
    manufacturer_lookup_fn=manufacturer_lookup,
)
```

---

## 5. Confirmed-Rule Traceability (so nothing gets lost between Parts)

| Confirmed Rule | Where It Lives |
|---|---|
| Area→Customer two-combo | `customer_model.get_active_customers_by_area()` (Part 1) — Screen wiring in Part 3 |
| Qty-only compulsory, rest Settings-driven | `sale.column_show_*` settings (Part 1) — Screen reads these to build the grid (Part 3) |
| Free column hidden ⇒ Retail, scheme never runs | `SaleEngine.is_wholesale_mode()` — single source of truth, gates all free/CC logic in `compute_line()` |
| Free Scheme = ratio (X+Y), one active per item | `item_free_scheme` table + `ItemFreeSchemeEngine.get_scheme_for_item()` |
| Minimum 1 to auto-fill free | `SaleEngine._compute_auto_free_qty()` via `sale.minimum_auto_free_qty` |
| Half-free toggle | `sale.allow_half_free` setting, read in `_compute_auto_free_qty()` |
| Net Rate formula | `SaleEngine._compute_net_rate()` — `current_rate × scheme_qty ÷ (scheme_qty + scheme_free)` |
| Rate always editable | `compute_line()` only auto-fills `rate` when `line_input.get("rate") is None` — an explicit user value always wins |
| Batch/Expiry read-only, nearest-expiry | `SaleEngine._pick_nearest_expiry_batch()`, reuses `ItemEngine.get_batches()` |
| CC on Purchase Rate, Wholesale only | `compute_line()` step 4 — gated by `is_wholesale and free_qty > 0`, uses `item_dto.purchase_rate`, never `mrp` |
| Payment Type fixed list | `VALID_PAYMENT_TYPES` in `sale_validator.py`, mirrored from the DB CHECK constraint |
| Receipt/Payment separate module | Nothing in `sale_engine.py` writes to `receipt_payment` — `amount_paid_now` is invoice-level only |
| Row-level inline item entry | Pure UI concern, deferred to Part 3 (Screens) |

---

**Part 2 complete.** Waiting for your confirmation before Part 3 (Screens: `sale_invoice_form_screen.py` with the row-level searchable-combo grid, `sale_invoice_list_screen.py`, `item_free_scheme_list_screen.py`/form, Dashboard wiring, and the combined Purchase+Sale ERP-AI-Tool blueprint JSON).
