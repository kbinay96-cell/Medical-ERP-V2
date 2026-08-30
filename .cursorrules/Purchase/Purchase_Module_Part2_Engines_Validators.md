# Purchase Module — Part 2: Engines, Validators, Business Rules

**Layer:** Engines (business logic) + Validators (pure checks) — per project rule
**Golden rule reused from `item_engine.py`:** Purchase Engine does **NOT** write to `item_batch` or `stock_ledger` directly. It calls the already-built `ItemEngine.add_batch(item_id, batch_payload, current_user_id, transaction_type='PURCHASE', reference_type='purchase_invoice', reference_id=purchase_invoice_id)` — this is explicitly documented as the intended future caller in `engines/item_engine.py`'s own docstring. **No duplicate stock-writing logic.**

---

## 1. `engines/purchase_validator.py`

Pure logic, no DB — mirrors `engines/customer_validator.py` / `utils/item_validator.py` shape.

```python
# engines/purchase_validator.py
from __future__ import annotations
from typing import Any


class PurchaseValidator:
    """Validates a Purchase Invoice payload BEFORE it reaches the Engine's
    save logic. Pure logic — no DB, no UI. Uniqueness (supplier+billno) is
    NOT checked here (needs a DB round-trip) — the Engine checks that via
    PurchaseInvoiceModel.exists_by_supplier_and_billno()."""

    @staticmethod
    def validate_invoice_header(data: dict[str, Any]) -> tuple[bool, str]:
        """Checks: supplier_id present, invoice_number non-empty,
        invoice_date_bs valid format, at least one line item present.
        Returns (is_valid, error_message)."""
        ...

    @staticmethod
    def validate_invoice_line(line: dict[str, Any]) -> tuple[bool, str]:
        """Checks per line: item_id present, qty > 0 OR free_qty > 0
        (both cannot be zero), purchase_rate >= 0, discount_percent in
        [0,100], expiry_month in [1,12], expiry_year plausible (>= current
        BS year), mrp >= 0, batch_no non-empty."""
        ...

    @staticmethod
    def validate_free_qty_rate(line: dict[str, Any]) -> tuple[bool, str]:
        """Business rule (glossary): free_qty lines MUST have purchase_rate
        contribution of 0 for that portion — this checks the payload isn't
        trying to price free units."""
        ...


class PurchaseOrderValidator:
    """Validates a Purchase Order payload — pure logic, no DB."""

    @staticmethod
    def validate_order_header(data: dict[str, Any]) -> tuple[bool, str]:
        """Checks: supplier_id present, order_date_bs valid, at least one
        line item present (manual or auto-suggested)."""
        ...

    @staticmethod
    def validate_order_line(line: dict[str, Any]) -> tuple[bool, str]:
        """Checks: item_id present, ordered_qty > 0. rate is optional
        (estimate only, not enforced)."""
        ...
```

---

## 2. `engines/purchase_engine.py`

### 2.1 DTOs

```python
# engines/purchase_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.purchase_invoice_model import PurchaseInvoiceModel, PurchaseInvoiceSearchFilters
from engines.purchase_validator import PurchaseValidator

logger = logging.getLogger(__name__)


@dataclass
class PurchaseInvoiceLineDTO:
    item_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    qty: float
    free_qty: float
    purchase_rate: float
    discount_percent: float
    cc_percent: float
    mrp: float
    sale_rate: float
    # computed/output fields (Engine fills these, never accepted as input):
    discount_amount: float = 0.0
    cc_amount: float = 0.0
    landing_cost_per_unit: float = 0.0
    item_batch_id: Optional[int] = None


@dataclass
class PurchaseInvoiceDTO:
    purchase_invoice_id: Optional[int]
    internal_ref_number: str
    invoice_number: str
    supplier_id: int
    invoice_date_bs: str
    grand_total: float
    status: str
    lines: list[PurchaseInvoiceLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
```

### 2.2 `PurchaseEngine` class — method list with responsibilities

