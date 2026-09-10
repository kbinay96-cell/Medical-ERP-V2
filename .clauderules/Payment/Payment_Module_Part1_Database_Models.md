# Payment Module — Part 1: Database Schema & Models Layer

**Project:** Medical ERP V2
**Layer:** Database + Models (SQL only, no business logic — per project rule)
**Scope:** Supplier Payment only (money going OUT to suppliers against Purchase Invoices) — the mirror image of the Receipt module, same rules applied to the other side of the ledger.
**Depends on (already built):**
- `purchase_invoice` (Purchase Module Part 1) — `grand_total`, `supplier_id`, `invoice_date_ad`
- `purchase_return` (Purchase Return Part 1) — for outstanding adjustment, same role `sale_return` plays for Receipt
- `engines/date_engine.py` — BS↔AD conversion
- `engines/supplier_engine.py` / `models/supplier_model.py`
- `engines/exceptions.py` — EngineError, ValidationError, RecordNotFoundError, DuplicateRecordError
- `screens/cancellation_reason_dialog.py` (built in Sale Return Part 3) — reused as-is
- Reserved (not yet built): Accounts module — every Payment will eventually generate a Journal Entry (`Supplier Payable Dr, Cash/Bank Cr`) once double-entry is wired; this module posts nothing to a ledger yet, only reserves the shape.

---

## 0. Scope — CONFIRMED (mirrors Receipt Module Part 1 sec 0, applied to suppliers)

1. **Edit allowed, history never lost** — same audit-log design as Receipt, not append-only reversal.
2. **Auto-allocation is FIFO** — against the supplier's oldest open (unpaid/partially-paid) Purchase Invoice first.
3. **Advance / on-account handling** — leftover payment beyond all open invoices becomes an advance credit tied to this payment, auto-applied to the supplier's next new Purchase Invoice, oldest-advance-first.
4. **Cancellation requires a mandatory reason** — soft-delete + `cancellation_reason`, reusing the shared `CancellationReasonDialog`.
5. **Draft/Posted/Cancelled lifecycle.**
6. **Not yet a Journal Entry** — reserved shape only, same reservation pattern as Receipt.

---

## 1. Database Schema

### 1.1 `payment` (header)

```sql
CREATE TABLE IF NOT EXISTS payment (
    payment_id                SERIAL PRIMARY KEY,
    payment_number               VARCHAR(30) NOT NULL UNIQUE,     -- e.g. PYMT-0001
    supplier_id                     INTEGER NOT NULL REFERENCES supplier(supplier_id),
    payment_date_ad                   DATE NOT NULL,
    payment_date_bs                     VARCHAR(10) NOT NULL,
    payment_mode                          VARCHAR(30) NOT NULL,      -- Cash, Bank Transfer, Cheque, Card, Other
    amount                                   NUMERIC(14,2) NOT NULL,    -- total amount paid -- the ONLY manually entered money figure
    allocated_amount                          NUMERIC(14,2) NOT NULL DEFAULT 0,  -- SUM of payment_allocation.allocated_amount -- Engine-maintained
    advance_amount                              NUMERIC(14,2) NOT NULL DEFAULT 0,  -- amount - allocated_amount at creation time
    reference_no                                  VARCHAR(50),                -- cheque number / bank transaction ref, nullable
    bank_name                                       VARCHAR(100),               -- nullable
    status                                             VARCHAR(20) NOT NULL DEFAULT 'Posted',
    cancellation_reason                                   TEXT,        -- mandatory only when status='Cancelled'
    remarks                                                 TEXT,
    is_deleted                                               BOOLEAN NOT NULL DEFAULT FALSE,
    created_by                                                 INTEGER NOT NULL,
    created_at_ad                                               TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at_bs                                                VARCHAR(10) NOT NULL,
    updated_by                                                     INTEGER,
    updated_at_ad                                                   TIMESTAMP,
    updated_at_bs                                                    VARCHAR(10),
    deleted_by                                                         INTEGER,
    deleted_at_ad                                                       TIMESTAMP,
    deleted_at_bs                                                        VARCHAR(10),

    CONSTRAINT chk_payment_status CHECK (status IN ('Draft', 'Posted', 'Cancelled')),
    CONSTRAINT chk_payment_payment_mode CHECK (payment_mode IN ('Cash', 'Bank Transfer', 'Cheque', 'Card', 'Other')),
    CONSTRAINT chk_payment_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_payment_allocation_not_exceed CHECK (allocated_amount + advance_amount <= amount)
);

CREATE INDEX IF NOT EXISTS idx_payment_supplier ON payment (supplier_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_payment_date ON payment (payment_date_ad) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_payment_status ON payment (status) WHERE is_deleted = FALSE;

COMMENT ON COLUMN payment.advance_amount IS 'The portion of this payment left unallocated at creation time. Consumed over time as future Purchase Invoices are created -- see payment_advance_usage.';
COMMENT ON COLUMN payment.cancellation_reason IS 'Required whenever status is set to Cancelled. Cancelling reverses this payment''s effect on supplier outstanding via status change alone -- payment_allocation rows are never deleted, only ignored once the parent is Cancelled.';
```

