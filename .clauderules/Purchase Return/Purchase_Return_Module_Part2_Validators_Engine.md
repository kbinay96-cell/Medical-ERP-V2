# Purchase Return Module — Part 2: Validators + Engine Layer

**Project:** Medical ERP V2
**Layer:** Business Logic (Validators + Engine — "No SQL. Business logic lives ONLY here.")
**Depends on Part 1:** `purchase_return`/`purchase_return_item` tables, `models/purchase_return_model.py`, `PurchaseInvoiceModel.get_returnable_items()` extension.
**Reuses (already built, unchanged):**
- `engines/item_engine.py` — `ItemEngine.post_stock_movement()` (already documented for this exact case)
- `engines/date_engine.py` — `ad_to_bs()`, `DateEngineError`
- `engines/exceptions.py` — `ValidationError`, `RecordNotFoundError`, `DuplicateRecordError`, `EngineError`
- `models/purchase_invoice_model.py` — `get_by_id()`, `get_returnable_items()` (Part 1 extension)

---

## 1. `engines/purchase_return_validator.py`

```python
"""
engines/purchase_return_validator.py

Purchase Return Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- mirrors engines/sale_return_validator.py's
shape, adapted for the independent paid-qty / free-qty cumulative checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
VALID_SETTLEMENT_MODES = ("Adjust Against Payable", "Supplier Advance", "Cash Refund")
VALID_RETURN_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class PurchaseReturnValidator:
    """
    Stateless validation rules for Purchase Return header + lines. Does
    NOT compute anything (no proportional discount/cc math, no stock
    posting) -- that lives in PurchaseReturnEngine, same separation used
    between PurchaseValidator and PurchaseEngine.
    """

    def __init__(
        self,
        return_number_exists_fn: Callable[[str, Optional[int]], bool],
        returned_qty_fn: Callable[[int], dict[str, float]],
    ) -> None:
        self._return_number_exists_fn = return_number_exists_fn
        # returned_qty_fn(purchase_invoice_item_id) ->
        # {"returned_qty": ..., "returned_free_qty": ...}, injected so the
        # Validator never touches the Model directly.
        self._returned_qty_fn = returned_qty_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("purchase_invoice_id"):
            result.add("Original Purchase Invoice is mandatory.")

        if not data.get("supplier_id"):
            result.add("Supplier is mandatory.")

        if not data.get("return_date_bs"):
            result.add("Return Date (BS) is mandatory.")

        return_reason = (data.get("return_reason") or "").strip()
        if not return_reason:
            result.add("Return Reason is mandatory.")
        elif len(return_reason) > MAX_LEN_REASON:
            result.add(f"Return Reason must not exceed {MAX_LEN_REASON} characters.")

        settlement_mode = data.get("settlement_mode", "Adjust Against Payable")
        if settlement_mode not in VALID_SETTLEMENT_MODES:
            result.add(f"Settlement Mode must be one of {VALID_SETTLEMENT_MODES}.")

        status = data.get("status", "Posted")
        if status not in VALID_RETURN_STATUSES:
            result.add("Status must be one of Draft, Posted, Cancelled.")

        return result

    def validate_return_number_unique(self, return_number: str, exclude_id: Optional[int] = None) -> ValidationResult:
        result = ValidationResult()
        number = (return_number or "").strip()
        if not number:
            result.add("Return Number is required.")
        elif self._return_number_exists_fn(number, exclude_id):
            result.add(f"Return Number '{number}' already exists.")
        return result

    def validate_lines(self, line_rows: list[dict], invoice_item_lookup: dict[int, dict]) -> ValidationResult:
        """
        Validates the whole return-line list against the original
        invoice's lines. `invoice_item_lookup` maps
        purchase_invoice_item_id -> that line's original row (from
        PurchaseInvoiceModel.get_returnable_items()), so this method
        never queries the database itself.

        Called by the Engine BEFORE any proportional discount/cc
        computation runs -- a structurally bad or over-quantity line
        list is rejected early, never partially computed or posted.

        Paid qty and free qty are checked INDEPENDENTLY -- a line can be
        fully returned on one side while still having remaining
        returnable quantity on the other.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("At least one return line is required.")
            return result

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"
            invoice_item_id = row.get("purchase_invoice_item_id")

            if not invoice_item_id:
                result.add(f"{prefix}: Original invoice line reference is required.")
                continue

            original = invoice_item_lookup.get(invoice_item_id)
            if original is None:
                result.add(f"{prefix}: Original invoice line not found on this invoice.")
                continue

            try:
                return_qty = float(row.get("return_qty") or 0)
                return_free_qty = float(row.get("return_free_qty") or 0)
            except (TypeError, ValueError):
                result.add(f"{prefix}: Return Qty and Return Free Qty must be valid numbers.")
                continue

            if return_qty < 0 or return_free_qty < 0:
                result.add(f"{prefix}: Return Qty and Return Free Qty cannot be negative.")
                continue

            if return_qty == 0 and return_free_qty == 0:
                result.add(f"{prefix}: Enter a Return Qty and/or a Return Free Qty greater than zero.")
                continue

            already = self._returned_qty_fn(invoice_item_id)
            original_qty = float(original.get("qty", 0))
            original_free_qty = float(original.get("free_qty", 0))
            remaining_qty = original_qty - already["returned_qty"]
            remaining_free_qty = original_free_qty - already["returned_free_qty"]

            if return_qty > remaining_qty:
                result.add(
                    f"{prefix}: Return Qty ({return_qty}) exceeds remaining returnable paid "
                    f"quantity ({remaining_qty}) -- already returned {already['returned_qty']} "
                    f"of {original_qty}."
                )
            if return_free_qty > remaining_free_qty:
                result.add(
                    f"{prefix}: Return Free Qty ({return_free_qty}) exceeds remaining returnable "
                    f"free quantity ({remaining_free_qty}) -- already returned "
                    f"{already['returned_free_qty']} of {original_free_qty}."
                )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Purchase Return.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result
```

