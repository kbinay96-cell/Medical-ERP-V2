# Sale Return Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Depends on (already built / confirmed):**
- `sale_invoice` / `sale_invoice_item` (Sale Module Part 1 — the invoice being returned against)
- `engines/date_engine.py` — BS↔AD conversion
- `engines/customer_engine.py` / `models/customer_model.py`
- `engines/item_engine.py` / `models/item_model.py` — `ItemEngine.post_stock_movement()` (stock re-entry)
- `engines/exceptions.py` — EngineError, ValidationError, RecordNotFoundError, DuplicateRecordError
- `engines/settings_engine.py`
- Reserved (not yet built): `receipt_payment` table shape (Accounts module) — Sale Return's `refund_mode='Advance'` path will eventually post into this; reference only, no dependency yet.

---

## 0. Scope — CONFIRMED

1. **Return is always against a specific posted Sale Invoice** — never a standalone/free-floating return. Every return line traces back to one exact `sale_invoice_item_id`.
2. **Partial + multiple returns allowed.** A customer can return part of a line today and the rest next month — system tracks *cumulative returned qty per invoice line* and never allows total returns to exceed the original billed `qty`.
3. **Return always re-enters the SAME batch** the item was originally sold from (`item_batch_id` copied from the original `sale_invoice_item`) — no batch selection in the Return UI, mirrors Sale Invoice's own "batch is read-only" rule.
4. **Free-qty units are never returnable** — only the paid `qty` portion of a line can be returned (a customer cannot "return" a free unit; if the whole line is voided, that is a Sale Invoice cancellation, not a Return). `sale_return_item` has no `free_qty` column by design.
5. **Rate/discount/cc/tax on the return line are NOT re-entered** — they are copied from the original `sale_invoice_item` proportionally to `return_qty`, and are read-only. This guarantees the return value can never drift from what was actually billed.
6. **Refund handling (`refund_mode`)** — fixed list: `Adjust Against Invoice` (reduces this same invoice's outstanding — default, most common), `Advance` (goes to customer's advance/credit balance, usable against any future invoice), `Cash Refund` (physical cash handed back now). This field decides how the Accounts module will later post the journal — reserved here, not journaled yet since Accounts isn't built.
7. **Status lifecycle** — `Draft | Posted | Cancelled`, same as Sale Invoice. Only a `Posted` return moves stock. A `Cancelled` return requires a mandatory `cancellation_reason` (project-wide rule, confirmed) and its stock/qty effect is reversed via a new posting, never by editing history.
8. **Full audit trail** — created/updated/deleted by+at (AD+BS), same pattern as every other V2 table. No exceptions.
9. **return_number** is our own sequential code (e.g. `SRTN-0001`), same pattern as `invoice_number`.

---

## 1. Database Schema

### 1.1 `sale_return` (header)

```sql
CREATE TABLE IF NOT EXISTS sale_return (
    sale_return_id          SERIAL PRIMARY KEY,
    return_number             VARCHAR(30) NOT NULL UNIQUE,     -- e.g. SRTN-0001
    sale_invoice_id             INTEGER NOT NULL REFERENCES sale_invoice(sale_invoice_id),
    customer_id                   INTEGER NOT NULL REFERENCES customers(customer_id),   -- snapshot from invoice (kept even if customer master changes)
    return_date_ad                  DATE NOT NULL,
    return_date_bs                    VARCHAR(10) NOT NULL,
    return_reason                       TEXT NOT NULL,             -- WHY the customer is returning (damaged/expired/wrong item/excess supply, etc.) -- separate from cancellation_reason below
    refund_mode                           VARCHAR(30) NOT NULL DEFAULT 'Adjust Against Invoice',
    total_qty                               NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_gross_amount                        NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(return_qty * rate) before discount
    total_discount_amount                       NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount                               NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_tax_amount                                NUMERIC(14,2) NOT NULL DEFAULT 0,
    round_off                                         NUMERIC(8,2) NOT NULL DEFAULT 0,
    grand_total                                         NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc + tax + round_off
    status                                                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                    TEXT,        -- mandatory only when status='Cancelled', enforced in Engine/Validator, not DB CHECK (keeps the column simple; Validator owns the rule)
    remarks                                                  TEXT,
    is_deleted                                                BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                                  INTEGER NOT NULL,
    created_at_ad                                                TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                                 VARCHAR(10) NOT NULL,
    updated_by                                                      INTEGER,
    updated_at_ad                                                    TIMESTAMP,
    updated_at_bs                                                     VARCHAR(10),
    deleted_by                                                          INTEGER,
    deleted_at_ad                                                        TIMESTAMP,
    deleted_at_bs                                                         VARCHAR(10),

    CONSTRAINT chk_sale_return_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_sale_return_refund_mode CHECK (refund_mode IN ('Adjust Against Invoice', 'Advance', 'Cash Refund'))
);

CREATE INDEX IF NOT EXISTS idx_sale_return_invoice ON sale_return (sale_invoice_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_customer ON sale_return (customer_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_date ON sale_return (return_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_sale_return_status ON sale_return (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN sale_return.refund_mode IS 'How the returned value is settled: Adjust Against Invoice (reduces this invoice''s own outstanding, default), Advance (added to customer credit balance, usable on any future invoice), Cash Refund (physical cash given back now). Drives future Accounts-module journal posting; not journaled yet as Accounts is a separate blueprint.';
COMMENT ON COLUMN sale_return.cancellation_reason IS 'Required by the Validator whenever status is set to Cancelled. Cancelling a Posted return never deletes it or its stock effect -- a reversing stock movement is posted instead (see 1.2 comment), preserving full history.';
```

