# Purchase Return Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Depends on (already built, confirmed from real files):**
- `purchase_invoice` / `purchase_invoice_item` (Purchase Module Part 1 — the invoice being returned against)
- `engines/date_engine.py` — BS↔AD conversion
- `engines/supplier_engine.py` / `models/supplier_model.py`
- `engines/item_engine.py` / `models/item_model.py` — `ItemEngine.post_stock_movement()` (already documented in its own docstring as the intended future caller for exactly this case: *"negative = stock OUT ... a Purchase Return"*)
- `engines/exceptions.py` — EngineError, ValidationError, RecordNotFoundError, DuplicateRecordError
- Reserved (not yet built): `receipt_payment`/Accounts module — Purchase Return's `settlement_mode='Supplier Advance'` path will eventually post into it; reference only, no dependency yet.

**Supersedes:** the placeholder `purchase_return` / `purchase_return_item` tables sketched in Purchase Module Part 1 §1.4 (marked "Phase-2, optional") — this document is the full, final schema. The placeholder version did not split paid vs. free quantity and had no audit trail; both are added below.

---

## 0. Scope — CONFIRMED

1. **Return is always against a specific posted Purchase Invoice** — never standalone. Every return line traces back to one exact `purchase_invoice_item_id`, same traceability principle as Sale Return.
2. **Partial + multiple returns allowed**, cumulative-tracked per invoice line — total returns can never exceed what was originally received on that line.
3. **Paid qty AND free qty are both separately returnable.** This is the one deliberate difference from Sale Return: a customer can never "return" a free unit they were gifted, but a pharmacy CAN return defective/expired free units back to the supplier — free stock is still real physical stock sitting in the batch, and the supplier gave it, so it can go back. Each return line therefore carries **two** quantity fields: `return_qty` (paid portion) and `return_free_qty` (free portion), validated independently against their own remaining balances.
4. **Return always goes back to the SAME batch** the goods were received into (`item_batch_id` copied from the original `purchase_invoice_item`) — no batch selection in the Return UI.
5. **Rate/discount/cc are NOT re-entered** — copied read-only from the original `purchase_invoice_item`, proportional to the quantity being returned (discount is proportional to `return_qty`, since discount only ever applied to paid qty in the original invoice; cc_amount is proportional to `return_free_qty`, since cc in Purchase Invoice was computed on free-goods customs value — see Purchase Module Part 1 §1.3).
6. **`settlement_mode`** — fixed list: `Adjust Against Payable` (reduces what we owe this supplier — default), `Supplier Advance` (goes to our advance/credit balance with this supplier, usable against a future purchase), `Cash Refund` (supplier hands cash back now). Reserved for the future Accounts module's journal posting, same reservation pattern as Sale Return's `refund_mode`.
7. **Status lifecycle** — `Draft | Posted | Cancelled`, same as every other V2 transaction. Only `Posted` moves stock (reduces it). Cancelling a `Posted` return requires mandatory `cancellation_reason` (project-wide rule) and reverses via a new opposite stock posting, never by editing history.
8. **Full audit trail** — created/updated/deleted by+at (AD+BS) — the placeholder table in Purchase Module Part 1 had none of this; added here to match every other V2 table.
9. **`return_number`** is our own sequential code (`PRTN-0001`), same pattern as `internal_ref_number` on `purchase_invoice`.

---

## 1. Database Schema

### 1.1 `purchase_return` (header) — replaces the Phase-2 placeholder