---

## 2. `engines/purchase_return_engine.py` — The Core Engine

```python
"""
engines/purchase_return_engine.py

Purchase Return Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - generates Return Numbers (PRTN-0001 style, mirrors PINV- pattern)
    - resolves each return line's read-only rate/discount/cc by copying
      proportionally from the original purchase_invoice_item (discount
      proportional to return_qty since discount only ever applied to
      paid qty; cc proportional to return_free_qty since cc was computed
      on free-goods customs value) -- never re-entered
    - enforces the two INDEPENDENT cumulative-qty rules (paid + free) via
      PurchaseReturnValidator + PurchaseInvoiceModel.get_returnable_items()
    - orchestrates validation before touching the database
      (models/purchase_return_model.py)
    - posts stock reversal through the EXISTING
      ItemEngine.post_stock_movement() -- this is literally the case its
      own docstring already documents ("negative = stock OUT ... a
      Purchase Return") -- no new stock-writing code
    - stamps BS-first audit fields via the shared Date Engine
    - enforces Cancel = reversal-posting (never edits history, never
      deletes a Posted return -- only a Draft may be soft-deleted)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.purchase_return_validator import PurchaseReturnValidator
from models.purchase_return_model import PurchaseReturnModel, PurchaseReturnSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_RETURN_PREFIX = "PRTN-"
DEFAULT_RETURN_PADDING = 4  # PRTN-0001


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; PurchaseReturnEngine falls back to AD-only stamps.")
        return None


@dataclass
class PurchaseReturnLineDTO:
    """Read-facing representation of one posted Purchase Return line."""
    purchase_return_item_id: int
    purchase_invoice_item_id: int
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    return_qty: float
    return_free_qty: float
    rate: float
    discount_percent: float
    discount_amount: float
    cc_percent: float
    cc_amount: float
    amount: float
    remarks: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "PurchaseReturnLineDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


@dataclass
class PurchaseReturnDTO:
    """Read-facing representation returned by the Engine to callers."""
    purchase_return_id: int
    return_number: str
    purchase_invoice_id: int
    supplier_id: int
    return_date_ad: Any
    return_date_bs: str
    return_reason: str
    settlement_mode: str
    total_qty: float
    total_free_qty: float
    total_gross_amount: float
    total_discount_amount: float
    total_cc_amount: float
    grand_total: float
    status: str
    cancellation_reason: Optional[str]
    remarks: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    internal_ref_number: Optional[str] = None   # only populated by search() (joined)
    supplier_name: Optional[str] = None         # only populated by search() (joined)
    lines: list[PurchaseReturnLineDTO] = None

    @classmethod
    def from_row(cls, row: dict, lines: Optional[list[PurchaseReturnLineDTO]] = None) -> "PurchaseReturnDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "lines"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, lines=lines or [])

    def to_dict(self) -> dict:
        return asdict(self)


class PurchaseReturnEngine:
    """Business-rule orchestration for the Purchase Return module."""

    def __init__(
        self,
        model: Optional[PurchaseReturnModel] = None,
        purchase_invoice_model=None,      # models.purchase_invoice_model.PurchaseInvoiceModel -- REQUIRED, injected (shared instance)
        item_engine=None,                 # engines.item_engine.ItemEngine -- REQUIRED, injected (shared instance)
        date_engine: Optional[Any] = None,
        validator: Optional[PurchaseReturnValidator] = None,
    ) -> None:
        if purchase_invoice_model is None:
            raise ValueError("PurchaseReturnEngine requires a purchase_invoice_model instance (shared with the Purchase module).")
        if item_engine is None:
            raise ValueError("PurchaseReturnEngine requires an item_engine instance (shared with the rest of the app).")

        self._model = model or PurchaseReturnModel()
        self._purchase_invoice_model = purchase_invoice_model
        self._item_engine = item_engine
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or PurchaseReturnValidator(
            return_number_exists_fn=self._return_number_exists,
            returned_qty_fn=self._model.get_returned_qty_for_invoice_item,
        )

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _return_number_exists(self, return_number: str, exclude_id: Optional[int] = None) -> bool:
        existing = self._model.search(PurchaseReturnSearchFilters(search_text=return_number, page_size=1))
        for row in existing:
            if row["return_number"] == return_number and row["purchase_return_id"] != exclude_id:
                return True
        return False

    def _generate_return_number(self) -> str:
        """Sequential PRTN-0001 style, same approach as internal_ref_number generation."""
        latest = self._model.search(PurchaseReturnSearchFilters(page_size=1, include_deleted=True))
        next_seq = 1
        if latest:
            last_number = latest[0]["return_number"]
            try:
                next_seq = int(last_number.replace(DEFAULT_RETURN_PREFIX, "")) + 1
            except ValueError:
                next_seq = 1
        return f"{DEFAULT_RETURN_PREFIX}{next_seq:0{DEFAULT_RETURN_PADDING}d}"

    def _stamp_bs_date(self, ad_value: date) -> str:
        if self._date_engine is None:
            return ad_value.isoformat()
        try:
            return self._date_engine.ad_to_bs(ad_value)
        except Exception:
            logger.warning("BS conversion failed for %s; falling back to AD string.", ad_value)
            return ad_value.isoformat()

    def _build_line_from_original(self, return_row: dict, original: dict) -> dict:
        """
        Computes the proportional, read-only discount/cc/amount for one
        return line from its original purchase_invoice_item row -- NEVER
        re-entered by the user.

        - discount_amount is proportional to return_qty / original.qty
          (discount only ever applied to paid qty on the original line).
        - cc_amount is proportional to return_free_qty / original.free_qty
          (cc was computed on free-goods customs value on the original
          line -- see Purchase Module Part 1 sec 1.3).
        - amount (value) only comes from the paid-qty portion; the
          free-qty portion always contributes 0 value, same as on the
          original invoice line.
        """
        return_qty = float(return_row.get("return_qty") or 0)
        return_free_qty = float(return_row.get("return_free_qty") or 0)
        original_qty = float(original["qty"])
        original_free_qty = float(original.get("free_qty") or 0)

        qty_proportion = return_qty / original_qty if original_qty else 0
        free_qty_proportion = return_free_qty / original_free_qty if original_free_qty else 0

        rate = float(original["purchase_rate"])
        discount_percent = float(original.get("discount_percent") or 0)
        discount_amount = round(float(original.get("discount_amount") or 0) * qty_proportion, 2)
        cc_percent = float(original.get("cc_percent") or 0)
        cc_amount = round(float(original.get("cc_amount") or 0) * free_qty_proportion, 2)
        amount = round((return_qty * rate) - discount_amount, 2)

        return {
            "purchase_invoice_item_id": original["purchase_invoice_item_id"],
            "item_id": original["item_id"],
            "item_batch_id": original["item_batch_id"],
            "batch_no": original["batch_no"],
            "expiry_month": original["expiry_month"],
            "expiry_year": original["expiry_year"],
            "return_qty": return_qty,
            "return_free_qty": return_free_qty,
            "rate": rate,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "cc_percent": cc_percent,
            "cc_amount": cc_amount,
            "amount": amount,
            "remarks": return_row.get("remarks"),
        }

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_return(
        self,
        purchase_invoice_id: int,
        supplier_id: int,
        return_date_ad: date,
        return_reason: str,
        settlement_mode: str,
        return_lines: list[dict],   # each: {"purchase_invoice_item_id", "return_qty", "return_free_qty", "remarks"?}
        created_by: int,
        remarks: Optional[str] = None,
        status: str = "Posted",
    ) -> PurchaseReturnDTO:
        # 1. Load the original invoice's returnable lines -- single source of truth
        invoice = self._purchase_invoice_model.get_by_id(purchase_invoice_id)
        if invoice is None:
            raise RecordNotFoundError(f"Purchase Invoice {purchase_invoice_id} not found.")

        returnable_items = self._purchase_invoice_model.get_returnable_items(purchase_invoice_id)
        invoice_item_lookup = {row["purchase_invoice_item_id"]: row for row in returnable_items}

        # 2. Validate header + lines BEFORE any computation
        header_data = {
            "purchase_invoice_id": purchase_invoice_id,
            "supplier_id": supplier_id,
            "return_date_bs": self._stamp_bs_date(return_date_ad),
            "return_reason": return_reason,
            "settlement_mode": settlement_mode,
            "status": status,
        }
        header_result = self._validator.validate_header(header_data)
        if not header_result.is_valid:
            raise ValidationError("; ".join(header_result.errors))

        lines_result = self._validator.validate_lines(return_lines, invoice_item_lookup)
        if not lines_result.is_valid:
            raise ValidationError("; ".join(lines_result.errors))

        # 3. Build computed, read-only line rows
        computed_lines = [
            self._build_line_from_original(row, invoice_item_lookup[row["purchase_invoice_item_id"]])
            for row in return_lines
        ]

        # 4. Roll up header totals
        total_qty = sum(l["return_qty"] for l in computed_lines)
        total_free_qty = sum(l["return_free_qty"] for l in computed_lines)
        total_gross_amount = round(sum(l["return_qty"] * l["rate"] for l in computed_lines), 2)
        total_discount_amount = round(sum(l["discount_amount"] for l in computed_lines), 2)
        total_cc_amount = round(sum(l["cc_amount"] for l in computed_lines), 2)
        grand_total = round(total_gross_amount - total_discount_amount + total_cc_amount, 2)

        # 5. Generate return_number, verify uniqueness (defensive re-check)
        return_number = self._generate_return_number()
        number_result = self._validator.validate_return_number_unique(return_number)
        if not number_result.is_valid:
            raise DuplicateRecordError("; ".join(number_result.errors))

        now_ad = datetime.now(timezone.utc)
        header_data.update({
            "return_number": return_number,
            "return_date_ad": return_date_ad,
            "total_qty": total_qty,
            "total_free_qty": total_free_qty,
            "total_gross_amount": total_gross_amount,
            "total_discount_amount": total_discount_amount,
            "total_cc_amount": total_cc_amount,
            "grand_total": grand_total,
            "remarks": remarks,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        })

        # 6. Persist header + lines in one transaction
        purchase_return_id = self._model.insert_with_items(header_data, computed_lines)

        # 7. Only a Posted return moves stock -- OUT this time (goods leaving to supplier)
        if status == "Posted":
            for line in computed_lines:
                total_units = line["return_qty"] + line["return_free_qty"]
                if total_units <= 0:
                    continue
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=-total_units,
                    transaction_type="PURCHASE_RETURN",
                    reference_id=purchase_return_id,
                    created_by=created_by,
                )

        return self.get_by_id(purchase_return_id)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, purchase_return_id: int) -> Optional[PurchaseReturnDTO]:
        row = self._model.get_by_id(purchase_return_id)
        if row is None:
            return None
        item_rows = self._model.get_items_by_return_id(purchase_return_id)
        lines = [PurchaseReturnLineDTO.from_row(r) for r in item_rows]
        return PurchaseReturnDTO.from_row(row, lines=lines)

    def search(self, filters: PurchaseReturnSearchFilters) -> list[PurchaseReturnDTO]:
        rows = self._model.search(filters)
        return [PurchaseReturnDTO.from_row(row) for row in rows]

    def get_returnable_lines(self, purchase_invoice_id: int) -> list[dict]:
        """Convenience pass-through for the Screen -- remaining returnable
        paid AND free qty per line, computed independently."""
        rows = self._purchase_invoice_model.get_returnable_items(purchase_invoice_id)
        for row in rows:
            row["remaining_returnable_qty"] = float(row["qty"]) - float(row["already_returned_qty"])
            row["remaining_returnable_free_qty"] = float(row.get("free_qty") or 0) - float(row["already_returned_free_qty"])
        return rows

    # ------------------------------------------------------------------ #
    # CANCEL -- reversal posting, never an edit of history
    # ------------------------------------------------------------------ #
    def cancel_return(self, purchase_return_id: int, cancellation_reason: str, updated_by: int) -> PurchaseReturnDTO:
        existing = self._model.get_by_id(purchase_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Purchase Return {purchase_return_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("This Purchase Return is already Cancelled.")

        reason_result = self._validator.validate_cancellation(cancellation_reason)
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        # Reverse the stock effect ONLY if it was Posted -- stock comes BACK IN this time
        if existing["status"] == "Posted":
            item_rows = self._model.get_items_by_return_id(purchase_return_id)
            for line in item_rows:
                total_units = float(line["return_qty"]) + float(line["return_free_qty"])
                if total_units <= 0:
                    continue
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=total_units,
                    transaction_type="PURCHASE_RETURN_CANCEL",
                    reference_id=purchase_return_id,
                    created_by=updated_by,
                )

        now_ad = datetime.now(timezone.utc)
        self._model.cancel(
            purchase_return_id=purchase_return_id,
            cancellation_reason=cancellation_reason,
            updated_by=updated_by,
            updated_at_ad=now_ad,
            updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(purchase_return_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE -- Draft only (a Posted or Cancelled return is never deleted, only cancelled)
    # ------------------------------------------------------------------ #
    def delete_draft(self, purchase_return_id: int, deleted_by: int) -> None:
        existing = self._model.get_by_id(purchase_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Purchase Return {purchase_return_id} not found.")
        if existing["status"] != "Draft":
            raise ValidationError("Only a Draft Purchase Return can be deleted. Use Cancel for a Posted return.")

        now_ad = datetime.now(timezone.utc)
        self._model.soft_delete(
            purchase_return_id=purchase_return_id,
            deleted_by=deleted_by,
            deleted_at_ad=now_ad,
            deleted_at_bs=self._stamp_bs_date(now_ad.date()),
        )
```

