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