```sql
CREATE TABLE IF NOT EXISTS purchase_return (
    purchase_return_id      SERIAL PRIMARY KEY,
    return_number              VARCHAR(30) NOT NULL UNIQUE,     -- e.g. PRTN-0001
    purchase_invoice_id           INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    supplier_id                     INTEGER NOT NULL REFERENCES supplier(supplier_id),   -- snapshot from invoice
    return_date_ad                   DATE NOT NULL,
    return_date_bs                     VARCHAR(10) NOT NULL,
    return_reason                        TEXT NOT NULL,             -- WHY goods are going back (damaged/expired/wrong item/quality issue)
    settlement_mode                        VARCHAR(30) NOT NULL DEFAULT 'Adjust Against Payable',
    total_qty                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- sum of returned PAID qty across lines
    total_free_qty                             NUMERIC(12,2) NOT NULL DEFAULT 0,   -- sum of returned FREE qty across lines
    total_gross_amount                           NUMERIC(14,2) NOT NULL DEFAULT 0,   -- sum(return_qty * rate) before discount, free qty contributes 0 value
    total_discount_amount                          NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_cc_amount                                  NUMERIC(14,2) NOT NULL DEFAULT 0,   -- reversed customs charge on returned free qty
    grand_total                                        NUMERIC(14,2) NOT NULL DEFAULT 0,   -- gross - discount + cc
    status                                                VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                    TEXT,        -- mandatory only when status='Cancelled'; enforced in Validator, not a DB CHECK
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

    CONSTRAINT chk_purchase_return_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_purchase_return_settlement_mode CHECK (settlement_mode IN ('Adjust Against Payable', 'Supplier Advance', 'Cash Refund'))
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_invoice ON purchase_return (purchase_invoice_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_supplier ON purchase_return (supplier_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_date ON purchase_return (return_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_purchase_return_status ON purchase_return (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN purchase_return.settlement_mode IS 'How the returned value is settled with the supplier: Adjust Against Payable (reduces what we owe this supplier, default), Supplier Advance (added to our credit balance with this supplier, usable on a future purchase), Cash Refund (supplier hands cash back now). Drives future Accounts-module journal posting; not journaled yet as Accounts is a separate blueprint.';
COMMENT ON COLUMN purchase_return.cancellation_reason IS 'Required by the Validator whenever status is set to Cancelled. Cancelling a Posted return never deletes it or its stock effect -- a reversing stock movement is posted instead, preserving full history.';
```

### 1.2 `purchase_return_item` (return lines) — replaces the Phase-2 placeholder

```sql
CREATE TABLE IF NOT EXISTS purchase_return_item (
    purchase_return_item_id  SERIAL PRIMARY KEY,
    purchase_return_id          INTEGER NOT NULL REFERENCES purchase_return(purchase_return_id),
    purchase_invoice_item_id       INTEGER NOT NULL REFERENCES purchase_invoice_item(purchase_invoice_item_id),  -- the EXACT original line -- source of truth for both cumulative-qty checks
    item_id                            INTEGER NOT NULL REFERENCES item(item_id),
    item_batch_id                        INTEGER NOT NULL REFERENCES item_batch(item_batch_id),   -- copied from purchase_invoice_item -- read-only, same batch stock leaves from
    batch_no                               VARCHAR(50) NOT NULL,     -- snapshot
    expiry_month                             SMALLINT NOT NULL,        -- snapshot
    expiry_year                                SMALLINT NOT NULL,        -- snapshot
    return_qty                                   NUMERIC(12,2) NOT NULL DEFAULT 0,   -- returned PAID quantity -- validated against remaining returnable paid qty
    return_free_qty                                NUMERIC(12,2) NOT NULL DEFAULT 0,   -- returned FREE quantity -- validated separately against remaining returnable free qty
    rate                                              NUMERIC(12,2) NOT NULL,   -- copied read-only from purchase_invoice_item.purchase_rate -- never re-entered
    discount_percent                                    NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only from original line
    discount_amount                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty-proportional share of the original line's discount (discount only ever applied to paid qty)
    cc_percent                                              NUMERIC(5,2) NOT NULL DEFAULT 0,    -- copied read-only
    cc_amount                                                 NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_free_qty-proportional share of the original line's customs charge (cc was computed on free qty in Purchase Invoice)
    amount                                                       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- return_qty * rate - discount_amount (free qty always contributes 0 value, same as on the original invoice line)
    remarks                                                        TEXT,

    CONSTRAINT chk_purchase_return_item_qty CHECK (return_qty >= 0 AND return_free_qty >= 0),
    CONSTRAINT chk_purchase_return_item_qty_nonzero CHECK (return_qty > 0 OR return_free_qty > 0)
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_item_return ON purchase_return_item (purchase_return_id);
CREATE INDEX IF NOT EXISTS idx_purchase_return_item_invoice_item ON purchase_return_item (purchase_invoice_item_id);
CREATE INDEX IF NOT EXISTS idx_purchase_return_item_batch ON purchase_return_item (item_batch_id);

COMMENT ON COLUMN purchase_return_item.purchase_invoice_item_id IS 'The single source of truth for validation: SUM(return_qty) across ALL non-cancelled purchase_return_item rows referencing the same purchase_invoice_item_id must never exceed that line''s original purchase_invoice_item.qty, and SUM(return_free_qty) must never exceed the original free_qty -- two independent cumulative checks. Enforced in purchase_return_validator.py, not the DB, since these are cross-row aggregate rules.';
COMMENT ON COLUMN purchase_return_item.rate IS 'Always copied from the original purchase_invoice_item.purchase_rate at return time and never independently editable.';
```