```python
class PurchaseEngine:
    """Business-rule orchestration for Purchase Invoice (GRN + Bill combined).
    Screens call ONLY this class — mirrors SupplierEngine/ItemEngine shape."""

    def __init__(self, model, date_engine, settings_engine, item_engine, purchase_order_engine,
                 country_tax_lookup_fn, manufacturer_lookup_fn) -> None:
        """item_engine: an ItemEngine instance — Purchase Engine delegates
        all stock/batch writes to it, never touches item_batch/stock_ledger
        itself. purchase_order_engine: injected so create_purchase_invoice()
        can mark a linked PO 'Received' — Purchase Invoice Engine never
        touches the purchase_order table directly."""
        ...

    def generate_internal_ref_number(self) -> str:
        """Next sequential PINV-0001, PINV-0002... Settings-driven prefix,
        same pattern as ItemEngine.generate_item_code()."""
        ...

    def _resolve_cc_percent(self, item_id: int) -> float:
        """Looks up the item's manufacturer -> manufacturer's country ->
        country_tax.custom_percent, via the SAME lookup chain ItemEngine
        already uses for resolve_item_tax(). Never raises — unresolved
        country/tax = 0.0, per the existing (0,0) fallback rule."""
        ...

    def _calculate_line_amounts(self, line: PurchaseInvoiceLineDTO) -> PurchaseInvoiceLineDTO:
        """Pure calculation, no DB writes:
        1. discount_amount = qty * purchase_rate * (discount_percent / 100)
        2. cc_amount = free_qty * declared_customs_value_per_unit * (cc_percent / 100)
           -- declared_customs_value_per_unit is the item's purchase_rate
              of the PAID units on this same line (free qty's own rate is
              always 0 by definition, per glossary — so CC basis is the
              paid-unit rate, applied only to the free-qty count).
        3. landing_cost_per_unit = OUTPUT ONLY:
           ((qty * purchase_rate) - discount_amount + cc_amount
            + freight_allocated + other_charges_allocated) / (qty + free_qty)
           -- never used as an input to any other calculation (glossary rule).
        Returns the line with all computed fields filled in."""
        ...

    def _allocate_invoice_level_charges(
        self, lines: list[PurchaseInvoiceLineDTO], total_freight: float, total_other: float
    ) -> list[PurchaseInvoiceLineDTO]:
        """Splits invoice-level freight/other-charges across lines,
        proportional to each line's (qty + free_qty) share of total units.
        Must run BEFORE _calculate_line_amounts's landing_cost step."""
        ...

    def create_purchase_invoice(self, payload: dict[str, Any], current_user_id: int) -> PurchaseInvoiceDTO:
        """Full flow:
        1. PurchaseValidator.validate_invoice_header() + validate_invoice_line() per line
        2. Duplicate check: model.exists_by_supplier_and_billno()
        3. Resolve CC% per line (_resolve_cc_percent)
        4. Allocate freight/other charges (_allocate_invoice_level_charges)
        5. Calculate amounts per line (_calculate_line_amounts)
        6. Insert purchase_invoice header (model.insert_invoice)
        7. For each line: insert purchase_invoice_item, THEN call
           self._item_engine.add_batch(item_id, batch_payload, current_user_id,
               transaction_type='PURCHASE', reference_type='purchase_invoice',
               reference_id=new_invoice_id)
           -- this is what actually creates the item_batch + stock_ledger row.
        8. Stamp resulting item_batch_id back via model.update_invoice_item_batch_link()
        9. If payload includes purchase_order_id: calls
           self._purchase_order_engine.mark_received(purchase_order_id, current_user_id)
           -- marks the WHOLE linked PO as 'Received' (no partial tracking,
           per confirmed scope). purchase_order_id stays optional — an
           invoice can be created without ever referencing a PO.
        10. Stamps BS-first audit fields via self._date_engine, same pattern
           as SupplierEngine._now_bs()/_now_ad()
        Raises ValidationError, DuplicateRecordError."""
        ...

    def get_purchase_invoice(self, purchase_invoice_id: int, include_deleted: bool = False) -> PurchaseInvoiceDTO:
        ...

    def search_purchase_invoices(self, search_text=None, supplier_id=None, status=None,
                                   include_deleted=False, page=1, page_size=50) -> tuple[list[PurchaseInvoiceDTO], int]:
        ...

    def cancel_purchase_invoice(self, purchase_invoice_id: int, current_user_id: int, reason: str) -> None:
        """Soft-delete only (project rule: no physical DELETE). Does NOT
        automatically reverse the stock_ledger entries — that reversal is a
        separate, explicit Purchase Return flow (Part-2, section 3), never
        an implicit side-effect of cancelling an invoice."""
        ...
```

