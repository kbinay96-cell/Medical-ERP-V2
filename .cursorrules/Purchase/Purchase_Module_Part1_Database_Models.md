# Purchase Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Depends on (already built, confirmed from real files):**
- `engines/date_engine.py` — BS↔AD conversion (ad_to_bs, DateEngineError)
- `engines/supplier_engine.py` / `models/supplier_model.py` — supplier lookup
- `engines/item_engine.py` / `models/item_model.py` — Item, ItemBatch, StockLedger
- `engines/country_tax_engine.py` — vat_percent/custom_percent lookup
- `engines/manufacturer_engine.py` — manufacturer's country
- `engines/exceptions.py` — EngineError, ValidationError, RecordNotFoundError, DuplicateRecordError

---

## 0. Scope — CONFIRMED (Bijay ke inputs se, `project_context.txt` se column names verify kiye)

1. **Purchase Order (PO)** — **Phase-1 core feature.** Auto low-stock detection + manual add/remove + WhatsApp/Email link — sab is phase mein banega.
2. **Purchase Return** — Phase-2 (baad mein).
3. **Column names verified from uploaded `project_context.txt`** (guess nahi kiya):
   - `item.minimum_stock` — `NUMERIC(18,2) NOT NULL DEFAULT 0` (source: `schema_item.sql`)
   - `supplier.mobile_no` — `VARCHAR(20)`, `supplier.email` — `VARCHAR(150)` (source: `schema_supplier.sql`)
4. **Partial Receipt tracking** aur **Preferred Supplier per Item** — SKIP kiya (Bijay ne mana kiya). PO status sirf simple rahega: `Draft → Sent → Received → Cancelled` — jab bhi koi Purchase Invoice is PO ko reference kare, poora PO `Received` mark ho jayega (partial-fulfillment ka alag tracking nahi banayenge).
5. **Email mode** — Phase-1 mein `mailto:` link (zero setup, manual click-to-send). SMTP auto-send future upgrade rahega (`purchase.email_send_mode` setting already future-ready rakha hai).

---

## 1. Database Schema

### 1.1 `purchase_order` (Phase-1 — core, with auto low-stock + manual items)

```sql
CREATE TABLE IF NOT EXISTS purchase_order (
    purchase_order_id   SERIAL PRIMARY KEY,
    po_number           VARCHAR(30) NOT NULL UNIQUE,
    supplier_id         INTEGER NOT NULL REFERENCES supplier(supplier_id),
    order_date_ad       DATE NOT NULL,
    order_date_bs       VARCHAR(10) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'Draft',  -- Draft, Sent, Received, Cancelled
    -- NOTE: 'Received' is set on the WHOLE PO the moment any Purchase
    -- Invoice references it (purchase_invoice.purchase_order_id) — no
    -- partial-fulfillment tracking per Bijay's confirmed scope.
    sent_via            VARCHAR(20),        -- 'whatsapp' | 'email' | NULL (not sent yet)
    sent_at_ad          TIMESTAMP,
    remarks             TEXT,
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_by          INTEGER NOT NULL,
    created_at_ad       TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs       VARCHAR(10) NOT NULL,
    updated_by          INTEGER,
    updated_at_ad       TIMESTAMP,
    updated_at_bs       VARCHAR(10),
    deleted_by          INTEGER,
    deleted_at_ad       TIMESTAMP,
    deleted_at_bs       VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS purchase_order_item (
    po_item_id          SERIAL PRIMARY KEY,
    purchase_order_id   INTEGER NOT NULL REFERENCES purchase_order(purchase_order_id),
    item_id             INTEGER NOT NULL REFERENCES item(item_id),
    ordered_qty          NUMERIC(12,2) NOT NULL,
    rate                  NUMERIC(12,2) NOT NULL DEFAULT 0,   -- estimated/last purchase rate, optional
    is_auto_suggested       BOOLEAN NOT NULL DEFAULT FALSE,     -- true = came from low-stock auto-detection
    stock_at_order_time       NUMERIC(18,2),                     -- snapshot: item's total_stock when added to this PO (audit trail — "why was this suggested")
    minimum_stock_at_order_time NUMERIC(18,2),
    remarks                    TEXT
);

CREATE INDEX IF NOT EXISTS idx_po_item_item_id ON purchase_order_item (item_id);
-- Used by the "already ordered elsewhere?" duplicate-check query — finds
-- open (Draft/Sent) POs for a given item_id across ALL suppliers.
```