> **Stock reversal:** posted via the EXISTING `ItemEngine.post_stock_movement()` — one call per line, `transaction_type='PURCHASE_RETURN'`, `quantity_change = -(return_qty + return_free_qty)`, same `item_batch_id` the goods were received into. This is explicitly the case `post_stock_movement()`'s own docstring already anticipates ("negative = stock OUT ... a Purchase Return") — no new stock-writing code.

> **Cancellation reversal:** cancelling a `Posted` purchase_return does NOT delete its stock effect or edit `purchase_return_item` rows. The Engine posts an equal-and-opposite `post_stock_movement()` call (`transaction_type='PURCHASE_RETURN_CANCEL'`, `quantity_change = +(return_qty + return_free_qty)`) and sets `status='Cancelled'` + `cancellation_reason` on the header — stock comes back in, full history stays visible.

---

## 2. Models Layer (SQL only — no business logic)

### 2.1 File: `models/purchase_return_model.py`

```python
"""
models/purchase_return_model.py

Purchase Return Model - Medical ERP V2

Project rule: "No SQL outside the Model." Mirrors models/sale_return_model.py's
shape (same two-cumulative-check pattern, adapted for paid+free qty).
SQL only, no business logic, no validation, no decisions -- all of that
belongs to engines/purchase_return_engine.py.
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
class PurchaseReturnSearchFilters:
    """Filter parameters for purchase return search/listing."""
    search_text: Optional[str] = None       # matches return_number, internal_ref_number, supplier_name (joined)
    supplier_id: Optional[int] = None
    purchase_invoice_id: Optional[int] = None
    status: Optional[str] = None            # 'Draft' | 'Posted' | 'Cancelled' | None (=all)
    settlement_mode: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


PURCHASE_RETURN_COLUMNS = (
    "return_number", "purchase_invoice_id", "supplier_id",
    "return_date_ad", "return_date_bs", "return_reason", "settlement_mode",
    "total_qty", "total_free_qty", "total_gross_amount", "total_discount_amount",
    "total_cc_amount", "grand_total", "status", "remarks",
)

PURCHASE_RETURN_ITEM_COLUMNS = (
    "purchase_invoice_item_id", "item_id", "item_batch_id", "batch_no",
    "expiry_month", "expiry_year", "return_qty", "return_free_qty", "rate",
    "discount_percent", "discount_amount", "cc_percent", "cc_amount",
    "amount", "remarks",
)


class PurchaseReturnModel:
    """Data-access layer for `purchase_return` + `purchase_return_item`. SQL only."""

    # ------------------------------------------------------------------ #
    # CREATE (header + lines, one transaction)
    # ------------------------------------------------------------------ #
    def insert_with_items(self, header_data: dict[str, Any], item_rows: list[dict[str, Any]]) -> int:
        """
        Inserts the purchase_return header and every purchase_return_item
        row in ONE database transaction. `header_data` must contain every
        column in PURCHASE_RETURN_COLUMNS plus created_by/created_at_ad/
        created_at_bs. Each dict in `item_rows` must contain every column
        in PURCHASE_RETURN_ITEM_COLUMNS. Returns the new purchase_return_id.

        NOTE: does NOT touch stock and does NOT validate cumulative return
        quantities -- the Engine calls get_returned_qty_for_invoice_item()
        per line BEFORE calling this, then calls
        ItemEngine.post_stock_movement() per line AFTER this insert
        succeeds, all inside the same logical operation.
        """
        header_columns = list(PURCHASE_RETURN_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)

        header_sql = f"""
            INSERT INTO purchase_return ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING purchase_return_id;
        """

        item_columns = ["purchase_return_id"] + list(PURCHASE_RETURN_ITEM_COLUMNS)
        item_col_sql = ", ".join(item_columns)
        item_placeholder_sql = ", ".join(f"%({c})s" for c in item_columns)
        item_sql = f"""
            INSERT INTO purchase_return_item ({item_col_sql})
            VALUES ({item_placeholder_sql});
        """

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    purchase_return_id = cur.fetchone()["purchase_return_id"]

                    for row in item_rows:
                        row = dict(row)
                        row["purchase_return_id"] = purchase_return_id
                        cur.execute(item_sql, row)

            return purchase_return_id
        except Exception:
            logger.exception("insert_with_items failed for purchase_return")
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # VALIDATION SUPPORT -- cumulative returned qty (paid + free, independently)
    # ------------------------------------------------------------------ #
    def get_returned_qty_for_invoice_item(self, purchase_invoice_item_id: int) -> dict[str, float]:
        """
        Returns {"returned_qty": ..., "returned_free_qty": ...} -- SUM of
        each across every purchase_return_item row referencing this
        purchase_invoice_item_id, counting ONLY returns whose parent
        purchase_return.status != 'Cancelled' and is_deleted = FALSE.
        The Engine subtracts these from the original line's qty/free_qty
        to get the remaining returnable amounts before allowing a new
        return line.
        """
        sql = """
            SELECT
                COALESCE(SUM(pri.return_qty), 0) AS returned_qty,
                COALESCE(SUM(pri.return_free_qty), 0) AS returned_free_qty
            FROM purchase_return_item pri
            JOIN purchase_return pr ON pr.purchase_return_id = pri.purchase_return_id
            WHERE pri.purchase_invoice_item_id = %(purchase_invoice_item_id)s
              AND pr.status != 'Cancelled'
              AND pr.is_deleted = FALSE;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"purchase_invoice_item_id": purchase_invoice_item_id})
                row = cur.fetchone()
                return {"returned_qty": float(row["returned_qty"]), "returned_free_qty": float(row["returned_free_qty"])}
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, purchase_return_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM purchase_return WHERE purchase_return_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": purchase_return_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_items_by_return_id(self, purchase_return_id: int) -> list[dict[str, Any]]:
        sql = "SELECT * FROM purchase_return_item WHERE purchase_return_id = %(id)s ORDER BY purchase_return_item_id;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": purchase_return_id})
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: PurchaseReturnSearchFilters) -> list[dict[str, Any]]:
        """Paginated search -- mirrors PurchaseInvoiceModel.search()'s dynamic WHERE-clause pattern."""
        conditions = ["pr.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}

        if filters.search_text:
            conditions.append(
                "(pr.return_number ILIKE %(search_text)s OR pi.internal_ref_number ILIKE %(search_text)s "
                "OR s.name ILIKE %(search_text)s)"
            )
            params["search_text"] = f"%{filters.search_text}%"
        if filters.supplier_id:
            conditions.append("pr.supplier_id = %(supplier_id)s")
            params["supplier_id"] = filters.supplier_id
        if filters.purchase_invoice_id:
            conditions.append("pr.purchase_invoice_id = %(purchase_invoice_id)s")
            params["purchase_invoice_id"] = filters.purchase_invoice_id
        if filters.status:
            conditions.append("pr.status = %(status)s")
            params["status"] = filters.status
        if filters.settlement_mode:
            conditions.append("pr.settlement_mode = %(settlement_mode)s")
            params["settlement_mode"] = filters.settlement_mode
        if filters.date_from_ad:
            conditions.append("pr.return_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("pr.return_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size

        sql = f"""
            SELECT pr.*, pi.internal_ref_number, s.name AS supplier_name
            FROM purchase_return pr
            JOIN purchase_invoice pi ON pi.purchase_invoice_id = pr.purchase_invoice_id
            JOIN supplier s ON s.supplier_id = pr.supplier_id
            WHERE {where_sql}
            ORDER BY pr.purchase_return_id DESC
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
    def cancel(self, purchase_return_id: int, cancellation_reason: str, updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE purchase_return
            SET status = 'Cancelled',
                cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s,
                updated_at_ad = %(updated_at_ad)s,
                updated_at_bs = %(updated_at_bs)s
            WHERE purchase_return_id = %(purchase_return_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "purchase_return_id": purchase_return_id,
                        "cancellation_reason": cancellation_reason,
                        "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad,
                        "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # SOFT DELETE (Draft only -- enforced in the Engine, see Part 2)
    # ------------------------------------------------------------------ #
    def soft_delete(self, purchase_return_id: int, deleted_by: int,
                     deleted_at_ad: Any, deleted_at_bs: str) -> None:
        sql = """
            UPDATE purchase_return
            SET is_deleted = TRUE,
                deleted_by = %(deleted_by)s,
                deleted_at_ad = %(deleted_at_ad)s,
                deleted_at_bs = %(deleted_at_bs)s
            WHERE purchase_return_id = %(purchase_return_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "purchase_return_id": purchase_return_id,
                        "deleted_by": deleted_by,
                        "deleted_at_ad": deleted_at_ad,
                        "deleted_at_bs": deleted_at_bs,
                    })
        finally:
            conn.close()
```