### 1.2 `sale_return_item` (return lines — one row per original invoice line being returned)

```sql
CREATE TABLE IF NOT EXISTS sale_return_item (
    sale_return_item_id      SERIAL PRIMARY KEY,
    sale_return_id              INTEGER NOT NULL REFERENCES sale_return(sale_return_id),
    sale_invoice_item_id          INTEGER NOT NULL REFERENCES sale_invoice_item(sale_invoice_item_id),  -- the EXACT original line -- source of truth for the cumulative-qty check
    item_id                          INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id                      INTEGER NOT NULL REFERENCES item_batch(item_batch_id),   -- copied from sale_invoice_item -- read-only, same batch stock re-enters
    batch_no                             VARCHAR(50) NOT NULL,     -- snapshot
    expiry_month                           SMALLINT NOT NULL,        -- snapshot
    expiry_year                              SMALLINT NOT NULL,        -- snapshot
    return_qty                                 NUMERIC(12,2) NOT NULL,   -- the ONLY field the user manually types; validated against remaining returnable qty in the Engine
    rate                                          NUMERIC(12,2) NOT NULL,   -- copied read-only from sale_invoice_item.rate -- never re-entered
    discount_percent                                NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only from original line
    discount_amount                                   NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share of the original line's discount
    cc_percent                                          NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only, Wholesale invoices only
    cc_amount                                             NUMERIC(12,2) NOT NULL DEFAULT 0,   -- proportional reversal -- only applies if the returned units include a CC-bearing free-goods link; ordinarily 0 since free_qty itself is never returned
    tax_percent                                             NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only
    tax_amount                                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share
    amount                                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty * rate - discount_amount
    remarks                                                        TEXT,

    CONSTRAINT chk_sale_return_item_qty CHECK (return_qty > 0)
);

CREATE INDEX IF NOT EXISTS idx_sale_return_item_return ON sale_return_item (sale_return_id);
CREATE INDEX IF NOT EXISTS idx_sale_return_item_invoice_item ON sale_return_item (sale_invoice_item_id);
CREATE INDEX IF NOT EXISTS idx_sale_return_item_batch ON sale_return_item (item_batch_id);

COMMENT ON COLUMN sale_return_item.sale_invoice_item_id IS 'The single source of truth for validation: SUM(return_qty) across ALL non-cancelled sale_return_item rows referencing the same sale_invoice_item_id must never exceed that line''s original sale_invoice_item.qty. Enforced in sale_return_validator.py, not the DB, since it is a cross-row aggregate rule.';
COMMENT ON COLUMN sale_return_item.rate IS 'Always copied from the original sale_invoice_item.rate at return time and never independently editable -- guarantees the return value can never diverge from what was actually billed.';
```

> **Stock re-entry:** posted via the EXISTING `ItemEngine.post_stock_movement()` — one call per line, `transaction_type='SALE_RETURN'`, `quantity_change = +return_qty`, same `item_batch_id` the goods were sold from. No new stock-writing code — identical append-only `stock_ledger` mechanism already used by Sale and Purchase.

> **Cancellation reversal:** cancelling a `Posted` sale_return does NOT delete its stock effect or edit `sale_return_item` rows. The Engine posts an equal-and-opposite `post_stock_movement()` call (`transaction_type='SALE_RETURN_CANCEL'`, `quantity_change = -return_qty`) and sets `status='Cancelled'` + `cancellation_reason` on the header. Full history — original return and its reversal — stays visible in `stock_ledger` and in `sale_return`.

---

## 2. Models Layer (SQL only — no business logic)

### 2.1 File: `models/sale_return_model.py`