> **Auto low-stock detection is a LIVE QUERY, not a stored queue.** No new table needed for "which items are low" — `models/item_model.py` gets one new method (`get_low_stock_items()`, see Section 2.3) that compares `item.minimum_stock` against `ItemModel.get_total_stock(item_id)` (already exists) at the moment the Purchase Order screen opens. This satisfies Bijay's rule: *"jab tak stock update na ho, item PO-suggestion list mein rehta hai"* — because the query re-runs live every time, it will keep showing the item until real stock (via a posted Purchase Invoice) crosses `minimum_stock` again.

### 1.2 `purchase_invoice` (Phase-1 — core table, GRN + Bill combined)

```sql
CREATE TABLE IF NOT EXISTS purchase_invoice (
    purchase_invoice_id SERIAL PRIMARY KEY,
    invoice_number      VARCHAR(30) NOT NULL,          -- supplier's bill number
    internal_ref_number VARCHAR(30) NOT NULL UNIQUE,   -- our own sequential code, e.g. PINV-0001
    supplier_id         INTEGER NOT NULL REFERENCES supplier(supplier_id),
    purchase_order_id   INTEGER REFERENCES purchase_order(purchase_order_id),  -- nullable (invoice can exist without a PO), links to Phase-1 PO when order was placed via system
    invoice_date_ad      DATE NOT NULL,
    invoice_date_bs      VARCHAR(10) NOT NULL,
    total_qty            NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount    NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(qty * purchase_rate) before discount/cc
    total_discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount        NUMERIC(14,2) NOT NULL DEFAULT 0,   -- customs charge on free goods (see glossary)
    total_freight_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_other_charges    NUMERIC(14,2) NOT NULL DEFAULT 0,
    grand_total             NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc + freight + other
    status                VARCHAR(20) NOT NULL DEFAULT 'Posted', -- Draft, Posted, Cancelled
    remarks               TEXT,
    is_deleted            BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INTEGER NOT NULL,
    created_at_ad         TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs         VARCHAR(10) NOT NULL,
    updated_by            INTEGER,
    updated_at_ad         TIMESTAMP,
    updated_at_bs         VARCHAR(10),
    deleted_by            INTEGER,
    deleted_at_ad         TIMESTAMP,
    deleted_at_bs         VARCHAR(10)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_purchase_invoice_supplier_billno
    ON purchase_invoice (supplier_id, invoice_number)
    WHERE is_deleted = FALSE;
    -- Same supplier, same bill number dobara enter na ho (duplicate bill safety)
```

### 1.3 `purchase_invoice_item` (line items — one row per batch)

```sql
CREATE TABLE IF NOT EXISTS purchase_invoice_item (
    purchase_invoice_item_id SERIAL PRIMARY KEY,
    purchase_invoice_id      INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    item_id                  INTEGER NOT NULL REFERENCES item(item_id),
    batch_no                 VARCHAR(50) NOT NULL,
    expiry_month              SMALLINT NOT NULL,
    expiry_year                SMALLINT NOT NULL,
    qty                        NUMERIC(12,2) NOT NULL,       -- paid quantity
    free_qty                   NUMERIC(12,2) NOT NULL DEFAULT 0,
    purchase_rate               NUMERIC(12,2) NOT NULL,        -- per unit, paid qty only (free qty rate is always 0 — see glossary)
    discount_percent             NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount               NUMERIC(12,2) NOT NULL DEFAULT 0,
    cc_percent                     NUMERIC(5,2) NOT NULL DEFAULT 0,   -- from country_tax.custom_percent (manufacturer's country)
    cc_amount                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- computed on free_qty * declared customs value/unit
    freight_amount_allocated         NUMERIC(12,2) NOT NULL DEFAULT 0,   -- this line's share of invoice-level freight
    other_charges_allocated           NUMERIC(12,2) NOT NULL DEFAULT 0,
    landing_cost_per_unit               NUMERIC(12,4) NOT NULL DEFAULT 0,  -- OUTPUT only, never an input (see glossary)
    mrp                                  NUMERIC(12,2) NOT NULL,
    sale_rate                             NUMERIC(12,2) NOT NULL DEFAULT 0,
    item_batch_id                         INTEGER REFERENCES item_batch(item_batch_id),  -- filled after ItemEngine.add_batch() succeeds
    remarks                                TEXT
);
```

### 1.4 `purchase_return` (Phase-2, optional)

