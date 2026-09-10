# Sale Return Module — Part 2: Validators + Engine Layer

**Project:** Medical ERP V2
**Layer:** Business Logic (Validators + Engine — "No SQL. Business logic lives ONLY here.")
**Depends on Part 1:** `sale_return`/`sale_return_item` tables, `models/sale_return_model.py`, `SaleInvoiceModel.get_returnable_items()` extension.
**Reuses (already built, unchanged):**
- `engines/item_engine.py` — `ItemEngine.post_stock_movement()`
- `engines/date_engine.py` — `ad_to_bs()`, `DateEngineError`
- `engines/settings_engine.py` — `get_setting()`
- `engines/exceptions.py` — `ValidationError`, `RecordNotFoundError`, `DuplicateRecordError`, `EngineError`
- `models/sale_invoice_model.py` — `get_by_id()`, `get_returnable_items()` (Part 1 extension)

---

## 1. `engines/sale_return_validator.py`

```python
"""
engines/sale_return_validator.py

Sale Return Validator - Medical ERP V2

Project rule: "Validation must be separated from the Model." Pure
validation rules only -- never touches the database directly except via
injected callback functions from the Engine (which owns the Model).
Mirrors engines/sale_validator.py's shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

MAX_LEN_REASON = 1000
VALID_REFUND_MODES = ("Adjust Against Invoice", "Advance", "Cash Refund")
VALID_RETURN_STATUSES = ("Draft", "Posted", "Cancelled")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, message: str) -> None:
        self.errors.append(message)


class SaleReturnValidator:
    """
    Stateless validation rules for Sale Return header + lines. Does NOT
    compute anything (no proportional discount/cc/tax math, no stock
    posting) -- it only checks that what the Engine is about to save is
    structurally sound and within the remaining returnable quantity.
    All computation lives in SaleReturnEngine, same separation used
    between SaleInvoiceValidator and SaleEngine.
    """

    def __init__(
        self,
        return_number_exists_fn: Callable[[str, Optional[int]], bool],
        returned_qty_fn: Callable[[int], float],
    ) -> None:
        self._return_number_exists_fn = return_number_exists_fn
        # returned_qty_fn(sale_invoice_item_id) -> already-returned qty,
        # injected so the Validator never touches the Model directly.
        self._returned_qty_fn = returned_qty_fn

    # ------------------------------------------------------------------ #
    def validate_header(self, data: dict) -> ValidationResult:
        result = ValidationResult()

        if not data.get("sale_invoice_id"):
            result.add("Original Sale Invoice is mandatory.")

        if not data.get("customer_id"):
            result.add("Customer is mandatory.")

        if not data.get("return_date_bs"):
            result.add("Return Date (BS) is mandatory.")

        return_reason = (data.get("return_reason") or "").strip()
        if not return_reason:
            result.add("Return Reason is mandatory.")
        elif len(return_reason) > MAX_LEN_REASON:
            result.add(f"Return Reason must not exceed {MAX_LEN_REASON} characters.")

        refund_mode = data.get("refund_mode", "Adjust Against Invoice")
        if refund_mode not in VALID_REFUND_MODES:
            result.add(f"Refund Mode must be one of {VALID_REFUND_MODES}.")

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
        Validates the whole return-line list at once against the original
        invoice's lines. `invoice_item_lookup` maps
        sale_invoice_item_id -> that line's original row (from
        SaleInvoiceModel.get_returnable_items()), so this method never
        queries the database itself.

        Called by the Engine BEFORE any proportional discount/cc/tax
        computation runs -- a structurally bad or over-quantity line list
        is rejected early, never partially computed or partially posted.
        """
        result = ValidationResult()

        if not line_rows:
            result.add("At least one return line is required.")
            return result

        for index, row in enumerate(line_rows, start=1):
            prefix = f"Line {index}"
            invoice_item_id = row.get("sale_invoice_item_id")

            if not invoice_item_id:
                result.add(f"{prefix}: Original invoice line reference is required.")
                continue

            original = invoice_item_lookup.get(invoice_item_id)
            if original is None:
                result.add(f"{prefix}: Original invoice line not found on this invoice.")
                continue

            return_qty = row.get("return_qty")
            try:
                return_qty = float(return_qty)
                if return_qty <= 0:
                    result.add(f"{prefix}: Return Qty must be greater than zero.")
                    continue
            except (TypeError, ValueError):
                result.add(f"{prefix}: Return Qty must be a valid number.")
                continue

            already_returned = self._returned_qty_fn(invoice_item_id)
            original_qty = float(original.get("qty", 0))
            remaining = original_qty - already_returned

            if return_qty > remaining:
                result.add(
                    f"{prefix}: Return Qty ({return_qty}) exceeds remaining returnable "
                    f"quantity ({remaining}) for this line -- already returned {already_returned} "
                    f"of {original_qty}."
                )

        return result

    def validate_cancellation(self, cancellation_reason: str) -> ValidationResult:
        result = ValidationResult()
        reason = (cancellation_reason or "").strip()
        if not reason:
            result.add("Cancellation Reason is mandatory to cancel a Sale Return.")
        elif len(reason) > MAX_LEN_REASON:
            result.add(f"Cancellation Reason must not exceed {MAX_LEN_REASON} characters.")
        return result
```