### 1.2 `payment_allocation` (which invoices this payment paid down)

```sql
CREATE TABLE IF NOT EXISTS payment_allocation (
    payment_allocation_id    SERIAL PRIMARY KEY,
    payment_id                  INTEGER NOT NULL REFERENCES payment(payment_id),
    purchase_invoice_id            INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),
    allocated_amount                  NUMERIC(14,2) NOT NULL,
    is_auto_allocated                   BOOLEAN NOT NULL DEFAULT TRUE,   -- TRUE = FIFO engine matched it, FALSE = user manually re-targeted
    remarks                               TEXT,

    CONSTRAINT chk_payment_allocation_positive CHECK (allocated_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_allocation_payment ON payment_allocation (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_allocation_invoice ON payment_allocation (purchase_invoice_id);

COMMENT ON COLUMN payment_allocation.purchase_invoice_id IS 'SUM(allocated_amount) across every payment_allocation row for a given purchase_invoice_id, restricted to payments with status != Cancelled, is the total amount ever paid toward that invoice. purchase_invoice.grand_total minus that sum (further reduced by any Purchase Return with settlement_mode=''Adjust Against Payable'') is that invoice''s live outstanding balance.';
```

### 1.3 `payment_advance_usage` (tracks how a payment's leftover advance gets consumed later)

```sql
CREATE TABLE IF NOT EXISTS payment_advance_usage (
    payment_advance_usage_id  SERIAL PRIMARY KEY,
    payment_id                   INTEGER NOT NULL REFERENCES payment(payment_id),
    purchase_invoice_id             INTEGER NOT NULL REFERENCES purchase_invoice(purchase_invoice_id),   -- the NEW invoice this advance was applied to
    used_amount                       NUMERIC(14,2) NOT NULL,
    used_by                             INTEGER NOT NULL,
    used_at_ad                           TIMESTAMP NOT NULL DEFAULT NOW(),
    used_at_bs                            VARCHAR(10) NOT NULL,

    CONSTRAINT chk_payment_advance_usage_positive CHECK (used_amount > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_advance_usage_payment ON payment_advance_usage (payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_advance_usage_invoice ON payment_advance_usage (purchase_invoice_id);

COMMENT ON TABLE payment_advance_usage IS 'A payment''s remaining usable advance = payment.advance_amount - SUM(used_amount) across its usage rows. Append-only, same reasoning as receipt_advance_usage.';
```

### 1.4 `payment_audit_log` (edit history)

```sql
CREATE TABLE IF NOT EXISTS payment_audit_log (
    payment_audit_log_id      SERIAL PRIMARY KEY,
    payment_id                   INTEGER NOT NULL REFERENCES payment(payment_id),
    changed_field                   VARCHAR(100) NOT NULL,   -- e.g. 'amount', 'allocation:purchase_invoice_id=42'
    old_value                         TEXT,
    new_value                           TEXT,
    changed_by                           INTEGER NOT NULL,
    changed_at_ad                          TIMESTAMP NOT NULL DEFAULT NOW(),
    changed_at_bs                           VARCHAR(10) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payment_audit_log_payment ON payment_audit_log (payment_id);

COMMENT ON TABLE payment_audit_log IS 'Append-only, one row per changed field per edit -- identical design to receipt_audit_log, mirrored for the supplier side.';
```