```python
"""
models/sale_return_model.py

Sale Return Model - Medical ERP V2

Project rule: "No SQL outside the Model." Mirrors models/sale_invoice_model.py's
shape exactly. SQL only, no business logic, no validation, no decisions --
all of that belongs to engines/sale_return_engine.py.
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
class SaleReturnSearchFilters:
    """Filter parameters for sale return search/listing."""
    search_text: Optional[str] = None       # matches return_number, invoice_number, customer_name (joined)
    customer_id: Optional[int] = None
    sale_invoice_id: Optional[int] = None
    status: Optional[str] = None            # 'Draft' | 'Posted' | 'Cancelled' | None (=all)
    refund_mode: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


SALE_RETURN_COLUMNS = (
    "return_number", "sale_invoice_id", "customer_id",
    "return_date_ad", "return_date_bs", "return_reason", "refund_mode",
    "total_qty", "total_gross_amount", "total_discount_amount",
    "total_cc_amount", "total_tax_amount", "round_off", "grand_total",
    "status", "remarks",
)

SALE_RETURN_ITEM_COLUMNS = (
    "sale_invoice_item_id", "item_id", "item_batch_id", "batch_no",
    "expiry_month", "expiry_year", "return_qty", "rate",
    "discount_percent", "discount_amount", "cc_percent", "cc_amount",
    "tax_percent", "tax_amount", "amount", "remarks",
)


class SaleReturnModel:
    """Data-access layer for `sale_return` + `sale_return_item`. SQL only."""

    # ------------------------------------------------------------------ #
    # CREATE (header + lines, one transaction)
    # ------------------------------------------------------------------ #
    def insert_with_items(self, header_data: dict[str, Any], item_rows: list[dict[str, Any]]) -> int:
        """
        Inserts the sale_return header and every sale_return_item row in ONE
        database transaction. `header_data` must contain every column in
        SALE_RETURN_COLUMNS plus created_by/created_at_ad/created_at_bs.
        Each dict in `item_rows` must contain every column in
        SALE_RETURN_ITEM_COLUMNS. Returns the new sale_return_id.

        NOTE: this does NOT touch stock and does NOT validate cumulative
        return quantity -- the Engine calls get_returned_qty_for_invoice_item()
        per line BEFORE calling this, then calls
        ItemEngine.post_stock_movement() per line AFTER this insert succeeds,
        all inside the same logical operation.
        """
        header_columns = list(SALE_RETURN_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)

        header_sql = f"""
            INSERT INTO sale_return ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING sale_return_id;
        """

        item_columns = ["sale_return_id"] + list(SALE_RETURN_ITEM_COLUMNS)
        item_col_sql = ", ".join(item_columns)
        item_placeholder_sql = ", ".join(f"%({c})s" for c in item_columns)
        item_sql = f"""
            INSERT INTO sale_return_item ({item_col_sql})
            VALUES ({item_placeholder_sql});
        """

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    sale_return_id = cur.fetchone()["sale_return_id"]

                    for row in item_rows:
                        row = dict(row)
                        row["sale_return_id"] = sale_return_id
                        cur.execute(item_sql, row)

            return sale_return_id
        except Exception:
            logger.exception("insert_with_items failed for sale_return")
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # VALIDATION SUPPORT -- cumulative returned qty per original invoice line
    # ------------------------------------------------------------------ #
    def get_returned_qty_for_invoice_item(self, sale_invoice_item_id: int) -> float:
        """
        Returns SUM(return_qty) across every sale_return_item row that
        references this sale_invoice_item_id, counting ONLY returns whose
        parent sale_return.status != 'Cancelled' and is_deleted = FALSE.
        The Engine subtracts this from sale_invoice_item.qty to get the
        remaining returnable quantity before allowing a new return line.
        """
        sql = """
            SELECT COALESCE(SUM(sri.return_qty), 0) AS returned_qty
            FROM sale_return_item sri
            JOIN sale_return sr ON sr.sale_return_id = sri.sale_return_id
            WHERE sri.sale_invoice_item_id = %(sale_invoice_item_id)s
              AND sr.status != 'Cancelled'
              AND sr.is_deleted = FALSE;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"sale_invoice_item_id": sale_invoice_item_id})
                return float(cur.fetchone()["returned_qty"])
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, sale_return_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM sale_return WHERE sale_return_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": sale_return_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_items_by_return_id(self, sale_return_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sale_return_item WHERE sale_return_id = %(id)s ORDER BY sale_return_item_id;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": sale_return_id})
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: SaleReturnSearchFilters) -> list[dict[str, Any]]:
        """Paginated search -- mirrors SaleInvoiceModel.search()'s dynamic WHERE-clause pattern."""
        conditions = ["sr.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}

        if filters.search_text:
            conditions.append(
                "(sr.return_number ILIKE %(search_text)s OR si.invoice_number ILIKE %(search_text)s "
                "OR c.name ILIKE %(search_text)s)"
            )
            params["search_text"] = f"%{filters.search_text}%"
        if filters.customer_id:
            conditions.append("sr.customer_id = %(customer_id)s")
            params["customer_id"] = filters.customer_id
        if filters.sale_invoice_id:
            conditions.append("sr.sale_invoice_id = %(sale_invoice_id)s")
            params["sale_invoice_id"] = filters.sale_invoice_id
        if filters.status:
            conditions.append("sr.status = %(status)s")
            params["status"] = filters.status
        if filters.refund_mode:
            conditions.append("sr.refund_mode = %(refund_mode)s")
            params["refund_mode"] = filters.refund_mode
        if filters.date_from_ad:
            conditions.append("sr.return_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("sr.return_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size

        sql = f"""
            SELECT sr.*, si.invoice_number, c.name AS customer_name
            FROM sale_return sr
            JOIN sale_invoice si ON si.sale_invoice_id = sr.sale_invoice_id
            JOIN customers c ON c.customer_id = sr.customer_id
            WHERE {where_sql}
            ORDER BY sr.sale_return_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        params["limit"] = filters.page_size
        params["offset"] = offset

        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # CANCEL (status change + mandatory reason -- never a delete)
    # ------------------------------------------------------------------ #
    def cancel(self, sale_return_id: int, cancellation_reason: str, updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE sale_return
            SET status = 'Cancelled',
                cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE sale_return_id = %(sale_return_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "sale_return_id": sale_return_id,
                        "cancellation_reason": cancellation_reason,
                        "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad,
                        "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # SOFT DELETE
    # ------------------------------------------------------------------ #
    def soft_delete(self, sale_return_id: int, deleted_by: int,
                     deleted_at_ad: Any, deleted_at_bs: str) -> None:
        sql = """
            UPDATE sale_return
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE sale_return_id = %(sale_return_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "sale_return_id": sale_return_id,
                        "deleted_by": deleted_by,
                        "deleted_at_ad": deleted_at_ad,
                        "deleted_at_bs": deleted_at_bs,
                    })
        finally:
            conn.close()
```

