# models/purchase_invoice_model.py
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Optional, List, Tuple

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
    order_by: Optional[str] = None
    order_dir: str = "ASC"

_SORTABLE_COLUMNS = {
    "internal_ref_number": "pi.internal_ref_number",
    "invoice_number": "pi.invoice_number",
    "supplier_name": "s.supplier_name",
    "invoice_date_bs": "pi.invoice_date_bs",
    "grand_total": "pi.grand_total",
    "status": "pi.status",
}


class PurchaseInvoiceModel:
    """Data-access layer for `purchase_invoice` + `purchase_invoice_item`.
    SQL only, no business logic — mirrors repo model conventions."""

    def insert_invoice(self, data: dict[str, Any]) -> int:
        """Inserts one purchase_invoice header row. Expects a dict of column->value.
        Returns new purchase_invoice_id."""
        get_connection = _get_connection()
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals_placeholder = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]

        sql = f"INSERT INTO purchase_invoice ({cols}) VALUES ({vals_placeholder}) RETURNING purchase_invoice_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()["purchase_invoice_id"]
                conn.commit()
                return new_id

    def insert_invoice_item(self, purchase_invoice_id: int, data: dict[str, Any]) -> int:
        """Insert a line into purchase_invoice_item and return the new id."""
        get_connection = _get_connection()
        data = dict(data)  # copy
        data["purchase_invoice_id"] = purchase_invoice_id
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals_placeholder = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]

        sql = f"INSERT INTO purchase_invoice_item ({cols}) VALUES ({vals_placeholder}) RETURNING purchase_invoice_item_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()["purchase_invoice_item_id"]
                conn.commit()
                return new_id

    def update_invoice_item_batch_link(self, purchase_invoice_item_id: int, item_batch_id: int) -> None:
        """After ItemEngine.add_batch() succeeds, stamp item_batch_id onto the invoice line."""
        get_connection = _get_connection()
        sql = "UPDATE purchase_invoice_item SET item_batch_id = %s WHERE purchase_invoice_item_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (item_batch_id, purchase_invoice_item_id))
                conn.commit()

    def get_by_id(self, purchase_invoice_id: int, include_deleted: bool = False) -> Optional[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_invoice WHERE purchase_invoice_id = %s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_invoice_id,))
                row = cur.fetchone()
                return row

    def get_items_by_invoice(self, purchase_invoice_id: int) -> List[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_invoice_item WHERE purchase_invoice_id = %s ORDER BY purchase_invoice_item_id"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_invoice_id,))
                rows = cur.fetchall()
                return rows

    def exists_by_supplier_and_billno(self, supplier_id: int, invoice_number: str, exclude_id: Optional[int] = None) -> bool:
        """Duplicate-bill safety check."""
        get_connection = _get_connection()
        sql = "SELECT 1 FROM purchase_invoice WHERE supplier_id = %s AND invoice_number = %s AND is_deleted = FALSE"
        params: List[Any] = [supplier_id, invoice_number]
        if exclude_id is not None:
            sql += " AND purchase_invoice_id <> %s"
            params.append(exclude_id)
        sql += " LIMIT 1"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None

    def get_last_internal_ref_sequence(self, prefix: str) -> int:
        """
        Returns the highest numeric suffix currently used among
        internal_ref_number values starting with `prefix` (including
        soft-deleted rows, so numbers are never reused) — same pattern
        as SupplierModel.get_last_code_sequence(). Returns 0 if none exist.
        """
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(internal_ref_number, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM purchase_invoice
            WHERE internal_ref_number ~ %(pattern)s;
        """
        params = {
            "prefix_pattern": f"^{prefix}",
            "pattern": f"^{prefix}[0-9]+$",
        }
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, params)
                return cur.fetchone()["max_seq"]

    def search(self, filters: PurchaseInvoiceSearchFilters) -> Tuple[List[dict], int]:
        """Return (rows, total_count). Joins supplier for display convenience."""
        get_connection = _get_connection()
        factory = _dict_cursor_factory()

        where_clauses = []
        params: List[Any] = []

        if filters.search_text:
            where_clauses.append("(pi.internal_ref_number ILIKE %s OR pi.invoice_number ILIKE %s)")
            like_val = f"%{filters.search_text}%"
            params.extend([like_val, like_val])

        if filters.supplier_id:
            where_clauses.append("pi.supplier_id = %s")
            params.append(filters.supplier_id)

        if filters.status:
            where_clauses.append("pi.status = %s")
            params.append(filters.status)

        if filters.date_from_ad:
            where_clauses.append("pi.invoice_date_ad >= %s")
            params.append(filters.date_from_ad)

        if filters.date_to_ad:
            where_clauses.append("pi.invoice_date_ad <= %s")
            params.append(filters.date_to_ad)

        if not filters.include_deleted:
            where_clauses.append("pi.is_deleted = FALSE")

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_sql = "SELECT COUNT(*) AS total FROM purchase_invoice pi" + where_sql

        order_column = _SORTABLE_COLUMNS.get(filters.order_by, "pi.created_at_ad")
        order_direction = "DESC" if (filters.order_dir or "").upper() == "DESC" else "ASC"

        query_sql = (
            "SELECT pi.*, s.supplier_name "
            "FROM purchase_invoice pi "
            "LEFT JOIN supplier s ON pi.supplier_id = s.supplier_id "
            + where_sql +
            f" ORDER BY {order_column} {order_direction} "
            " LIMIT %s OFFSET %s"
        )

        limit = filters.page_size or 50
        offset = (max(1, filters.page) - 1) * limit
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(count_sql, params)
                count_row = cur.fetchone()
                total = int(count_row["total"]) if count_row else 0

                cur.execute(query_sql, params + [limit, offset])
                rows = cur.fetchall()
                return rows, total

    def soft_delete(self, purchase_invoice_id: int, deleted_by: int, deleted_at_ad: str, deleted_at_bs: str) -> None:
        get_connection = _get_connection()
        sql = "UPDATE purchase_invoice SET is_deleted = TRUE, deleted_by = %s, deleted_at_ad = %s, deleted_at_bs = %s WHERE purchase_invoice_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (deleted_by, deleted_at_ad, deleted_at_bs, purchase_invoice_id))
                conn.commit()