```sql
CREATE TABLE IF NOT EXISTS purchase_return (
    purchase_return_id   SERIAL PRIMARY KEY,
    return_number         VARCHAR(30) NOT NULL UNIQUE,
    purchase_invoice_id   INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    supplier_id            INTEGER NOT NULL REFERENCES supplier(supplier_id),
    return_date_ad          DATE NOT NULL,
    return_date_bs           VARCHAR(10) NOT NULL,
    total_amount              NUMERIC(14,2) NOT NULL DEFAULT 0,
    reason                     TEXT,
    status                     VARCHAR(20) NOT NULL DEFAULT 'Posted',
    is_deleted                 BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                 INTEGER NOT NULL,
    created_at_ad               TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                 VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_return_item (
    purchase_return_item_id  SERIAL PRIMARY KEY,
    purchase_return_id        INTEGER NOT NULL REFERENCES purchase_return(purchase_return_id),
    item_batch_id               INTEGER NOT NULL REFERENCES item_batch(item_batch_id),
    return_qty                    NUMERIC(12,2) NOT NULL,
    return_rate                    NUMERIC(12,2) NOT NULL,
    remarks                         TEXT
);
```

> **Note:** `item_batch_id` link Purchase Invoice Item se hota hai — is table mein khud koi qty column nahi hai (project rule: stock sirf `item_batch` mein). Purchase Engine batch create karne ke liye **existing `ItemEngine.add_batch()`** call karega — naya stock-writing code nahi likhna.

---

## 2. Models Layer (SQL only — `models/purchase_model.py`, `models/purchase_order_model.py`)

### 2.1 File: `models/purchase_invoice_model.py`

```python
# models/purchase_invoice_model.py
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class PurchaseInvoiceSearchFilters:
    search_text: Optional[str] = None
    supplier_id: Optional[int] = None
    status: Optional[str] = None
    date_from_ad: Optional[str] = None
    date_to_ad: Optional[str] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class PurchaseInvoiceModel:
    """Data-access layer for `purchase_invoice` + `purchase_invoice_item`.
    SQL only, no business logic — mirrors models/supplier_model.py shape."""

    def insert_invoice(self, data: dict[str, Any]) -> int:
        """Inserts one purchase_invoice header row. `data` must contain every
        column this INSERT expects (Engine's job to fill defaults/audit stamps).
        Returns new purchase_invoice_id."""
        ...

    def insert_invoice_item(self, purchase_invoice_id: int, data: dict[str, Any]) -> int:
        """Inserts one purchase_invoice_item row. Returns new purchase_invoice_item_id."""
        ...

    def update_invoice_item_batch_link(self, purchase_invoice_item_id: int, item_batch_id: int) -> None:
        """After ItemEngine.add_batch() succeeds, stamps the resulting item_batch_id
        back onto the invoice line — so the line is traceable to its stock batch."""
        ...

    def get_by_id(self, purchase_invoice_id: int, include_deleted: bool = False) -> Optional[dict]:
        ...

    def get_items_by_invoice(self, purchase_invoice_id: int) -> list[dict]:
        ...

    def exists_by_supplier_and_billno(self, supplier_id: int, invoice_number: str, exclude_id: Optional[int] = None) -> bool:
        """Duplicate-bill safety check — same supplier + same bill number."""
        ...

    def get_last_internal_ref_sequence(self, prefix: str) -> int:
        """Highest numeric suffix among internal_ref_number starting with `prefix`
        (e.g. PINV-) — same pattern as SupplierModel.get_last_code_sequence()."""
        ...

    def search(self, filters: PurchaseInvoiceSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) with supplier_name joined in for List screen."""
        ...

    def soft_delete(self, purchase_invoice_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> None:
        ...
```

### 2.2 File: `models/purchase_order_model.py` (Phase-1 — full detail)

```python
# models/purchase_order_model.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PurchaseOrderSearchFilters:
    search_text: Optional[str] = None
    supplier_id: Optional[int] = None
    status: Optional[str] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class PurchaseOrderModel:
    """Data-access layer for `purchase_order` + `purchase_order_item`.
    SQL only, no business logic — mirrors PurchaseInvoiceModel shape."""

    def insert_order(self, data: dict[str, Any]) -> int:
        """Inserts one purchase_order header row. Returns new purchase_order_id."""
        ...

    def insert_order_item(self, purchase_order_id: int, data: dict[str, Any]) -> int:
        """Inserts one purchase_order_item row (manual OR auto-suggested —
        `is_auto_suggested` flag distinguishes them, both stored the same way)."""
        ...

    def get_by_id(self, purchase_order_id: int, include_deleted: bool = False) -> Optional[dict]:
        ...

    def get_items_by_order(self, purchase_order_id: int) -> list[dict]:
        ...

    def get_open_order_items_for_item_ids(self, item_ids: list[int]) -> list[dict]:
        """Returns rows {item_id, po_id, po_number, supplier_name, ordered_qty,
        status} for any item currently sitting in a Draft/Sent PO (any
        supplier). Used by the Engine to build the 'Already ordered in
        PO-0012 (Sent) — order again?' warning shown on the auto-suggest
        screen. Does NOT block — just informs."""
        ...

    def get_last_po_number_sequence(self, prefix: str) -> int:
        """Same pattern as SupplierModel.get_last_code_sequence()."""
        ...

    def search(self, filters: PurchaseOrderSearchFilters) -> tuple[list[dict], int]:
        """Returns (rows, total_count) with supplier_name joined in."""
        ...

    def mark_status(self, purchase_order_id: int, status: str, updated_by: int,
                     updated_at_ad, updated_at_bs: str) -> None:
        """Sets status to 'Sent' (after WhatsApp/Email link opened),
        'Received' (called by PurchaseEngine once an invoice references this
        PO), or 'Cancelled'."""
        ...

    def soft_delete(self, purchase_order_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> None:
        ...
```