### 2.2 Extension to existing `models/sale_invoice_model.py`

Add one read-only helper needed by the Return screen to fetch a posted invoice's returnable lines:

```python
def get_returnable_items(self, sale_invoice_id: int) -> list[dict[str, Any]]:
    """
    Returns every sale_invoice_item row for a posted invoice, joined with
    already-returned quantity, so the Engine/Screen can compute remaining
    returnable qty per line without a second round-trip.
    """
    sql = """
        SELECT
            sii.*,
            COALESCE(SUM(sri.return_qty) FILTER (WHERE sr.status != 'Cancelled' AND sr.is_deleted = FALSE), 0) AS already_returned_qty
        FROM sale_invoice_item sii
        LEFT JOIN sale_return_item sri ON sri.sale_invoice_item_id = sii.sale_invoice_item_id
        LEFT JOIN sale_return sr ON sr.sale_return_id = sri.sale_return_id
        WHERE sii.sale_invoice_id = %(sale_invoice_id)s
        GROUP BY sii.sale_invoice_item_id
        ORDER BY sii.sale_invoice_item_id;
    """
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
            cur.execute(sql, {"sale_invoice_id": sale_invoice_id})
            return cur.fetchall()
    finally:
        conn.close()
```

---

## 3. Glossary

| Term | Meaning |
|---|---|
| **Returnable Qty** | `sale_invoice_item.qty − already_returned_qty` (sum of all non-cancelled returns against that exact line). A new return line can never exceed this remaining amount. |
| **refund_mode** | How the return's value is settled: `Adjust Against Invoice` (default — reduces this invoice's own outstanding balance), `Advance` (added to customer's credit balance for any future invoice), `Cash Refund` (physical cash handed back immediately). Reserved for the future Accounts module's journal posting. |
| **Same-Batch Re-entry** | Stock always returns to the exact `item_batch_id` it was sold from — no batch re-selection, mirrors Sale Invoice's read-only batch rule. |
| **Cancellation vs Deletion** | Cancelling a Posted return reverses its stock effect with a new equal-and-opposite movement (never edits history) and requires `cancellation_reason`. Soft-delete (`is_deleted`) is separate and only hides a `Draft` return that was never posted. |
| **return_reason vs cancellation_reason** | `return_reason` is WHY the customer is returning goods (business reason, always required). `cancellation_reason` is WHY this return document itself was voided after the fact (only required if status becomes Cancelled) — two different questions. |

---

**Part 1 complete.** Waiting for your confirmation before Part 2 (Validators + Engine: `sale_return_validator.py`, `sale_return_engine.py` — cumulative-qty check, proportional discount/cc/tax calculation, stock reversal orchestration via existing `ItemEngine.post_stock_movement()`, cancellation reversal flow).
