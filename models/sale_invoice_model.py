# models/sale_invoice_model.py
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
    search_text: Optional[str] = None
    customer_id: Optional[int] = None
    status: Optional[str] = None
    date_from_ad: Optional[str] = None
    date_to_ad: Optional[str] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50
    order_by: Optional[str] = None
    order_dir: str = "DESC"


_SORTABLE_COLUMNS = {
    "invoice_number": "si.invoice_number",
    "customer_name": "c.customer_name",
    "invoice_date_bs": "si.invoice_date_bs",
    "grand_total": "si.grand_total",
    "status": "si.status",
}


class SaleInvoiceModel:
    """Data-access layer for `sale_invoice` + `sale_invoice_item`. SQL only."""

    def insert_invoice(self, data: dict[str, Any]) -> int:
        keys = list(data.keys())
        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]
        sql = f"INSERT INTO sale_invoice ({cols}) VALUES ({placeholders}) RETURNING sale_invoice_id"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()["sale_invoice_id"]
                conn.commit()
                return int(new_id)

    def insert_invoice_item(self, sale_invoice_id: int, data: dict[str, Any]) -> int:
        payload = dict(data)
        payload["sale_invoice_id"] = sale_invoice_id
        keys = list(payload.keys())
        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        values = [payload[k] for k in keys]
        sql = (
            f"INSERT INTO sale_invoice_item ({cols}) VALUES ({placeholders}) "
            "RETURNING sale_invoice_item_id"
        )
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()["sale_invoice_item_id"]
                conn.commit()
                return int(new_id)

    def get_by_id(self, sale_invoice_id: int, include_deleted: bool = False) -> Optional[dict]:
        sql = "SELECT * FROM sale_invoice WHERE sale_invoice_id = %s"
        if not include_deleted:
            sql += " AND is_deleted = FALSE"
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, (sale_invoice_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_items_by_invoice(self, sale_invoice_id: int) -> list[dict]:
        sql = (
            "SELECT * FROM sale_invoice_item "
            "WHERE sale_invoice_id = %s ORDER BY sale_invoice_item_id"
        )
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, (sale_invoice_id,))
                return [dict(r) for r in cur.fetchall()]

    def get_last_invoice_sequence(self, prefix: str) -> int:
        sql = """
            SELECT COALESCE(MAX(
                CAST(REGEXP_REPLACE(invoice_number, %(prefix_pattern)s, '') AS INTEGER)
            ), 0) AS max_seq
            FROM sale_invoice
            WHERE invoice_number ~ %(pattern)s;
        """
        params = {
            "prefix_pattern": f"^{prefix}",
            "pattern": f"^{prefix}[0-9]+$",
        }
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return int(cur.fetchone()["max_seq"] or 0)

    def get_customer_outstanding(self, customer_id: int, exclude_invoice_id: Optional[int] = None) -> float:
        sql = """
            SELECT COALESCE(SUM(balance_amount), 0) AS total
            FROM sale_invoice
            WHERE customer_id = %s
              AND is_deleted = FALSE
              AND status = 'Posted'
              AND balance_amount > 0
        """
        params: list[Any] = [customer_id]
        if exclude_invoice_id is not None:
            sql += " AND sale_invoice_id <> %s"
            params.append(exclude_invoice_id)
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return float(cur.fetchone()["total"] or 0)

    def search(self, filters: SaleInvoiceSearchFilters) -> tuple[list[dict], int]:
        where_clauses: list[str] = []
        params: list[Any] = []

        if filters.search_text:
            where_clauses.append("(si.invoice_number ILIKE %s OR c.customer_name ILIKE %s)")
            like_val = f"%{filters.search_text}%"
            params.extend([like_val, like_val])

        if filters.customer_id:
            where_clauses.append("si.customer_id = %s")
            params.append(filters.customer_id)

        if filters.status:
            where_clauses.append("si.status = %s")
            params.append(filters.status)

        if filters.date_from_ad:
            where_clauses.append("si.invoice_date_ad >= %s")
            params.append(filters.date_from_ad)

        if filters.date_to_ad:
            where_clauses.append("si.invoice_date_ad <= %s")
            params.append(filters.date_to_ad)

        if not filters.include_deleted:
            where_clauses.append("si.is_deleted = FALSE")

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        count_sql = (
            "SELECT COUNT(*) AS total FROM sale_invoice si "
            "LEFT JOIN customers c ON si.customer_id = c.customer_id"
            + where_sql
        )

        order_column = _SORTABLE_COLUMNS.get(filters.order_by, "si.created_at_ad")
        order_direction = "ASC" if (filters.order_dir or "").upper() == "ASC" else "DESC"
        query_sql = (
            "SELECT si.*, c.customer_name "
            "FROM sale_invoice si "
            "LEFT JOIN customers c ON si.customer_id = c.customer_id "
            + where_sql
            + f" ORDER BY {order_column} {order_direction} "
            " LIMIT %s OFFSET %s"
        )

        limit = filters.page_size or 50
        offset = (max(1, filters.page) - 1) * limit
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(count_sql, params)
                total = int(cur.fetchone()["total"] or 0)
                cur.execute(query_sql, params + [limit, offset])
                rows = [dict(r) for r in cur.fetchall()]
                return rows, total

    def soft_delete(
        self,
        sale_invoice_id: int,
        deleted_by: int,
        deleted_at_ad,
        deleted_at_bs: str,
        reason: str,
    ) -> None:
        sql = """
            UPDATE sale_invoice
               SET is_deleted = TRUE,
                   status = 'Cancelled',
                   deleted_by = %s,
                   deleted_at_ad = %s,
                   deleted_at_bs = %s,
                   cancellation_reason = %s
             WHERE sale_invoice_id = %s
               AND is_deleted = FALSE
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (deleted_by, deleted_at_ad, deleted_at_bs, reason, sale_invoice_id),
                )
                conn.commit()
