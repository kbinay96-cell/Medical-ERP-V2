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