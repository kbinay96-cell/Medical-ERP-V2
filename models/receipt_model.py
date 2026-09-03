"""
models/receipt_model.py

Receipt Model - Medical ERP V2

Project rule: "No SQL outside the Model." SQL only, no business logic,
no FIFO decisions, no advance-consumption decisions -- all of that
belongs to engines/receipt_engine.py.
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
class ReceiptSearchFilters:
    search_text: Optional[str] = None       # matches receipt_number, customer name (joined), reference_no
    customer_id: Optional[int] = None
    status: Optional[str] = None
    payment_mode: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


RECEIPT_COLUMNS = (
    "receipt_number", "customer_id", "receipt_date_ad", "receipt_date_bs",
    "payment_mode", "amount", "allocated_amount", "advance_amount",
    "reference_no", "bank_name", "status", "remarks",
)

RECEIPT_ALLOCATION_COLUMNS = ("sale_invoice_id", "allocated_amount", "is_auto_allocated", "remarks")


class ReceiptModel:
    """Data-access layer for `receipt` + `receipt_allocation` +
    `receipt_advance_usage` + `receipt_audit_log`. SQL only."""

    # ------------------------------------------------------------------ #
    # CREATE (header + allocations, one transaction)
    # ------------------------------------------------------------------ #
    def insert_with_allocations(self, header_data: dict[str, Any], allocation_rows: list[dict[str, Any]]) -> int:
        """
        Inserts the receipt header and every receipt_allocation row in
        ONE database transaction. `header_data` must contain every
        column in RECEIPT_COLUMNS plus created_by/created_at_ad/
        created_at_bs. Each dict in `allocation_rows` must contain every
        column in RECEIPT_ALLOCATION_COLUMNS. Returns the new receipt_id.

        NOTE: this does NOT decide the FIFO allocation or compute
        advance_amount -- the Engine computes those BEFORE calling this,
        so header_data.allocated_amount/advance_amount already reflect
        the final values.
        """
        header_columns = list(RECEIPT_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)

        header_sql = f"""
            INSERT INTO receipt ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING receipt_id;
        """

        allocation_columns = ["receipt_id"] + list(RECEIPT_ALLOCATION_COLUMNS)
        allocation_col_sql = ", ".join(allocation_columns)
        allocation_placeholder_sql = ", ".join(f"%({c})s" for c in allocation_columns)
        allocation_sql = f"""
            INSERT INTO receipt_allocation ({allocation_col_sql})
            VALUES ({allocation_placeholder_sql});
        """

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    receipt_id = cur.fetchone()["receipt_id"]

                    for row in allocation_rows:
                        row = dict(row)
                        row["receipt_id"] = receipt_id
                        cur.execute(allocation_sql, row)

            return receipt_id
        except Exception:
            logger.exception("insert_with_allocations failed for receipt")
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # FIFO SUPPORT -- customer's open invoices, oldest first
    # ------------------------------------------------------------------ #
    def get_outstanding_invoices_for_customer(self, customer_id: int) -> list[dict[str, Any]]:
        """
        Returns every Posted, non-deleted sale_invoice for this customer
        with a live-computed `outstanding_amount` column, ORDERED BY
        invoice_date_ad ASC (oldest first) -- this ordering IS the FIFO
        rule; the Engine simply consumes rows top-to-bottom. Only rows
        where outstanding_amount > 0 are returned.

        outstanding_amount = grand_total
                              - COALESCE(SUM(receipt_allocation via non-cancelled receipts), 0)
                              - COALESCE(SUM(sale_return.grand_total WHERE refund_mode='Adjust Against Invoice' AND status != 'Cancelled'), 0)

        The sale_return subtraction is included NOW (even though the
        Accounts module isn't built yet) because Sale Return was built
        BEFORE Receipt in this project's order -- ignoring it here would
        make outstanding wrong for any invoice that already had a return
        applied against it.
        """
        sql = """
            SELECT
                si.sale_invoice_id,
                si.invoice_number,
                si.invoice_date_ad,
                si.grand_total,
                si.grand_total
                    - COALESCE(ra_sum.total_allocated, 0)
                    - COALESCE(sr_sum.total_adjusted, 0) AS outstanding_amount
            FROM sale_invoice si
            LEFT JOIN (
                SELECT ra.sale_invoice_id, SUM(ra.allocated_amount) AS total_allocated
                FROM receipt_allocation ra
                JOIN receipt r ON r.receipt_id = ra.receipt_id
                WHERE r.status != 'Cancelled' AND r.is_deleted = FALSE
                GROUP BY ra.sale_invoice_id
            ) ra_sum ON ra_sum.sale_invoice_id = si.sale_invoice_id
            LEFT JOIN (
                SELECT sr.sale_invoice_id, SUM(sr.grand_total) AS total_adjusted
                FROM sale_return sr
                WHERE sr.refund_mode = 'Adjust Against Invoice'
                  AND sr.status != 'Cancelled' AND sr.is_deleted = FALSE
                GROUP BY sr.sale_invoice_id
            ) sr_sum ON sr_sum.sale_invoice_id = si.sale_invoice_id
            WHERE si.customer_id = %(customer_id)s
              AND si.status = 'Posted'
              AND si.is_deleted = FALSE
            HAVING si.grand_total
                    - COALESCE(ra_sum.total_allocated, 0)
                    - COALESCE(sr_sum.total_adjusted, 0) > 0
            ORDER BY si.invoice_date_ad ASC, si.sale_invoice_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"customer_id": customer_id})
                return cur.fetchall()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # ADVANCE SUPPORT
    # ------------------------------------------------------------------ #
    def get_available_advance_for_customer(self, customer_id: int) -> list[dict[str, Any]]:
        """
        Returns every non-cancelled receipt for this customer with
        advance_amount > 0, alongside its remaining usable amount
        (advance_amount - SUM(receipt_advance_usage.used_amount)),
        ORDERED BY receipt_date_ad ASC (oldest advance consumed first --
        same FIFO principle applied to advance as to invoices).
        Only rows where remaining > 0 are returned.
        """
        sql = """
            SELECT
                r.receipt_id,
                r.receipt_number,
                r.receipt_date_ad,
                r.advance_amount,
                r.advance_amount - COALESCE(au_sum.total_used, 0) AS remaining_advance
            FROM receipt r
            LEFT JOIN (
                SELECT receipt_id, SUM(used_amount) AS total_used
                FROM receipt_advance_usage
                GROUP BY receipt_id
            ) au_sum ON au_sum.receipt_id = r.receipt_id
            WHERE r.customer_id = %(customer_id)s
              AND r.status != 'Cancelled' AND r.is_deleted = FALSE
              AND r.advance_amount > 0
            HAVING r.advance_amount - COALESCE(au_sum.total_used, 0) > 0
            ORDER BY r.receipt_date_ad ASC, r.receipt_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"customer_id": customer_id})
                return cur.fetchall()
        finally:
            conn.close()

    def insert_advance_usage(self, receipt_id: int, sale_invoice_id: int, used_amount: float,
                              used_by: int, used_at_ad: Any, used_at_bs: str) -> int:
        sql = """
            INSERT INTO receipt_advance_usage
                (receipt_id, sale_invoice_id, used_amount, used_by, used_at_ad, used_at_bs)
            VALUES (%(receipt_id)s, %(sale_invoice_id)s, %(used_amount)s, %(used_by)s, %(used_at_ad)s, %(used_at_bs)s)
            RETURNING receipt_advance_usage_id;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(sql, {
                        "receipt_id": receipt_id, "sale_invoice_id": sale_invoice_id,
                        "used_amount": used_amount, "used_by": used_by,
                        "used_at_ad": used_at_ad, "used_at_bs": used_at_bs,
                    })
                    return cur.fetchone()["receipt_advance_usage_id"]
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # AUDIT LOG
    # ------------------------------------------------------------------ #
    def insert_audit_log_entries(self, entries: list[dict[str, Any]]) -> None:
        """
        Each entry: {"receipt_id", "changed_field", "old_value",
        "new_value", "changed_by", "changed_at_ad", "changed_at_bs"}.
        Called by the Engine BEFORE applying an edit -- see Part 2.
        """
        if not entries:
            return
        sql = """
            INSERT INTO receipt_audit_log
                (receipt_id, changed_field, old_value, new_value, changed_by, changed_at_ad, changed_at_bs)
            VALUES (%(receipt_id)s, %(changed_field)s, %(old_value)s, %(new_value)s, %(changed_by)s, %(changed_at_ad)s, %(changed_at_bs)s);
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    for entry in entries:
                        cur.execute(sql, entry)
        finally:
            conn.close()

    def get_audit_log(self, receipt_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM receipt_audit_log
            WHERE receipt_id = %(receipt_id)s
            ORDER BY changed_at_ad ASC, receipt_audit_log_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"receipt_id": receipt_id})
                return cur.fetchall()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_by_id(self, receipt_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM receipt WHERE receipt_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": receipt_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_allocations_by_receipt_id(self, receipt_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT ra.*, si.invoice_number
            FROM receipt_allocation ra
            JOIN sale_invoice si ON si.sale_invoice_id = ra.sale_invoice_id
            WHERE ra.receipt_id = %(id)s
            ORDER BY ra.receipt_allocation_id;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": receipt_id})
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: ReceiptSearchFilters) -> list[dict[str, Any]]:
        conditions = ["r.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}

        if filters.search_text:
            conditions.append(
                "(r.receipt_number ILIKE %(search_text)s OR c.name ILIKE %(search_text)s "
                "OR r.reference_no ILIKE %(search_text)s)"
            )
            params["search_text"] = f"%{filters.search_text}%"
        if filters.customer_id:
            conditions.append("r.customer_id = %(customer_id)s")
            params["customer_id"] = filters.customer_id
        if filters.status:
            conditions.append("r.status = %(status)s")
            params["status"] = filters.status
        if filters.payment_mode:
            conditions.append("r.payment_mode = %(payment_mode)s")
            params["payment_mode"] = filters.payment_mode
        if filters.date_from_ad:
            conditions.append("r.receipt_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("r.receipt_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size

        sql = f"""
            SELECT r.*, c.name AS customer_name
            FROM receipt r
            JOIN customer c ON c.customer_id = r.customer_id
            WHERE {where_sql}
            ORDER BY r.receipt_id DESC
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
    # UPDATE (header fields only -- allocation edits go through
    # replace_allocations() below, both ALWAYS preceded by an audit-log
    # insert in the same transaction, called by the Engine)
    # ------------------------------------------------------------------ #
    def update_header_fields(self, receipt_id: int, changed_fields: dict[str, Any],
                              updated_by: int, updated_at_ad: Any, updated_at_bs: str) -> None:
        """`changed_fields` is a partial dict of only the columns being
        changed (e.g. {"payment_mode": "Bank Transfer", "reference_no": "TXN123"}).
        The Engine has already written the audit-log rows for these
        changes before calling this."""
        if not changed_fields:
            return
        set_clause = ", ".join(f"{col} = %({col})s" for col in changed_fields)
        sql = f"""
            UPDATE receipt
            SET {set_clause}, updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE receipt_id = %(receipt_id)s;
        """
        params = dict(changed_fields)
        params.update({"receipt_id": receipt_id, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs})
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            conn.close()

    def replace_allocations(self, receipt_id: int, new_allocation_rows: list[dict[str, Any]]) -> None:
        """Deletes all existing receipt_allocation rows for this receipt
        and inserts the new set, in one transaction. Only ever called by
        the Engine AFTER it has written audit-log entries describing
        exactly what changed (old invoice/amount -> new invoice/amount)
        -- this method itself has no memory of the prior state."""
        delete_sql = "DELETE FROM receipt_allocation WHERE receipt_id = %(receipt_id)s;"
        insert_columns = ["receipt_id"] + list(RECEIPT_ALLOCATION_COLUMNS)
        insert_col_sql = ", ".join(insert_columns)
        insert_placeholder_sql = ", ".join(f"%({c})s" for c in insert_columns)
        insert_sql = f"INSERT INTO receipt_allocation ({insert_col_sql}) VALUES ({insert_placeholder_sql});"

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(delete_sql, {"receipt_id": receipt_id})
                    for row in new_allocation_rows:
                        row = dict(row)
                        row["receipt_id"] = receipt_id
                        cur.execute(insert_sql, row)
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # CANCEL (status change + mandatory reason -- never a delete)
    # ------------------------------------------------------------------ #
    def cancel(self, receipt_id: int, cancellation_reason: str, updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE receipt
            SET status = 'Cancelled', cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE receipt_id = %(receipt_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "receipt_id": receipt_id, "cancellation_reason": cancellation_reason,
                        "updated_by": updated_by, "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # SOFT DELETE (Draft only -- enforced in the Engine)
    # ------------------------------------------------------------------ #
    def soft_delete(self, receipt_id: int, deleted_by: int, deleted_at_ad: Any, deleted_at_bs: str) -> None:
        sql = """
            UPDATE receipt
            SET is_deleted = TRUE, deleted_by = %(deleted_by)s, deleted_at_ad = %(deleted_at_ad)s, deleted_at_bs = %(deleted_at_bs)s
            WHERE receipt_id = %(receipt_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "receipt_id": receipt_id, "deleted_by": deleted_by,
                        "deleted_at_ad": deleted_at_ad, "deleted_at_bs": deleted_at_bs,
                    })
        finally:
            conn.close()