### 2.2 Extension to existing `models/purchase_invoice_model.py`

Add one read-only helper needed by the Return screen — mirrors `SaleInvoiceModel.get_returnable_items()` from Sale Return Part 1, adapted for the paid+free split:

```python
def get_returnable_items(self, purchase_invoice_id: int) -> list[dict[str, Any]]:
    """
    Returns every purchase_invoice_item row for a posted invoice, joined
    with already-returned paid qty AND already-returned free qty, so the
    Engine/Screen can compute both remaining returnable amounts per line
    without a second round-trip.
    """
    sql = """
        SELECT
            pii.*,
            COALESCE(SUM(pri.return_qty) FILTER (WHERE pr.status != 'Cancelled' AND pr.is_deleted = FALSE), 0) AS already_returned_qty,
            COALESCE(SUM(pri.return_free_qty) FILTER (WHERE pr.status != 'Cancelled' AND pr.is_deleted = FALSE), 0) AS already_returned_free_qty
        FROM purchase_invoice_item pii
        LEFT JOIN purchase_return_item pri ON pri.purchase_invoice_item_id = pii.purchase_invoice_item_id
        LEFT JOIN purchase_return pr ON pr.purchase_return_id = pri.purchase_return_id
        WHERE pii.purchase_invoice_id = %(purchase_invoice_id)s
        GROUP BY pii.purchase_invoice_item_id
        ORDER BY pii.purchase_invoice_item_id;
    """
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
            cur.execute(sql, {"purchase_invoice_id": purchase_invoice_id})
            return cur.fetchall()
    finally:
        conn.close()
```