### 2.2.1 New method needed on EXISTING `models/item_model.py` (extension, not a new file)

Per project rule ("No SQL outside the Model"), item-table queries belong in `ItemModel` — a purchase-module file must NOT query the `item` table directly. So `ItemModel` (already built) gets **one new method** added:

```python
# ADDITION to models/item_model.py — class ItemModel

    def get_low_stock_items(self) -> list[dict]:
        """Returns every active, non-deleted item where
        SUM(item_batch.batch_qty) <= item.minimum_stock, along with the
        current total_stock and minimum_stock values (for display and for
        stock_at_order_time/minimum_stock_at_order_time snapshotting).
        This is a LIVE query — no caching, no stored 'queue' table. Called
        fresh every time the Purchase Order auto-suggest screen opens."""
        ...
```

### 2.3 File: `models/purchase_return_model.py` (Phase-2)

Same shape, for `purchase_return` / `purchase_return_item` — `insert`, `get_by_id`, `search`, `get_by_invoice`.

---

## 4. Settings Seed (add to `database/schema_auth.sql`'s existing settings INSERT block, or a new small migration — same `ON CONFLICT ... DO NOTHING` pattern already used for `customer.code_prefix` / `manufacturer.code_prefix`)

```sql
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    ('purchase.po_prefix', 'PO-', 'Purchase', 'string', 'PO-', 'Prefix for auto-generated Purchase Order numbers', 10),
    ('purchase.invoice_prefix', 'PINV-', 'Purchase', 'string', 'PINV-', 'Prefix for auto-generated Purchase Invoice internal reference numbers', 20),
    ('purchase.return_prefix', 'PRET-', 'Purchase', 'string', 'PRET-', 'Prefix for auto-generated Purchase Return numbers (Phase-2)', 30),
    ('purchase.reorder_target_multiplier', '2', 'Purchase', 'decimal', '2', 'Suggested reorder qty = (minimum_stock x multiplier) - current_stock', 40),
    ('purchase.whatsapp_message_template', 'Hello {supplier_name}, please arrange the following items:\n{item_list}\n\nRegards, {company_name}', 'Purchase', 'string', 'Hello {supplier_name}, please arrange the following items:\n{item_list}\n\nRegards, {company_name}', 'WhatsApp order message template. Placeholders: {supplier_name} {po_number} {item_list} {company_name}', 50),
    ('purchase.email_subject_template', 'Purchase Order - {po_number}', 'Purchase', 'string', 'Purchase Order - {po_number}', 'Email subject template for Purchase Orders', 60),
    ('purchase.email_body_template', 'Dear {supplier_name},\n\nPlease find our purchase order below:\n{item_list}\n\nRegards,\n{company_name}', 'Purchase', 'string', 'Dear {supplier_name},\n\nPlease find our purchase order below:\n{item_list}\n\nRegards,\n{company_name}', 'Email body template for Purchase Orders', 70),
    ('purchase.email_send_mode', 'mailto', 'Purchase', 'string', 'mailto', 'mailto = opens default email client (manual send, zero setup) | smtp = auto-send (future, needs SMTP credentials)', 80)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;
```

> Ye settings automatically Settings screen mein **"Purchase"** group tile ke roop mein dikhengi (jaisa `settings_engine.get_settings_grouped()` sab groups ko auto-discover karta hai) — koi alag Settings-UI code nahi likhna padega.

---

## 3. Imports Reference (Part-1 files)

```python
# models/purchase_invoice_model.py
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Optional
# lazy imports inside functions: database.db.get_connection, psycopg2.extras
```

No other project-internal imports needed at Model layer (per rule: Models only touch DB, never call Engines).

---

**Part 1 complete.** Part 2 covers Engines + Validators + DTOs + business rules (CC calc, landing cost, stock creation via ItemEngine).