---

## 2. `engines/sale_return_engine.py` — The Core Engine

```python
"""
engines/sale_return_engine.py

Sale Return Engine - Medical ERP V2

Project rule: "Keep business logic inside the Engine only." This is the
ONLY place that:
    - generates Return Numbers (SRTN-0001 style, mirrors SINV-/PINV- pattern)
    - resolves each return line's read-only rate/discount/cc/tax by
      copying proportionally from the original sale_invoice_item (never
      re-entered, per confirmed scope)
    - enforces the cumulative-returned-qty rule via
      SaleReturnValidator + SaleInvoiceModel.get_returnable_items()
    - orchestrates validation before touching the database
      (models/sale_return_model.py)
    - posts stock re-entry through the EXISTING
      ItemEngine.post_stock_movement() -- no new stock-writing code
    - stamps BS-first audit fields via the shared Date Engine
    - enforces the Cancel = reversal-posting rule (never edits history,
      never deletes a Posted return -- only a Draft may be soft-deleted)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.sale_return_validator import SaleReturnValidator
from models.sale_return_model import SaleReturnModel, SaleReturnSearchFilters

logger = logging.getLogger(__name__)

DEFAULT_RETURN_PREFIX = "SRTN-"
DEFAULT_RETURN_PADDING = 4  # SRTN-0001


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning("engines.date_engine not importable; SaleReturnEngine falls back to AD-only stamps.")
        return None


@dataclass
class SaleReturnLineDTO:
    """Read-facing representation of one posted Sale Return line."""
    sale_return_item_id: int
    sale_invoice_item_id: int
    item_id: int
    item_batch_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    return_qty: float
    rate: float
    discount_percent: float
    discount_amount: float
    cc_percent: float
    cc_amount: float
    tax_percent: float
    tax_amount: float
    amount: float
    remarks: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "SaleReturnLineDTO":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__.keys()})


@dataclass
class SaleReturnDTO:
    """Read-facing representation returned by the Engine to callers."""
    sale_return_id: int
    return_number: str
    sale_invoice_id: int
    customer_id: int
    return_date_ad: Any
    return_date_bs: str
    return_reason: str
    refund_mode: str
    total_qty: float
    total_gross_amount: float
    total_discount_amount: float
    total_cc_amount: float
    total_tax_amount: float
    round_off: float
    grand_total: float
    status: str
    cancellation_reason: Optional[str]
    remarks: Optional[str]
    is_deleted: bool
    created_by: int
    created_at_ad: Any
    created_at_bs: Optional[str]
    invoice_number: Optional[str] = None    # only populated by search() (joined)
    customer_name: Optional[str] = None     # only populated by search() (joined)
    lines: list[SaleReturnLineDTO] = None

    @classmethod
    def from_row(cls, row: dict, lines: Optional[list[SaleReturnLineDTO]] = None) -> "SaleReturnDTO":
        known_fields = {f for f in cls.__dataclass_fields__.keys() if f != "lines"}
        known = {k: row.get(k) for k in known_fields}
        return cls(**known, lines=lines or [])

    def to_dict(self) -> dict:
        return asdict(self)


class SaleReturnEngine:
    """Business-rule orchestration for the Sale Return module."""

    def __init__(
        self,
        model: Optional[SaleReturnModel] = None,
        sale_invoice_model=None,               # models.sale_invoice_model.SaleInvoiceModel -- REQUIRED, injected (shared instance)
        item_engine=None,                      # engines.item_engine.ItemEngine -- REQUIRED, injected (shared instance)
        date_engine: Optional[Any] = None,
        validator: Optional[SaleReturnValidator] = None,
    ) -> None:
        if sale_invoice_model is None:
            raise ValueError("SaleReturnEngine requires a sale_invoice_model instance (shared with the Sale module).")
        if item_engine is None:
            raise ValueError("SaleReturnEngine requires an item_engine instance (shared with the rest of the app).")

        self._model = model or SaleReturnModel()
        self._sale_invoice_model = sale_invoice_model
        self._item_engine = item_engine
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()
        self._validator = validator or SaleReturnValidator(
            return_number_exists_fn=self._return_number_exists,
            returned_qty_fn=self._model.get_returned_qty_for_invoice_item,
        )

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _return_number_exists(self, return_number: str, exclude_id: Optional[int] = None) -> bool:
        existing = self._model.search(SaleReturnSearchFilters(search_text=return_number, page_size=1))
        for row in existing:
            if row["return_number"] == return_number and row["sale_return_id"] != exclude_id:
                return True
        return False

    def _generate_return_number(self) -> str:
        """Sequential SRTN-0001 style, same approach as invoice_number generation."""
        latest = self._model.search(SaleReturnSearchFilters(page_size=1, include_deleted=True))
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
        Computes the proportional, read-only discount/cc/tax/amount for one
        return line from its original sale_invoice_item row -- NEVER
        re-entered by the user. Proportion is return_qty / original.qty.
        """
        return_qty = float(return_row["return_qty"])
        original_qty = float(original["qty"])
        proportion = return_qty / original_qty if original_qty else 0

        rate = float(original["rate"])
        discount_percent = float(original.get("discount_percent") or 0)
        discount_amount = round(float(original.get("discount_amount") or 0) * proportion, 2)
        cc_percent = float(original.get("cc_percent") or 0)
        cc_amount = round(float(original.get("cc_amount") or 0) * proportion, 2)
        tax_percent = float(original.get("tax_percent") or 0)
        tax_amount = round(float(original.get("tax_amount") or 0) * proportion, 2)
        amount = round((return_qty * rate) - discount_amount, 2)

        return {
            "sale_invoice_item_id": original["sale_invoice_item_id"],
            "item_id": original["item_id"],
            "item_batch_id": original["item_batch_id"],
            "batch_no": original["batch_no"],
            "expiry_month": original["expiry_month"],
            "expiry_year": original["expiry_year"],
            "return_qty": return_qty,
            "rate": rate,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "cc_percent": cc_percent,
            "cc_amount": cc_amount,
            "tax_percent": tax_percent,
            "tax_amount": tax_amount,
            "amount": amount,
            "remarks": return_row.get("remarks"),
        }

    # ------------------------------------------------------------------ #
    # CREATE
    # ------------------------------------------------------------------ #
    def create_return(
        self,
        sale_invoice_id: int,
        customer_id: int,
        return_date_ad: date,
        return_reason: str,
        refund_mode: str,
        return_lines: list[dict],       # each: {"sale_invoice_item_id", "return_qty", "remarks"?}
        created_by: int,
        remarks: Optional[str] = None,
        status: str = "Posted",
    ) -> SaleReturnDTO:
        # 1. Load the original invoice's returnable lines -- single source of truth
        invoice = self._sale_invoice_model.get_by_id(sale_invoice_id)
        if invoice is None:
            raise RecordNotFoundError(f"Sale Invoice {sale_invoice_id} not found.")

        returnable_items = self._sale_invoice_model.get_returnable_items(sale_invoice_id)
        invoice_item_lookup = {row["sale_invoice_item_id"]: row for row in returnable_items}

        # 2. Validate header + lines BEFORE any computation
        header_data = {
            "sale_invoice_id": sale_invoice_id,
            "customer_id": customer_id,
            "return_date_bs": self._stamp_bs_date(return_date_ad),
            "return_reason": return_reason,
            "refund_mode": refund_mode,
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
            self._build_line_from_original(row, invoice_item_lookup[row["sale_invoice_item_id"]])
            for row in return_lines
        ]

        # 4. Roll up header totals
        total_qty = sum(l["return_qty"] for l in computed_lines)
        total_gross_amount = round(sum(l["return_qty"] * l["rate"] for l in computed_lines), 2)
        total_discount_amount = round(sum(l["discount_amount"] for l in computed_lines), 2)
        total_cc_amount = round(sum(l["cc_amount"] for l in computed_lines), 2)
        total_tax_amount = round(sum(l["tax_amount"] for l in computed_lines), 2)
        grand_total = round(
            total_gross_amount - total_discount_amount + total_cc_amount + total_tax_amount, 2
        )

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
            "total_gross_amount": total_gross_amount,
            "total_discount_amount": total_discount_amount,
            "total_cc_amount": total_cc_amount,
            "total_tax_amount": total_tax_amount,
            "round_off": 0,
            "grand_total": grand_total,
            "remarks": remarks,
            "created_by": created_by,
            "created_at_ad": now_ad,
            "created_at_bs": self._stamp_bs_date(now_ad.date()),
        })

        # 6. Persist header + lines in one transaction
        sale_return_id = self._model.insert_with_items(header_data, computed_lines)

        # 7. Only a Posted return moves stock
        if status == "Posted":
            for line in computed_lines:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=line["return_qty"],
                    transaction_type="SALE_RETURN",
                    reference_id=sale_return_id,
                    created_by=created_by,
                )

        return self.get_by_id(sale_return_id)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, sale_return_id: int) -> Optional[SaleReturnDTO]:
        row = self._model.get_by_id(sale_return_id)
        if row is None:
            return None
        item_rows = self._model.get_items_by_return_id(sale_return_id)
        lines = [SaleReturnLineDTO.from_row(r) for r in item_rows]
        return SaleReturnDTO.from_row(row, lines=lines)

    def search(self, filters: SaleReturnSearchFilters) -> list[SaleReturnDTO]:
        rows = self._model.search(filters)
        return [SaleReturnDTO.from_row(row) for row in rows]

    def get_returnable_lines(self, sale_invoice_id: int) -> list[dict]:
        """Convenience pass-through for the Screen -- remaining returnable qty per line."""
        rows = self._sale_invoice_model.get_returnable_items(sale_invoice_id)
        for row in rows:
            row["remaining_returnable_qty"] = float(row["qty"]) - float(row["already_returned_qty"])
        return rows

    # ------------------------------------------------------------------ #
    # CANCEL -- reversal posting, never an edit of history
    # ------------------------------------------------------------------ #
    def cancel_return(self, sale_return_id: int, cancellation_reason: str, updated_by: int) -> SaleReturnDTO:
        existing = self._model.get_by_id(sale_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Sale Return {sale_return_id} not found.")
        if existing["status"] == "Cancelled":
            raise ValidationError("This Sale Return is already Cancelled.")

        reason_result = self._validator.validate_cancellation(cancellation_reason)
        if not reason_result.is_valid:
            raise ValidationError("; ".join(reason_result.errors))

        # Reverse the stock effect ONLY if it was Posted (a Draft never moved stock)
        if existing["status"] == "Posted":
            item_rows = self._model.get_items_by_return_id(sale_return_id)
            for line in item_rows:
                self._item_engine.post_stock_movement(
                    item_batch_id=line["item_batch_id"],
                    quantity_change=-float(line["return_qty"]),
                    transaction_type="SALE_RETURN_CANCEL",
                    reference_id=sale_return_id,
                    created_by=updated_by,
                )

        now_ad = datetime.now(timezone.utc)
        self._model.cancel(
            sale_return_id=sale_return_id,
            cancellation_reason=cancellation_reason,
            updated_by=updated_by,
            updated_at_ad=now_ad,
            updated_at_bs=self._stamp_bs_date(now_ad.date()),
        )
        return self.get_by_id(sale_return_id)

    # ------------------------------------------------------------------ #
    # SOFT DELETE -- Draft only (a Posted or Cancelled return is never deleted, only cancelled)
    # ------------------------------------------------------------------ #
    def delete_draft(self, sale_return_id: int, deleted_by: int) -> None:
        existing = self._model.get_by_id(sale_return_id)
        if existing is None:
            raise RecordNotFoundError(f"Sale Return {sale_return_id} not found.")
        if existing["status"] != "Draft":
            raise ValidationError("Only a Draft Sale Return can be deleted. Use Cancel for a Posted return.")

        now_ad = datetime.now(timezone.utc)
        self._model.soft_delete(
            sale_return_id=sale_return_id,
            deleted_by=deleted_by,
            deleted_at_ad=now_ad,
            deleted_at_bs=self._stamp_bs_date(now_ad.date()),
        )
```

