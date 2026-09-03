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