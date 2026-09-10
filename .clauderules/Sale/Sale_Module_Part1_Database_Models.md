# Sale Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Depends on (already built, confirmed from real files):**
- `engines/date_engine.py` — BS↔AD conversion (ad_to_bs, DateEngineError)
- `engines/customer_engine.py` / `models/customer_model.py` — customer + area lookup
- `engines/item_engine.py` / `models/item_model.py` — Item, ItemBatch, StockLedger, `resolve_item_tax()`, `post_stock_movement()`
- `engines/country_tax_engine.py` — `custom_percent` lookup (for CC on Free Goods)
- `engines/manufacturer_engine.py` — manufacturer's country
- `engines/exceptions.py` — EngineError, ValidationError, RecordNotFoundError, DuplicateRecordError
- `engines/settings_engine.py` — column show/hide + free-scheme toggles

---

## 0. Scope — CONFIRMED (from discussion with Bijay)

1. **Sale Invoice** — Phase-1 core feature.
2. **Sale Order** (quotation/booking, no stock impact) — Phase-2.
3. **Sale Return** — Phase-3.
4. **Receipt / Payment** — built as a **separate, standalone Accounts module** (Option A), NOT inside Sale module. Sale Invoice only *records* what is owed; Receipt separately reduces the customer's running balance. Same Accounts module will later handle Purchase Payments too (shared table shape, `direction` column distinguishes Receipt vs Payment). This blueprint reserves the `receipt_payment` table shape here for reference only — full Accounts Engine/Screens come in their own future blueprint.
5. **Area → Customer two-combo search**, confirmed. Area selected first, Customer combo filtered to that `area_id`.
6. **Column visibility is fully Settings-driven** except **Qty**, which is always visible/compulsory. Whatever columns are visible in the entry table are exactly what prints on the invoice (single source of truth — no separate "print template" column list).
7. **Free Qty column visible = Wholesale mode.** Free Qty column hidden = Retail mode — free-scheme logic does not run at all in Retail mode (no computation, no CC).
8. **Free Scheme** — new reusable master `item_free_scheme`, ratio-based (`scheme_qty` + `scheme_free`, e.g. "5+1"). Same design pattern as `supplier_manufacturer_discount`.
9. **Two entry modes per line, user-togglable:** **Free Qty mode** (paid qty + free qty shown separately, free auto-suggested from scheme, minimum 1 to auto-fill) vs **Net Rate mode** (single blended qty, rate auto-reduced to reflect the free benefit — `Net Rate = Current Rate × scheme_qty ÷ (scheme_qty + scheme_free)`). Both editable.
10. **Batch + Expiry are READ-ONLY** in Sale Invoice — system auto-picks nearest-expiry batch via existing `ItemEngine.get_batches()` (already expiry-ascending). No manual batch override in Sale (unlike Purchase, where batches are created).
11. **CC on Free Goods** — applies in Wholesale mode only, calculated on **Purchase Rate** (the item's cost, NOT MRP): `CC Amount = free_qty × item_purchase_rate_at_time × manufacturer_country_custom_percent ÷ 100`. Mirrors the exact Purchase-side CC concept, reused via `country_tax_engine`/`manufacturer_engine`, applied on the Sale side to free goods given out.
12. **Row-level inline item entry** — every grid row's Item cell is itself a searchable, type-ahead combo (mirrors `utils/combo_helpers.make_searchable`, adapted for an in-table cell). Selecting an item in the last row auto-appends a new empty row (Excel-style continuous entry). A conventional "+ Add Item" header-level control also remains available, mirroring the Purchase Invoice screen.
13. **Payment Type on invoice (Cash/Credit split at invoice time only)** — fixed list: `Cash | Bank | eSewa | Khalti | IPS`. This is captured at Sale Invoice save time (how much of this bill, if any, was paid immediately) — NOT the same as the standalone Receipt module (item 4 above), which handles later/partial/multi-invoice collections.
14. Column names verified from uploaded `project_context.txt` (no guessing):
    - `customer.area_id`, `customer.price_level_id`, `customer.credit_limit`, `customer.opening_balance`, `customer.balance_type` (source: `schema_customer.sql`)
    - `item.purchase_rate`, `item.sale_rate`, `item.mrp` (source: `schema_item.sql`)
    - `item_batch.batch_no`, `expiry_year`, `expiry_month`, `expiry_display` (generated column) (source: `schema_item.sql`)
    - `manufacturer.country` (source: `schema_manufacturer.sql`)
    - `country_tax.custom_percent` (source: `0004_create_country_tax.sql`)

---

## 1. Database Schema

### 1.1 `sale_invoice` (Phase-1 — core header table)

```sql
CREATE TABLE IF NOT EXISTS sale_invoice (
    sale_invoice_id       SERIAL PRIMARY KEY,
    invoice_number        VARCHAR(30) NOT NULL UNIQUE,     -- our own sequential code, e.g. SINV-0001
    customer_id            INTEGER NOT NULL REFERENCES customers(customer_id),
    area_id                 INTEGER REFERENCES areas(area_id),   -- snapshot of customer's area at sale time (area may change later on customer master; invoice keeps its own record)
    price_level_id           INTEGER REFERENCES price_levels(price_level_id),  -- snapshot from customer at sale time
    invoice_date_ad           DATE NOT NULL,
    invoice_date_bs            VARCHAR(10) NOT NULL,       -- "Invoice Miti" per the reference bill — BS is primary
    sale_mode                   VARCHAR(20) NOT NULL DEFAULT 'Retail',  -- 'Retail' | 'Wholesale' -- derived from whether Free column was enabled for this invoice; stored so historical invoices remain correctly interpreted even if the Setting changes later
    total_qty                    NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_free_qty                 NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount              NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(qty * rate) before discount
    total_discount_amount             NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount                     NUMERIC(14,2) NOT NULL DEFAULT 0,   -- CC on Free Goods, wholesale-mode only
    total_tax_amount                     NUMERIC(14,2) NOT NULL DEFAULT 0,   -- VAT/Custom via resolve_item_tax(), if item-level tax applies on sale
    round_off                             NUMERIC(8,2) NOT NULL DEFAULT 0,
    grand_total                            NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc + tax + round_off
    payment_type                            VARCHAR(20),          -- 'Cash' | 'Bank' | 'eSewa' | 'Khalti' | 'IPS' | NULL (fully Credit, nothing paid now)
    amount_paid_now                          NUMERIC(14,2) NOT NULL DEFAULT 0,   -- how much was settled at invoice time; remainder becomes the customer's outstanding balance
    status                                    VARCHAR(20) NOT NULL DEFAULT 'Posted',  -- Draft, Posted, Cancelled
    remarks                                   TEXT,
    is_deleted                                 BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                  INTEGER NOT NULL,
    created_at_ad                                TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                 VARCHAR(10) NOT NULL,
    updated_by                                     INTEGER,
    updated_at_ad                                   TIMESTAMP,
    updated_at_bs                                    VARCHAR(10),
    deleted_by                                        INTEGER,
    deleted_at_ad                                      TIMESTAMP,
    deleted_at_bs                                       VARCHAR(10),

    CONSTRAINT chk_sale_invoice_sale_mode CHECK (sale_mode IN ('Retail', 'Wholesale')),
    CONSTRAINT chk_sale_invoice_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_sale_invoice_payment_type CHECK (payment_type IS NULL OR payment_type IN ('Cash', 'Bank', 'eSewa', 'Khalti', 'IPS'))
);

CREATE INDEX IF NOT EXISTS idx_sale_invoice_customer ON sale_invoice (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_invoice_area ON sale_invoice (area_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_invoice_date ON sale_invoice (invoice_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_invoice_status ON sale_invoice (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN sale_invoice.sale_mode IS 'Snapshot of whether the Free Qty column was active for this invoice (Wholesale) or not (Retail). Drives whether free-scheme/CC logic applied. Stored per-invoice so historical bills stay correctly interpreted if Settings change later.';
COMMENT ON COLUMN sale_invoice.amount_paid_now IS 'Portion of grand_total settled immediately at invoice time via payment_type. The remainder (grand_total - amount_paid_now) becomes part of the customer''s outstanding balance, later reduced via standalone Receipt entries in the Accounts module.';
```

### 1.2 `sale_invoice_item` (line items — one row per batch sold)

```sql
CREATE TABLE IF NOT EXISTS sale_invoice_item (
    sale_invoice_item_id   SERIAL PRIMARY KEY,
    sale_invoice_id          INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    item_id                    INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id                INTEGER NOT NULL REFERENCES item_batch(item_batch_id),  -- auto-picked nearest-expiry batch (read-only in UI)
    batch_no                      VARCHAR(50) NOT NULL,     -- snapshot for display/print, avoids a join for historical invoices
    expiry_month                    SMALLINT NOT NULL,        -- snapshot
    expiry_year                      SMALLINT NOT NULL,        -- snapshot
    entry_mode                        VARCHAR(20) NOT NULL DEFAULT 'free_qty',  -- 'free_qty' | 'net_rate' -- which of the two entry modes this line was entered in
    qty                                NUMERIC(12,2) NOT NULL,   -- paid qty (free_qty mode) OR blended total qty (net_rate mode) -- the ONLY field the user must type
    free_qty                            NUMERIC(12,2) NOT NULL DEFAULT 0,  -- only meaningful in free_qty mode + Wholesale; 0 in Retail or net_rate mode
    current_rate                          NUMERIC(12,2) NOT NULL,   -- item.sale_rate at time of entry, before any net-rate blending
    rate                                    NUMERIC(12,2) NOT NULL,   -- the EDITABLE rate actually billed on this line (equals current_rate in free_qty mode unless user overrides; equals the blended Net Rate in net_rate mode unless user overrides)
    discount_percent                          NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount                             NUMERIC(12,2) NOT NULL DEFAULT 0,
    cc_percent                                    NUMERIC(5,2) NOT NULL DEFAULT 0,   -- from country_tax.custom_percent (manufacturer's country), wholesale-mode only
    cc_amount                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- free_qty * item_purchase_rate_at_time * cc_percent / 100 -- CC is on Purchase Rate, NEVER on MRP
    tax_percent                                       NUMERIC(5,2) NOT NULL DEFAULT 0,   -- from resolve_item_tax(), if applicable on sale
    tax_amount                                          NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount                                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- qty * rate - discount_amount (the line total, excluding cc/tax which roll up separately)
    mrp                                                    NUMERIC(12,2) NOT NULL,
    remarks                                                  TEXT,

    CONSTRAINT chk_sale_invoice_item_entry_mode CHECK (entry_mode IN ('free_qty', 'net_rate')),
    CONSTRAINT chk_sale_invoice_item_qty CHECK (qty > 0),
    CONSTRAINT chk_sale_invoice_item_free_qty CHECK (free_qty >= 0)
);

CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_invoice ON sale_invoice_item (sale_invoice_id);
CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_item ON sale_invoice_item (item_id);
CREATE INDEX IF NOT EXISTS idx_sale_invoice_item_batch ON sale_invoice_item (item_batch_id);

COMMENT ON COLUMN sale_invoice_item.qty IS 'The ONLY quantity field the user manually types. In free_qty mode this is the PAID qty (free_qty is separate). In net_rate mode this is the TOTAL blended qty handed over (paid+free already reflected via the reduced rate).';
COMMENT ON COLUMN sale_invoice_item.rate IS 'Always editable regardless of mode. Auto-populated from item.sale_rate (free_qty mode) or the computed Net Rate formula (net_rate mode), but the user can override either.';
```

> **Stock deduction:** posted via the EXISTING `ItemEngine.post_stock_movement()` — one call per line, `transaction_type='SALE'`, `quantity_change = -(qty + free_qty)` (both paid and free units leave physical stock). No new stock-writing code; this is the same append-only `stock_ledger` mechanism Purchase already uses.

### 1.3 `item_free_scheme` (new reusable master — ratio-based Free Qty scheme)

```sql
CREATE TABLE IF NOT EXISTS item_free_scheme (
    item_free_scheme_id   SERIAL PRIMARY KEY,
    item_id                 INTEGER NOT NULL REFERENCES item(item_id),
    scheme_qty                NUMERIC(10,2) NOT NULL,     -- e.g. 5  (buy this many...)
    scheme_free                 NUMERIC(10,2) NOT NULL,     -- e.g. 1  (...get this many free)  -- together read as "5+1"
    is_active                     BOOLEAN NOT NULL DEFAULT TRUE,
    remarks                        TEXT,

    is_deleted                      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_by                       INTEGER,
    deleted_at_ad                     TIMESTAMPTZ,
    deleted_at_bs                      VARCHAR(10),

    created_by                          INTEGER NOT NULL,
    created_at_ad                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at_bs                         VARCHAR(10) NOT NULL,

    updated_by                              INTEGER,
    updated_at_ad                            TIMESTAMPTZ,
    updated_at_bs                             VARCHAR(10),

    CONSTRAINT chk_item_free_scheme_qty CHECK (scheme_qty > 0),
    CONSTRAINT chk_item_free_scheme_free CHECK (scheme_free > 0)
);

-- One ACTIVE scheme per item at a time (mirrors supplier_manufacturer_discount's
-- "one active mapping per pair" rule) -- soft-delete then re-add for a new ratio.
CREATE UNIQUE INDEX IF NOT EXISTS uq_item_free_scheme_item_active
    ON item_free_scheme (item_id)
    WHERE is_deleted = FALSE AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_item_free_scheme_item ON item_free_scheme (item_id) WHERE is_deleted = FALSE;

COMMENT ON TABLE item_free_scheme IS 'Wholesale Free Qty scheme per item, e.g. scheme_qty=5, scheme_free=1 reads as "5+1". Consumed by SaleEngine to auto-suggest free_qty (free_qty mode) or compute the blended Net Rate (net_rate mode). Never applies in Retail-mode invoices.';
```

### 1.4 `sale_order` + `sale_order_item` (Phase-2 — quotation/booking, reserved here for reference)

```sql
CREATE TABLE IF NOT EXISTS sale_order (
    sale_order_id       SERIAL PRIMARY KEY,
    so_number             VARCHAR(30) NOT NULL UNIQUE,
    customer_id             INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date_ad             DATE NOT NULL,
    order_date_bs              VARCHAR(10) NOT NULL,
    status                       VARCHAR(20) NOT NULL DEFAULT 'Draft',  -- Draft, Confirmed, Converted, Cancelled
    -- 'Converted' is set the moment a Sale Invoice references this sale_order_id,
    -- same "whole-document" status rule already used for purchase_order.
    remarks                       TEXT,
    is_deleted                     BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                      INTEGER NOT NULL,
    created_at_ad                    TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                     VARCHAR(10) NOT NULL,
    updated_by                         INTEGER,
    updated_at_ad                       TIMESTAMP,
    updated_at_bs                        VARCHAR(10),
    deleted_by                            INTEGER,
    deleted_at_ad                          TIMESTAMP,
    deleted_at_bs                           VARCHAR(10),

    CONSTRAINT chk_sale_order_status CHECK (status IN ('Draft', 'Confirmed', 'Converted', 'Cancelled'))
);

CREATE TABLE IF NOT EXISTS sale_order_item (
    sale_order_item_id   SERIAL PRIMARY KEY,
    sale_order_id           INTEGER NOT NULL REFERENCES sale_order(sale_order_id),
    item_id                   INTEGER NOT NULL REFERENCES item(item_id),
    qty                        NUMERIC(12,2) NOT NULL,
    rate                        NUMERIC(12,2) NOT NULL DEFAULT 0,
    remarks                      TEXT
);
```

> Sale Order carries no batch/stock commitment — it is a booking only, converted later into a real Sale Invoice (batch auto-picked at conversion time, same as a fresh invoice).

### 1.5 `sale_return` + `sale_return_item` (Phase-3, reserved here for reference)

```sql
CREATE TABLE IF NOT EXISTS sale_return (
    sale_return_id        SERIAL PRIMARY KEY,
    return_number            VARCHAR(30) NOT NULL UNIQUE,
    sale_invoice_id             INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    customer_id                   INTEGER NOT NULL REFERENCES customers(customer_id),
    return_date_ad                 DATE NOT NULL,
    return_date_bs                   VARCHAR(10) NOT NULL,
    total_amount                       NUMERIC(14,2) NOT NULL DEFAULT 0,
    reason                               TEXT,
    status                                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    is_deleted                             BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                               INTEGER NOT NULL,
    created_at_ad                              TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_return_item (
    sale_return_item_id     SERIAL PRIMARY KEY,
    sale_return_id             INTEGER NOT NULL REFERENCES sale_return(sale_return_id),
    item_batch_id                 INTEGER NOT NULL REFERENCES item_batch(item_batch_id),
    return_qty                      NUMERIC(12,2) NOT NULL,
    return_rate                       NUMERIC(12,2) NOT NULL,
    remarks                             TEXT
);
```

> Stock re-entry via `ItemEngine.post_stock_movement()`, `transaction_type='SALE_RETURN'`, positive quantity_change — same reusable mechanism, no new stock-writing code.

### 1.6 `receipt_payment` (Accounts module — reserved shape only, NOT built in this blueprint)

```sql
-- Reference only. Full Accounts Engine/Model/Screens are a SEPARATE future
-- blueprint (Option A, confirmed). Shape recorded here so Sale/Purchase
-- Engines know what they will eventually link against.
CREATE TABLE IF NOT EXISTS receipt_payment (
    receipt_payment_id    SERIAL PRIMARY KEY,
    direction                VARCHAR(10) NOT NULL,      -- 'Receipt' (from customer) | 'Payment' (to supplier)
    party_type                 VARCHAR(20) NOT NULL,      -- 'Customer' | 'Supplier'
    customer_id                  INTEGER REFERENCES customers(customer_id),
    supplier_id                    INTEGER REFERENCES supplier(supplier_id),
    reference_type                   VARCHAR(30),          -- 'sale_invoice' | 'purchase_invoice' | NULL (unallocated/on-account)
    reference_id                       INTEGER,               -- sale_invoice_id or purchase_invoice_id, if allocated to one
    amount                               NUMERIC(14,2) NOT NULL,
    payment_type                          VARCHAR(20) NOT NULL,   -- 'Cash' | 'Bank' | 'eSewa' | 'Khalti' | 'IPS'
    transaction_date_ad                     DATE NOT NULL,
    transaction_date_bs                      VARCHAR(10) NOT NULL,
    remarks                                    TEXT,
    is_deleted                                  BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                   INTEGER NOT NULL,
    created_at_ad                                 TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                  VARCHAR(10) NOT NULL,

    CONSTRAINT chk_receipt_payment_direction CHECK (direction IN ('Receipt', 'Payment')),
    CONSTRAINT chk_receipt_payment_party_type CHECK (party_type IN ('Customer', 'Supplier')),
    CONSTRAINT chk_receipt_payment_type CHECK (payment_type IN ('Cash', 'Bank', 'eSewa', 'Khalti', 'IPS'))
);
```

---

## 2. Settings Seed (Column Visibility + Free-Scheme Behaviour)

New Settings group: **"Sale"** — same pattern as existing `security.*` / `print.*` rows in `schema_auth.sql`. Every column EXCEPT Qty gets its own show/hide boolean.

```sql
INSERT INTO settings (setting_key, setting_value, setting_group, data_type, default_value, description, display_order) VALUES
    -- Column visibility (compulsory columns -- Item, Qty, Rate, Amount -- are NOT here; they are always shown, no toggle exists for them)
    ('sale.column_show_batch', 'true', 'Sale', 'boolean', 'true', 'Show Batch No. column on the Sale Invoice grid and print', 10),
    ('sale.column_show_expiry', 'true', 'Sale', 'boolean', 'true', 'Show Expiry column on the Sale Invoice grid and print', 20),
    ('sale.column_show_free', 'false', 'Sale', 'boolean', 'false', 'Show Free Qty column -- ON = Wholesale mode (free scheme + CC apply), OFF = Retail mode (free scheme never applies)', 30),
    ('sale.column_show_mrp', 'true', 'Sale', 'boolean', 'true', 'Show MRP column on the Sale Invoice grid and print', 40),
    ('sale.column_show_discount_percent', 'true', 'Sale', 'boolean', 'true', 'Show Discount % column on the Sale Invoice grid and print', 50),
    ('sale.column_show_packing', 'true', 'Sale', 'boolean', 'true', 'Show Packing/Unit column on the Sale Invoice grid and print', 60),
    ('sale.column_show_tax', 'false', 'Sale', 'boolean', 'false', 'Show Tax % / Tax Amount columns on the Sale Invoice grid and print', 70),

    -- Free-scheme behaviour
    ('sale.allow_half_free', 'false', 'Sale', 'boolean', 'false', 'Allow proportional (fractional) free qty when the entered qty is not an exact multiple of the item''s free scheme, e.g. 2.5 of a 5+1 scheme -> 0.5 free', 80),
    ('sale.minimum_auto_free_qty', '1', 'Sale', 'decimal', '1', 'Minimum computed free qty required before it is auto-filled on a line; below this the Free field is left at 0 for the user to set manually', 90),

    -- Code prefix
    ('sale.invoice_prefix', 'SINV-', 'Sale', 'string', 'SINV-', 'Prefix used when auto-generating Sale Invoice numbers', 100),
    ('sale.order_prefix', 'SO-', 'Sale', 'string', 'SO-', 'Prefix used when auto-generating Sale Order numbers (Phase-2)', 110)
ON CONFLICT (setting_key) WHERE companyid IS NULL AND userid IS NULL DO NOTHING;
```

> **Print rule reminder (per Bijay's confirmed requirement):** the Sale Invoice screen and the printed invoice both read from these SAME settings — there is no separate "print layout" column list to keep in sync. Whatever the entry grid shows is exactly what prints.

---

## 3. Models Layer (SQL only — no business logic)

### 3.1 File: `models/sale_invoice_model.py`

```python
"""
models/sale_invoice_model.py

Sale Invoice Model - Medical ERP V2

Project rule: "No SQL outside the Model." Mirrors models/purchase_invoice_model.py's
shape exactly. SQL only, no business logic, no validation, no decisions --
all of that belongs to engines/sale_engine.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class SaleInvoiceSearchFilters:
    """Filter parameters for sale invoice search/listing."""
    search_text: Optional[str] = None       # matches invoice_number, customer_name (joined)
    customer_id: Optional[int] = None
    area_id: Optional[int] = None
    status: Optional[str] = None            # 'Draft' | 'Posted' | 'Cancelled' | None (=all)
    sale_mode: Optional[str] = None         # 'Retail' | 'Wholesale' | None (=both)
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


SALE_INVOICE_COLUMNS = (
    "invoice_number", "customer_id", "area_id", "price_level_id",
    "invoice_date_ad", "invoice_date_bs", "sale_mode",
    "total_qty", "total_free_qty", "total_gross_amount", "total_discount_amount",
    "total_cc_amount", "total_tax_amount", "round_off", "grand_total",
    "payment_type", "amount_paid_now", "status", "remarks",
)

SALE_INVOICE_ITEM_COLUMNS = (
    "item_id", "item_batch_id", "batch_no", "expiry_month", "expiry_year",
    "entry_mode", "qty", "free_qty", "current_rate", "rate",
    "discount_percent", "discount_amount", "cc_percent", "cc_amount",
    "tax_percent", "tax_amount", "amount", "mrp", "remarks",
)


class SaleInvoiceModel:
    """Data-access layer for `sale_invoice` + `sale_invoice_item`. SQL only."""

    # ------------------------------------------------------------------ #
    # CREATE (header + lines, one transaction -- mirrors PurchaseInvoiceModel)
    # ------------------------------------------------------------------ #
    def insert_with_items(self, header_data: dict[str, Any], item_rows: list[dict[str, Any]]) -> int:
        """
        Inserts the sale_invoice header and every sale_invoice_item row in
        ONE database transaction -- either the whole invoice saves or none
        of it does. `header_data` must contain every column in
        SALE_INVOICE_COLUMNS plus created_by/created_at_ad/created_at_bs.
        Each dict in `item_rows` must contain every column in
        SALE_INVOICE_ITEM_COLUMNS. Returns the new sale_invoice_id.

        NOTE: this does NOT touch stock -- the Engine calls
        ItemEngine.post_stock_movement() per line separately, in the same
        logical operation, after this insert succeeds.
        """
        header_columns = list(SALE_INVOICE_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)

        header_sql = f"""
            INSERT INTO sale_invoice ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING sale_invoice_id;
        """

        item_columns = ["sale_invoice_id"] + list(SALE_INVOICE_ITEM_COLUMNS)
        item_col_sql = ", ".join(item_columns)
        item_placeholder_sql = ", ".join(f"%({c})s" for c in item_columns)
        item_sql = f"""
            INSERT INTO sale_invoice_item ({item_col_sql})
            VALUES ({item_placeholder_sql});
        """

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(header_sql, header_data)
                new_id = cur.fetchone()[0]

                for row in item_rows:
                    row_data = dict(row)
                    row_data["sale_invoice_id"] = new_id
                    cur.execute(item_sql, row_data)

            conn.commit()
            logger.info("Sale invoice inserted: id=%s number=%s lines=%s", new_id, header_data.get("invoice_number"), len(item_rows))
            return new_id

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, sale_invoice_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM sale_invoice WHERE sale_invoice_id = %(id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": sale_invoice_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_items_by_invoice(self, sale_invoice_id: int) -> list[dict]:
        sql = """
            SELECT * FROM sale_invoice_item
            WHERE sale_invoice_id = %(id)s
            ORDER BY sale_invoice_item_id ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": sale_invoice_id})
                return [dict(r) for r in cur.fetchall()]

    def exists_by_number(self, invoice_number: str, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM sale_invoice WHERE invoice_number = %(number)s AND is_deleted = FALSE"
        params: dict[str, Any] = {"number": invoice_number}
        if exclude_id is not None:
            sql += " AND sale_invoice_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_number_sequence(self, prefix: str) -> int:
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(invoice_number, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM sale_invoice
            WHERE invoice_number ~ %(pattern)s;
        """
        params = {"prefix_pattern": f"^{prefix}", "pattern": f"^{prefix}[0-9]+$"}
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, filters: SaleInvoiceSearchFilters) -> tuple[list[dict], int]:
        """
        Returns (rows, total_count). Joins customers for display name so
        the List screen doesn't need a second round trip per row --
        same reasoning already used by ItemModel.search()'s total_stock
        subquery and SupplierManufacturerDiscountModel's joined names.
        """
        where = ["1=1"]
        params: dict[str, Any] = {}

        if not filters.include_deleted:
            where.append("si.is_deleted = FALSE")
        if filters.customer_id:
            where.append("si.customer_id = %(customer_id)s")
            params["customer_id"] = filters.customer_id
        if filters.area_id:
            where.append("si.area_id = %(area_id)s")
            params["area_id"] = filters.area_id
        if filters.status:
            where.append("si.status = %(status)s")
            params["status"] = filters.status
        if filters.sale_mode:
            where.append("si.sale_mode = %(sale_mode)s")
            params["sale_mode"] = filters.sale_mode
        if filters.date_from_ad:
            where.append("si.invoice_date_ad >= %(date_from)s")
            params["date_from"] = filters.date_from_ad
        if filters.date_to_ad:
            where.append("si.invoice_date_ad <= %(date_to)s")
            params["date_to"] = filters.date_to_ad
        if filters.search_text:
            where.append("(si.invoice_number ILIKE %(search)s OR c.customer_name ILIKE %(search)s)")
            params["search"] = f"%{filters.search_text}%"

        where_clause = " AND ".join(where)
        offset = max(filters.page - 1, 0) * filters.page_size

        count_sql = f"""
            SELECT COUNT(*) AS total FROM sale_invoice si
            LEFT JOIN customers c ON c.customer_id = si.customer_id
            WHERE {where_clause};
        """
        data_sql = f"""
            SELECT si.*, c.customer_name AS customer_name, a.area_name AS area_name
            FROM sale_invoice si
            LEFT JOIN customers c ON c.customer_id = si.customer_id
            LEFT JOIN areas a ON a.area_id = si.area_id
            WHERE {where_clause}
            ORDER BY si.invoice_date_ad DESC, si.sale_invoice_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """

        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(count_sql, params)
                total_count = cur.fetchone()["total"]

                data_params = dict(params)
                data_params["limit"] = filters.page_size
                data_params["offset"] = offset
                cur.execute(data_sql, data_params)
                rows = [dict(r) for r in cur.fetchall()]

        return rows, total_count

    # ------------------------------------------------------------------ #
    # SOFT DELETE (Cancel) -- Sale Invoices are add-only like Purchase
    # Invoices; corrections go through Sale Return, not editing.
    # ------------------------------------------------------------------ #
    def soft_delete(self, sale_invoice_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE sale_invoice
            SET is_deleted = TRUE, status = 'Cancelled',
                deleted_by = %(deleted_by)s, deleted_at_ad = %(deleted_at_ad)s, deleted_at_bs = %(deleted_at_bs)s
            WHERE sale_invoice_id = %(id)s AND is_deleted = FALSE;
        """
        params = {"id": sale_invoice_id, "deleted_by": deleted_by, "deleted_at_ad": deleted_at_ad, "deleted_at_bs": deleted_at_bs}
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                if ok:
                    logger.info("Sale invoice cancelled: id=%s by=%s", sale_invoice_id, deleted_by)
                return ok


__all__ = ["SaleInvoiceModel", "SaleInvoiceSearchFilters", "SALE_INVOICE_COLUMNS", "SALE_INVOICE_ITEM_COLUMNS"]
```

### 3.2 File: `models/item_free_scheme_model.py`

```python
"""
models/item_free_scheme_model.py

Item Free Scheme Model - Medical ERP V2

Project rule: "No SQL outside the Model." Mirrors
models/supplier_manufacturer_discount_model.py's shape (simple per-item
mapping, one active row at a time). SQL only, no business logic.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ItemFreeSchemeModel:
    """Data-access layer for `item_free_scheme`. SQL only, no business logic."""

    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO item_free_scheme (
                item_id, scheme_qty, scheme_free, is_active, remarks,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(item_id)s, %(scheme_qty)s, %(scheme_free)s, %(is_active)s, %(remarks)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING item_free_scheme_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()[0]
                conn.commit()
                logger.info("Item free scheme inserted: id=%s item_id=%s %s+%s", new_id, data.get("item_id"), data.get("scheme_qty"), data.get("scheme_free"))
                return new_id

    def update(self, item_free_scheme_id: int, data: dict[str, Any]) -> bool:
        sql = """
            UPDATE item_free_scheme
            SET scheme_qty = %(scheme_qty)s, scheme_free = %(scheme_free)s,
                is_active = %(is_active)s, remarks = %(remarks)s,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE item_free_scheme_id = %(id)s AND is_deleted = FALSE;
        """
        params = dict(data)
        params["id"] = item_free_scheme_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                updated = cur.rowcount > 0
                conn.commit()
                return updated

    def get_by_id(self, item_free_scheme_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM item_free_scheme WHERE item_free_scheme_id = %(id)s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": item_free_scheme_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def get_active_by_item(self, item_id: int) -> Optional[dict]:
        """The ONE currently-active scheme for this item, or None if the
        item has no free scheme configured -- used live by SaleEngine
        every time an item is added to a Sale Invoice line."""
        sql = """
            SELECT * FROM item_free_scheme
            WHERE item_id = %(item_id)s AND is_deleted = FALSE AND is_active = TRUE
            LIMIT 1;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                row = cur.fetchone()
                return dict(row) if row else None

    def exists_active_for_item(self, item_id: int, exclude_id: Optional[int] = None) -> bool:
        sql = "SELECT 1 FROM item_free_scheme WHERE item_id = %(item_id)s AND is_deleted = FALSE AND is_active = TRUE"
        params: dict[str, Any] = {"item_id": item_id}
        if exclude_id is not None:
            sql += " AND item_free_scheme_id != %(exclude_id)s"
            params["exclude_id"] = exclude_id
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def search(self, search_text: Optional[str] = None, include_deleted: bool = False) -> list[dict]:
        """Joined with item for display -- item name/code -- same pattern as
        SupplierManufacturerDiscountModel's joined supplier/manufacturer names."""
        where = ["1=1"]
        params: dict[str, Any] = {}
        if not include_deleted:
            where.append("fs.is_deleted = FALSE")
        if search_text:
            where.append("i.item_name ILIKE %(search)s")
            params["search"] = f"%{search_text}%"
        where_clause = " AND ".join(where)

        sql = f"""
            SELECT fs.*, i.item_name AS item_name, i.item_code AS item_code
            FROM item_free_scheme fs
            LEFT JOIN item i ON i.item_id = fs.item_id
            WHERE {where_clause}
            ORDER BY i.item_name ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def soft_delete(self, item_free_scheme_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> bool:
        sql = """
            UPDATE item_free_scheme
            SET is_deleted = TRUE, deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s, deleted_at_bs = %(deleted_at_bs)s
            WHERE item_free_scheme_id = %(id)s AND is_deleted = FALSE;
        """
        params = {"id": item_free_scheme_id, "deleted_by": deleted_by, "deleted_at_ad": deleted_at_ad, "deleted_at_bs": deleted_at_bs}
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                return ok

    def restore(self, item_free_scheme_id: int, updated_by: int, updated_at_ad, updated_at_bs: str) -> bool:
        sql = """
            UPDATE item_free_scheme
            SET is_deleted = FALSE, deleted_by = NULL, deleted_at_ad = NULL, deleted_at_bs = NULL,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE item_free_scheme_id = %(id)s AND is_deleted = TRUE;
        """
        params = {"id": item_free_scheme_id, "updated_by": updated_by, "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs}
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                ok = cur.rowcount > 0
                conn.commit()
                return ok


__all__ = ["ItemFreeSchemeModel"]
```

### 3.3 Extension to existing `models/customer_model.py`

One new function, added alongside the existing `get_areas()` / `get_active_customers()`:

```python
def get_active_customers_by_area(area_id: int) -> list[dict]:
    """
    Backs the Sale Invoice screen's Area -> Customer two-combo search
    (confirmed requirement): once an Area is picked, this narrows the
    Customer combo to only that area's active, non-deleted customers.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT customer_id, customer_code, customer_name, price_level_id, credit_limit, "
                "opening_balance, balance_type FROM customers "
                "WHERE area_id = %s AND is_active = TRUE AND is_deleted = FALSE ORDER BY customer_name",
                (area_id,)
            )
            return cur.fetchall()
```

### 3.4 Extension to existing `models/item_model.py`

One new read helper, used by the Sale Invoice grid to auto-fill Batch/Expiry/Rate/Free-scheme the moment an item is chosen in a row:

```python
def get_nearest_expiry_batch(self, item_id: int) -> Optional[dict]:
    """
    Returns the single nearest-expiry batch with qty > 0 for an item, or
    None if the item has no available stock. Backs the Sale Invoice
    grid's auto-batch-pick (read-only Batch/Expiry columns, per confirmed
    scope). Reuses the exact same ordering ItemModel.search()'s
    nearest_batch_no/nearest_expiry_display subqueries already use.
    """
    sql = """
        SELECT * FROM item_batch
        WHERE item_id = %(item_id)s AND batch_qty > 0
        ORDER BY expiry_year ASC, expiry_month ASC, batch_no ASC
        LIMIT 1;
    """
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
            cur.execute(sql, {"item_id": item_id})
            row = cur.fetchone()
            return dict(row) if row else None
```

> This belongs on `ItemModel` (not a new file) since it queries `item_batch`, which `ItemModel`/`ItemBatchModel` already own exclusively per the project's "no SQL outside the Model" rule.

---

## 4. Glossary (mirrors Part-1 Purchase doc's approach, terms specific to Sale)

| Term | Meaning |
|---|---|
| **Sale Mode** | `Retail` (Free column hidden, no free-scheme/CC logic runs at all) vs `Wholesale` (Free column shown, free-scheme + CC on Free Goods both active). Snapshotted per-invoice at creation time. |
| **Free Qty mode** (line-level) | User enters paid `qty`; `free_qty` is a separate field, auto-suggested from `item_free_scheme` (minimum `sale.minimum_auto_free_qty` before auto-fill), still user-editable. |
| **Net Rate mode** (line-level) | User enters a single blended `qty` (paid+free together); `rate` is auto-reduced via `Net Rate = current_rate × scheme_qty ÷ (scheme_qty + scheme_free)` so the line total already reflects the free benefit with no free_qty shown. Still user-editable. |
| **CC on Free Goods** | Customs-style charge applied ONLY in Wholesale mode, on the value of free goods handed out: `free_qty × item's purchase_rate × manufacturer_country custom_percent ÷ 100`. Always on Purchase Rate, never on MRP — this is the cost basis, mirroring the exact Purchase-side CC concept, applied here because giving away free stock is itself treated as a taxable supply. |
| **Amount Paid Now vs Receipt** | `sale_invoice.amount_paid_now` is whatever was settled at the moment of billing (captured directly on the invoice). Anything beyond that becomes outstanding customer balance, later reduced only through separate `receipt_payment` rows in the standalone Accounts module — the two are never the same record. |

---

**Part 1 complete.** Waiting for your confirmation before Part 2 (Validators + Engines: `sale_validator.py`, `item_free_scheme_engine.py`, `sale_engine.py` — free-scheme resolution, net-rate calculation, stock deduction orchestration via existing `ItemEngine.post_stock_movement()`).