---

## 3. Glossary

| Term | Meaning |
|---|---|
| **Returnable Qty (paid)** | `purchase_invoice_item.qty − already_returned_qty`. **Returnable Free Qty** | `purchase_invoice_item.free_qty − already_returned_free_qty`. Tracked and validated completely independently — a line can be fully returned on the paid side while still having free units left, or vice versa. |
| **settlement_mode** | How the return's value is settled with the supplier: `Adjust Against Payable` (default — reduces what we owe this supplier), `Supplier Advance` (added to our credit balance, usable on a future purchase), `Cash Refund` (supplier hands cash back now). Reserved for the future Accounts module's journal posting. |
| **Why free qty IS returnable here (unlike Sale Return)** | In Sale Return, free goods were a gift TO the customer, so the customer can't hand back something they didn't pay for as a "return." In Purchase Return, free goods were a gift FROM the supplier, but they are still real physical units sitting in our batch stock — if they're expired or defective, we return them to the supplier exactly like the paid units, just with 0 value attached (matching how they had 0 value on the original invoice line too). |
| **Same-Batch Reversal** | Returned stock always leaves from the exact `item_batch_id` it was received into — no batch re-selection. |
| **Cancellation vs Deletion** | Cancelling a Posted return reverses its stock effect with a new equal-and-opposite movement (stock comes back in) and requires `cancellation_reason`. Soft-delete (`is_deleted`) only hides a `Draft` return that was never posted. |

---

**Part 1 complete.** Waiting for your confirmation before Part 2 (Validators + Engine: `purchase_return_validator.py`, `purchase_return_engine.py` — independent paid/free cumulative-qty checks, proportional discount/cc calculation, stock reversal via `ItemEngine.post_stock_movement()`, cancellation reversal flow).