---

## 2. Models Layer (SQL only — no business logic)

### 2.1 File: `models/payment_model.py`

```python
"""
models/payment_model.py

Payment Model - Medical ERP V2

Project rule: "No SQL outside the Model." Mirrors models/receipt_model.py's
shape exactly, applied to the supplier/purchase side. SQL only.
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
class PaymentSearchFilters:
    search_text: Optional[str] = None       # matches payment_number, supplier name (joined), reference_no
    supplier_id: Optional[int] = None
    status: Optional[str] = None
    payment_mode: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


PAYMENT_COLUMNS = (
    "payment_number", "supplier_id", "payment_date_ad", "payment_date_bs",
    "payment_mode", "amount", "allocated_amount", "advance_amount",
    "reference_no", "bank_name", "status", "remarks",
)

PAYMENT_ALLOCATION_COLUMNS = ("purchase_invoice_id", "allocated_amount", "is_auto_allocated", "remarks")


class PaymentModel:
    """Data-access layer for `payment` + `payment_allocation` +
    `payment_advance_usage` + `payment_audit_log`. SQL only."""

    # ------------------------------------------------------------------ #
    # CREATE (header + allocations, one transaction)
    # ------------------------------------------------------------------ #
    def insert_with_allocations(self, header_data: dict[str, Any], allocation_rows: list[dict[str, Any]]) -> int:
        header_columns = list(PAYMENT_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)

        header_sql = f"""
            INSERT INTO payment ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING payment_id;
        """

        allocation_columns = ["payment_id"] + list(PAYMENT_ALLOCATION_COLUMNS)
        allocation_col_sql = ", ".join(allocation_columns)
        allocation_placeholder_sql = ", ".join(f"%({c})s" for c in allocation_columns)
        allocation_sql = f"""
            INSERT INTO payment_allocation ({allocation_col_sql})
            VALUES ({allocation_placeholder_sql});
        """

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    payment_id = cur.fetchone()["payment_id"]

                    for row in allocation_rows:
                        row = dict(row)
                        row["payment_id"] = payment_id
                        cur.execute(allocation_sql, row)

            return payment_id
        except Exception:
            logger.exception("insert_with_allocations failed for payment")
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # FIFO SUPPORT -- supplier's open invoices, oldest first
    # ------------------------------------------------------------------ #
    def get_outstanding_invoices_for_supplier(self, supplier_id: int) -> list[dict[str, Any]]:
        """
        Mirrors ReceiptModel.get_outstanding_invoices_for_customer().
        outstanding_amount = grand_total
                              - COALESCE(SUM(payment_allocation via non-cancelled payments), 0)
                              - COALESCE(SUM(purchase_return.grand_total WHERE settlement_mode='Adjust Against Payable' AND status != 'Cancelled'), 0)
        Ordered oldest invoice_date_ad first -- the FIFO rule.
        """
        sql = """
            SELECT
                pi.purchase_invoice_id,
                pi.internal_ref_number,
                pi.invoice_date_ad,
                pi.grand_total,
                pi.grand_total
                    - COALESCE(pa_sum.total_allocated, 0)
                    - COALESCE(pr_sum.total_adjusted, 0) AS outstanding_amount
            FROM purchase_invoice pi
            LEFT JOIN (
                SELECT pa.purchase_invoice_id, SUM(pa.allocated_amount) AS total_allocated
                FROM payment_allocation pa
                JOIN payment p ON p.payment_id = pa.payment_id
                WHERE p.status != 'Cancelled' AND p.is_deleted = FALSE
                GROUP BY pa.purchase_invoice_id
            ) pa_sum ON pa_sum.purchase_invoice_id = pi.purchase_invoice_id
            LEFT JOIN (
                SELECT pr.purchase_invoice_id, SUM(pr.grand_total) AS total_adjusted
                FROM purchase_return pr
                WHERE pr.settlement_mode = 'Adjust Against Payable'
                  AND pr.status != 'Cancelled' AND pr.is_deleted = FALSE
                GROUP BY pr.purchase_invoice_id
            ) pr_sum ON pr_sum.purchase_invoice_id = pi.purchase_invoice_id
            WHERE pi.supplier_id = %(supplier_id)s
              AND pi.status = 'Posted'
              AND pi.is_deleted = FALSE
            HAVING pi.grand_total
                    - COALESCE(pa_sum.total_allocated, 0)
                    - COALESCE(pr_sum.total_adjusted, 0) > 0
            ORDER BY pi.invoice_date_ad ASC, pi.purchase_invoice_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"supplier_id": supplier_id})
                return cur.fetchall()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # ADVANCE SUPPORT
    # ------------------------------------------------------------------ #
    def get_available_advance_for_supplier(self, supplier_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT
                p.payment_id,
                p.payment_number,
                p.payment_date_ad,
                p.advance_amount,
                p.advance_amount - COALESCE(au_sum.total_used, 0) AS remaining_advance
            FROM payment p
            LEFT JOIN (
                SELECT payment_id, SUM(used_amount) AS total_used
                FROM payment_advance_usage
                GROUP BY payment_id
            ) au_sum ON au_sum.payment_id = p.payment_id
            WHERE p.supplier_id = %(supplier_id)s
              AND p.status != 'Cancelled' AND p.is_deleted = FALSE
              AND p.advance_amount > 0
            HAVING p.advance_amount - COALESCE(au_sum.total_used, 0) > 0
            ORDER BY p.payment_date_ad ASC, p.payment_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"supplier_id": supplier_id})
                return cur.fetchall()
        finally:
            conn.close()

    def insert_advance_usage(self, payment_id: int, purchase_invoice_id: int, used_amount: float,
                              used_by: int, used_at_ad: Any, used_at_bs: str) -> int:
        sql = """
            INSERT INTO payment_advance_usage
                (payment_id, purchase_invoice_id, used_amount, used_by, used_at_ad, used_at_bs)
            VALUES (%(payment_id)s, %(purchase_invoice_id)s, %(used_amount)s, %(used_by)s, %(used_at_ad)s, %(used_at_bs)s)
            RETURNING payment_advance_usage_id;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(sql, {
                        "payment_id": payment_id, "purchase_invoice_id": purchase_invoice_id,
                        "used_amount": used_amount, "used_by": used_by,
                        "used_at_ad": used_at_ad, "used_at_bs": used_at_bs,
                    })
                    return cur.fetchone()["payment_advance_usage_id"]
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # AUDIT LOG
    # ------------------------------------------------------------------ #
    def insert_audit_log_entries(self, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        sql = """
            INSERT INTO payment_audit_log
                (payment_id, changed_field, old_value, new_value, changed_by, changed_at_ad, changed_at_bs)
            VALUES (%(payment_id)s, %(changed_field)s, %(old_value)s, %(new_value)s, %(changed_by)s, %(changed_at_ad)s, %(changed_at_bs)s);
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    for entry in entries:
                        cur.execute(sql, entry)
        finally:
            conn.close()

    def get_audit_log(self, payment_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM payment_audit_log
            WHERE payment_id = %(payment_id)s
            ORDER BY changed_at_ad ASC, payment_audit_log_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"payment_id": payment_id})
                return cur.fetchall()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, payment_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM payment WHERE payment_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": payment_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_allocations_by_payment_id(self, payment_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT pa.*, pi.internal_ref_number
            FROM payment_allocation pa
            JOIN purchase_invoice pi ON pi.purchase_invoice_id = pa.purchase_invoice_id
            WHERE pa.payment_id = %(id)s
            ORDER BY pa.payment_allocation_id;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": payment_id})
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: PaymentSearchFilters) -> list[dict[str, Any]]:
        conditions = ["p.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}

        if filters.search_text:
            conditions.append(
                "(p.payment_number ILIKE %(search_text)s OR s.name ILIKE %(search_text)s "
                "OR p.reference_no ILIKE %(search_text)s)"
            )
            params["search_text"] = f"%{filters.search_text}%"
        if filters.supplier_id:
            conditions.append("p.supplier_id = %(supplier_id)s")
            params["supplier_id"] = filters.supplier_id
        if filters.status:
            conditions.append("p.status = %(status)s")
            params["status"] = filters.status
        if filters.payment_mode:
            conditions.append("p.payment_mode = %(payment_mode)s")
            params["payment_mode"] = filters.payment_mode
        if filters.date_from_ad:
            conditions.append("p.payment_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("p.payment_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size

        sql = f"""
            SELECT p.*, s.name AS supplier_name
            FROM payment p
            JOIN supplier s ON s.supplier_id = p.supplier_id
            WHERE {where_sql}
            ORDER BY p.payment_id DESC
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
    # UPDATE (header fields, always preceded by an audit-log insert,
    # called by the Engine)
    # ------------------------------------------------------------------ #
    def update_header_fields(self, payment_id: int, changed_fields: dict[str, Any],
                              updated_by: int, updated_at_ad: Any, updated_at_bs: str) -> None:
        if not changed_fields:
            return
        set_clause = ", ".join(f"{col} = %({col})s" for col in changed_fields)
        sql = f"""
            UPDATE payment
            SET {set_clause}, updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE payment_id = %(payment_id)s;
        """
        params = dict(changed_fields)
        params.update({"payment_id": payment_id, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs})
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            conn.close()

    def replace_allocations(self, payment_id: int, new_allocation_rows: list[dict[str, Any]]) -> None:
        delete_sql = "DELETE FROM payment_allocation WHERE payment_id = %(payment_id)s;"
        insert_columns = ["payment_id"] + list(PAYMENT_ALLOCATION_COLUMNS)
        insert_col_sql = ", ".join(insert_columns)
        insert_placeholder_sql = ", ".join(f"%({c})s" for c in insert_columns)
        insert_sql = f"INSERT INTO payment_allocation ({insert_col_sql}) VALUES ({insert_placeholder_sql});"

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(delete_sql, {"payment_id": payment_id})
                    for row in new_allocation_rows:
                        row = dict(row)
                        row["payment_id"] = payment_id
                        cur.execute(insert_sql, row)
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # CANCEL (status change + mandatory reason -- never a delete)
    # ------------------------------------------------------------------ #
    def cancel(self, payment_id: int, cancellation_reason: str, updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE payment
            SET status = 'Cancelled', cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE payment_id = %(payment_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "payment_id": payment_id, "cancellation_reason": cancellation_reason,
                        "updated_by": updated_by, "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # SOFT DELETE (Draft only -- enforced in the Engine)
    # ------------------------------------------------------------------ #
    def soft_delete(self, payment_id: int, deleted_by: int, deleted_at_ad: Any, deleted_at_bs: str) -> None:
        sql = """
            UPDATE payment
            SET is_deleted = TRUE, deleted_by = %(deleted_by)s, deleted_at_ad = %(deleted_at_ad)s, deleted_at_bs = %(deleted_at_bs)s
            WHERE payment_id = %(payment_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "payment_id": payment_id, "deleted_by": deleted_by,
                        "deleted_at_ad": deleted_at_ad, "deleted_at_bs": deleted_at_bs,
                    })
        finally:
            conn.close()
```

---

## 3. Glossary

| Term | Meaning |
|---|---|
| **Outstanding Amount (Supplier side)** | `purchase_invoice.grand_total − allocated (via non-cancelled payments) − adjusted (via non-cancelled Purchase Returns with settlement_mode='Adjust Against Payable')`. |
| **FIFO Auto-Allocation** | Same principle as Receipt: `get_outstanding_invoices_for_supplier()` returns oldest-first, Engine fills top-to-bottom. |
| **Advance (Supplier side)** | Leftover payment after every open invoice is satisfied; consumed later via `payment_advance_usage`, oldest-first. |
| **Edit + Audit Log** | Identical design to Receipt — a Payment stays one editable record, every change logged in `payment_audit_log` before being applied. |

---

**Part 1 complete.** Waiting for your confirmation before Part 2 (Validators + Engine: `payment_validator.py`, `payment_engine.py` — mirrors `receipt_engine.py` exactly, FIFO against supplier invoices, advance consumption against future Purchase Invoices via a hook into `PurchaseEngine.create_purchase_invoice()`).