---

## 3. Wiring Notes (for Part 3)

```
Construction order matters -- SaleReturnEngine depends on BOTH
sale_invoice_model (already exists, shared) AND item_engine (already
exists, shared). No new engine needs to be built first (unlike
SaleEngine, which needed ItemFreeSchemeEngine built first).

1. SaleInvoiceModel  -- already exists, extended in Part 1 with
   get_returnable_items()
2. ItemEngine        -- already exists, unchanged
3. SaleReturnEngine  -- built with both of the above injected:

       sale_return_engine = SaleReturnEngine(
           sale_invoice_model=existing_sale_invoice_model,
           item_engine=existing_item_engine,
       )

   SaleReturnValidator is constructed internally by SaleReturnEngine
   (same pattern as SaleEngine building SaleInvoiceValidator itself) --
   the Screen never touches the Validator directly.
```

---

## 4. Confirmed-Rule Traceability

| Confirmed Rule (from Part 1 Scope) | Where enforced |
|---|---|
| Return always against a specific posted Sale Invoice line | `create_return()` loads `get_returnable_items()`; `validate_lines()` rejects any `sale_invoice_item_id` not found on that invoice |
| Cumulative return qty never exceeds original billed qty | `SaleReturnValidator.validate_lines()` via injected `returned_qty_fn` (backed by `SaleReturnModel.get_returned_qty_for_invoice_item()`) |
| Same-batch stock re-entry, no batch selection | `_build_line_from_original()` copies `item_batch_id`/`batch_no`/expiry straight from the original line |
| Free-qty units never returnable | Return lines only ever reference `sale_invoice_item.qty` (paid qty); the Validator/Engine never reads or exposes `free_qty` from the original line |
| Rate/discount/cc/tax read-only, proportional to original line | `_build_line_from_original()` is the ONLY place these are computed -- never accepted from `return_lines` input |
| `refund_mode` fixed list, reserved for future Accounts posting | Enforced in `SaleReturnValidator.validate_header()`; no journal posting happens yet (Accounts module not built) |
| Draft/Posted/Cancelled lifecycle | `status` validated in `validate_header()`; only `Posted` triggers `post_stock_movement()` in `create_return()` |
| Cancellation requires mandatory reason, reverses via new posting (never edits history) | `cancel_return()` calls `validate_cancellation()` then posts an equal-and-opposite `SALE_RETURN_CANCEL` movement -- `sale_return_item` rows are never touched |
| Soft-delete only for Draft; Posted/Cancelled are never deleted | `delete_draft()` explicitly checks `status == 'Draft'` and raises `ValidationError` otherwise |

---

**Part 2 complete.** Waiting for your confirmation before Part 3 (Screens: `sale_return_form_screen.py` with the two-combo Invoice→returnable-lines picker, `sale_return_list_screen.py`, wiring checklist, and the updated Combined Purchase+Sale+SaleReturn Blueprint JSON).
