# models/purchase_order_model.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, List, Tuple

def _get_connection():
    from database.db import get_connection
    return get_connection


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class PurchaseOrderSearchFilters:
    search_text: Optional[str] = None
    supplier_id: Optional[int] = None
    status: Optional[str] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


class PurchaseOrderModel:
    """Data-access layer for `purchase_order` + `purchase_order_item`."""

    def insert_order(self, data: dict[str, Any]) -> int:
        get_connection = _get_connection()
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]
        sql = f"INSERT INTO purchase_order ({cols}) VALUES ({vals}) RETURNING purchase_order_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    def insert_order_item(self, purchase_order_id: int, data: dict[str, Any]) -> int:
        get_connection = _get_connection()
        data = dict(data)
        data["purchase_order_id"] = purchase_order_id
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]
        sql = f"INSERT INTO purchase_order_item ({cols}) VALUES ({vals}) RETURNING po_item_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    def get_by_id(self, purchase_order_id: int, include_deleted: bool = False) -> Optional[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_order WHERE purchase_order_id = %s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_order_id,))
                return cur.fetchone()

    def get_items_by_order(self, purchase_order_id: int) -> List[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_order_item WHERE purchase_order_id = %s ORDER BY po_item_id"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_order_id,))
                return cur.fetchall()

    def get_open_order_items_for_item_ids(self, item_ids: List[int]) -> List[dict]:
        """Return open (Draft/Sent) PO rows for the provided item_ids across suppliers."""
        if not item_ids:
            return []
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = """
            SELECT poi.item_id,
                   po.purchase_order_id AS po_id,
                   po.po_number,
                   s.supplier_name,
                   poi.ordered_qty,
                   po.status
            FROM purchase_order_item poi
            JOIN purchase_order po ON poi.purchase_order_id = po.purchase_order_id
            LEFT JOIN supplier s ON po.supplier_id = s.supplier_id
            WHERE poi.item_id = ANY(%s)
              AND po.status IN ('Draft', 'Sent')
              AND po.is_deleted = FALSE
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (item_ids,))
                return cur.fetchall()

    def get_last_po_number_sequence(self, prefix: str) -> int:
        get_connection = _get_connection()
        sql = """
            SELECT MAX(NULLIF(REGEXP_REPLACE(po_number, '^\\D+', ''), '')::integer) AS max_seq
            FROM purchase_order
            WHERE po_number LIKE %s
        """
        like_pattern = f"{prefix}%"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (like_pattern,))
                res = cur.fetchone()
                return int(res[0]) if res and res[0] else 0

    def search(self, filters: PurchaseOrderSearchFilters) -> Tuple[List[dict], int]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        where_clauses = []
        params = []
        if filters.search_text:
            where_clauses.append("(po.po_number ILIKE %s OR s.supplier_name ILIKE %s)")
            like_val = f"%{filters.search_text}%"
            params.extend([like_val, like_val])
        if filters.supplier_id:
            where_clauses.append("po.supplier_id = %s")
            params.append(filters.supplier_id)
        if filters.status:
            where_clauses.append("po.status = %s")
            params.append(filters.status)
        if not filters.include_deleted:
            where_clauses.append("po.is_deleted = FALSE")
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        count_sql = "SELECT COUNT(1) FROM purchase_order po LEFT JOIN supplier s ON po.supplier_id = s.supplier_id" + where_sql
        query_sql = (
            "SELECT po.*, s.supplier_name "
            "FROM purchase_order po LEFT JOIN supplier s ON po.supplier_id = s.supplier_id "
            + where_sql +
            " ORDER BY po.created_at_ad DESC LIMIT %s OFFSET %s"
        )
        limit = filters.page_size or 50
        offset = (max(1, filters.page) - 1) * limit
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(count_sql, params)
                count_row = cur.fetchone()
                total = int(count_row["count"]) if count_row and "count" in count_row else int(count_row[0]) if count_row else 0
                cur.execute(query_sql, params + [limit, offset])
                rows = cur.fetchall()
                return rows, total

    def mark_status(self, purchase_order_id: int, status: str, updated_by: int, updated_at_ad, updated_at_bs: str) -> None:
        get_connection = _get_connection()
        sql = "UPDATE purchase_order SET status = %s, updated_by = %s, updated_at_ad = %s, updated_at_bs = %s WHERE purchase_order_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, updated_by, updated_at_ad, updated_at_bs, purchase_order_id))
                conn.commit()

    def soft_delete(self, purchase_order_id: int, deleted_by: int, deleted_at_ad, deleted_at_bs: str) -> None:
        get_connection = _get_connection()
        sql = "UPDATE purchase_order SET is_deleted = TRUE, deleted_by = %s, deleted_at_ad = %s, deleted_at_bs = %s WHERE purchase_order_id = %s"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (deleted_by, deleted_at_ad, deleted_at_bs, purchase_order_id))
                conn.commit()