---

## 3. Wiring Notes (for Part 3)

```
Construction order -- PurchaseReturnEngine depends on BOTH
purchase_invoice_model (already exists, shared) AND item_engine
(already exists, shared). No new lower-level engine needed first.

1. PurchaseInvoiceModel  -- already exists, extended in Part 1 with
   get_returnable_items()
2. ItemEngine            -- already exists, unchanged
3. PurchaseReturnEngine  -- built with both of the above injected:

       purchase_return_engine = PurchaseReturnEngine(
           purchase_invoice_model=existing_purchase_invoice_model,
           item_engine=existing_item_engine,
       )

   PurchaseReturnValidator is constructed internally by
   PurchaseReturnEngine (same pattern as PurchaseEngine building
   PurchaseValidator itself) -- the Screen never touches the Validator
   directly.
```

---

## 4. Confirmed-Rule Traceability

| Confirmed Rule (from Part 1 Scope) | Where enforced |
|---|---|
| Return always against a specific posted Purchase Invoice line | `create_return()` loads `get_returnable_items()`; `validate_lines()` rejects any `purchase_invoice_item_id` not found on that invoice |
| Paid qty and free qty returnable independently, each cumulative-checked | `PurchaseReturnValidator.validate_lines()` checks `remaining_qty` and `remaining_free_qty` separately via injected `returned_qty_fn` (backed by `PurchaseReturnModel.get_returned_qty_for_invoice_item()`) |
| Same-batch stock reversal, no batch selection | `_build_line_from_original()` copies `item_batch_id`/`batch_no`/expiry straight from the original line |
| Rate/discount/cc read-only, proportional to original line | `_build_line_from_original()` is the ONLY place these are computed -- discount proportional to `return_qty`, cc proportional to `return_free_qty` -- never accepted from `return_lines` input |
| `settlement_mode` fixed list, reserved for future Accounts posting | Enforced in `PurchaseReturnValidator.validate_header()`; no journal posting happens yet |
| Draft/Posted/Cancelled lifecycle | `status` validated in `validate_header()`; only `Posted` triggers `post_stock_movement()` (negative -- stock OUT) in `create_return()` |
| Cancellation requires mandatory reason, reverses via new posting | `cancel_return()` calls `validate_cancellation()` then posts an equal-and-opposite `PURCHASE_RETURN_CANCEL` movement (positive -- stock back IN) -- `purchase_return_item` rows are never touched |
| Soft-delete only for Draft; Posted/Cancelled are never deleted | `delete_draft()` explicitly checks `status == 'Draft'` and raises `ValidationError` otherwise |

---

**Part 2 complete.** Waiting for your confirmation before Part 3 (Screens: `purchase_return_form_screen.py` with the Invoice→returnable-lines picker showing both paid and free remaining qty per row, `purchase_return_list_screen.py`, wiring checklist, and the updated Combined Blueprint JSON replacing the old `purchase_return` Phase-2 placeholder tasks).