> **Why CC/landing-cost logic lives in the Engine, not the Model or Screen:** Per `architecture_rules` in `projects/medical_erp_v2.json` — "Business logic only inside Engines." The Screen only collects raw input (qty, rate, discount%) and displays the Engine's computed output; the Model only persists whatever dict the Engine hands it.

---

## 3. `engines/purchase_order_engine.py` (Phase-1 — auto low-stock detection, duplicate-check, WhatsApp/Email text)

```python
# engines/purchase_order_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_order_model import PurchaseOrderModel, PurchaseOrderSearchFilters
from models.item_model import ItemModel
from engines.purchase_validator import PurchaseOrderValidator

logger = logging.getLogger(__name__)


@dataclass
class LowStockSuggestionDTO:
    """One row for the auto-suggest screen."""
    item_id: int
    item_name: str
    current_stock: float
    minimum_stock: float
    suggested_qty: float          # (minimum_stock * reorder_multiplier) - current_stock
    already_ordered_elsewhere: list[dict] = field(default_factory=list)
    # e.g. [{"po_number": "PO-0012", "supplier_name": "Sun Pharma", "status": "Sent", "ordered_qty": 50}]


@dataclass
class PurchaseOrderLineDTO:
    item_id: int
    ordered_qty: float
    rate: float = 0.0
    is_auto_suggested: bool = False
    stock_at_order_time: Optional[float] = None
    minimum_stock_at_order_time: Optional[float] = None


@dataclass
class PurchaseOrderDTO:
    purchase_order_id: Optional[int]
    po_number: str
    supplier_id: int
    order_date_bs: str
    status: str
    sent_via: Optional[str]
    lines: list[PurchaseOrderLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class PurchaseOrderEngine:
    """Business-rule orchestration for Purchase Orders — auto low-stock
    suggestion, manual add/remove, duplicate-order warning, WhatsApp/Email
    message building. Screens call ONLY this class."""

    def __init__(self, model: PurchaseOrderModel, item_model: ItemModel,
                 date_engine, settings_engine) -> None:
        ...

    def generate_po_number(self) -> str:
        """Next sequential PO-0001, PO-0002... Settings-driven
        (purchase.po_prefix), same pattern as ItemEngine.generate_item_code()."""
        ...

    def get_low_stock_suggestions(self) -> list[LowStockSuggestionDTO]:
        """LIVE query, called fresh every time the PO screen opens:
        1. self._item_model.get_low_stock_items() -> raw low-stock rows
        2. self._model.get_open_order_items_for_item_ids([...]) -> duplicate
           warnings, attached per item
        3. suggested_qty = (minimum_stock * settings.purchase.reorder_target_multiplier)
           - current_stock, floored at 0
        Never raises — an item stays in this list until its real stock
        (via a posted Purchase Invoice) rises back above minimum_stock,
        because this is a live comparison, not a stored flag."""
        ...

    def create_purchase_order(self, payload: dict[str, Any], current_user_id: int) -> PurchaseOrderDTO:
        """Validates header + each line (PurchaseOrderValidator), inserts
        purchase_order + purchase_order_item rows (both manual and
        auto-suggested lines saved the same way, is_auto_suggested flag
        just for audit/reporting). Does NOT touch item_batch/stock —
        a PO is a request, not a stock movement."""
        ...

    def build_supplier_message(self, purchase_order_id: int) -> dict[str, str]:
        """Reads Settings templates (purchase.whatsapp_message_template,
        purchase.email_subject_template, purchase.email_body_template),
        fills in {supplier_name}, {po_number}, {item_list}, {company_name}
        placeholders using the PO's actual lines + item names + company
        name (from Settings' existing company.name key). Returns:
        {"whatsapp_text": "...", "email_subject": "...", "email_body": "..."}
        Pure text building — no webbrowser/UI calls here (Screen's job)."""
        ...

    def mark_sent(self, purchase_order_id: int, sent_via: str, current_user_id: int) -> None:
        """sent_via = 'whatsapp' | 'email'. Called by the Screen right after
        the wa.me/mailto link is opened. Sets status='Sent' if it was
        'Draft'."""
        ...

    def mark_received(self, purchase_order_id: int, current_user_id: int) -> None:
        """Called by PurchaseEngine.create_purchase_invoice() when an
        invoice references this PO. Sets status='Received' — whole PO,
        no partial tracking (confirmed scope)."""
        ...

    def get_purchase_order(self, purchase_order_id: int, include_deleted: bool = False) -> PurchaseOrderDTO:
        ...

    def search_purchase_orders(self, search_text=None, supplier_id=None, status=None,
                                 include_deleted=False, page=1, page_size=50) -> tuple[list[PurchaseOrderDTO], int]:
        ...

    def cancel_purchase_order(self, purchase_order_id: int, current_user_id: int) -> None:
        """Soft-delete only. An item on a cancelled PO reappears in
        get_low_stock_suggestions() next time (if still genuinely low),
        since that query ignores cancelled/deleted POs by design."""
        ...
```

> **WhatsApp/Email — zero API cost, confirmed approach:** No WhatsApp Business API, no SMTP server required for Phase-1. `build_supplier_message()` only builds text; the **Screen** (`purchase_order_list_screen.py`, Part-3) turns `whatsapp_text` into a `https://wa.me/{mobile_no}?text={urlencoded_text}` URL and `email_subject`/`email_body` into a `mailto:{email}?subject=...&body=...` URL, then calls Python's built-in `webbrowser.open(url)` — opens WhatsApp Web/App or the user's default email client with everything pre-filled. Zero paid service, zero credentials needed.

---

## 4. `engines/purchase_return_engine.py` (Phase-2 — build only after Purchase Invoice/Order are live and tested)

```python
# engines/purchase_return_engine.py

class PurchaseReturnEngine:
    def __init__(self, model, date_engine, item_engine) -> None: ...

    def create_return(self, payload: dict, current_user_id: int) -> dict:
        """Validates return_qty <= remaining batch_qty for the referenced
        item_batch_id, then calls self._item_engine.post_stock_movement(
            item_batch_id, transaction_type='PURCHASE_RETURN',
            quantity_change=-return_qty, ...)
        -- reuses ItemEngine.post_stock_movement(), which is ALREADY built
        for exactly this future case (see its docstring in item_engine.py:
        'negative = stock OUT ... a Purchase Return')."""
        ...
```

---

## 5. Full Import List (Part-2 files)

```python
# engines/purchase_validator.py
from __future__ import annotations
from typing import Any

# engines/purchase_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.purchase_invoice_model import PurchaseInvoiceModel, PurchaseInvoiceSearchFilters
from engines.purchase_validator import PurchaseValidator
# lazy-loaded inside functions (same defensive pattern as manufacturer_engine.py):
#   engines.date_engine (ad_to_bs, DateEngineError)
#   engines.settings_engine (get_setting)
#   engines.item_engine (ItemEngine) -- injected via constructor, not imported directly
#   engines.purchase_order_engine (PurchaseOrderEngine) -- injected via constructor
#   engines.item_lookup_registry (manufacturer_lookup, country_tax_lookup)

# engines/purchase_order_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_order_model import PurchaseOrderModel, PurchaseOrderSearchFilters
from models.item_model import ItemModel
from engines.purchase_validator import PurchaseOrderValidator
# lazy-loaded inside functions:
#   engines.date_engine (ad_to_bs, DateEngineError)
#   engines.settings_engine (get_setting)

# engines/purchase_return_engine.py (Phase-2)
from __future__ import annotations
from typing import Any
from models.purchase_return_model import PurchaseReturnModel
```

---

**Part 2 complete.** Part 3 covers Screens, the ERP-AI-Tool blueprint JSON (for auto-progress tracking), and the exact **Apply Code format** to hand any of this code back into ERP-AI-Tool.
