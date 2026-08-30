# models/item_free_scheme_model.py
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ItemFreeSchemeModel:
    """Data-access layer for `item_free_scheme`. One row per (item_id,
    supplier_id) pair -- upsert semantics, no soft-delete (this is a
    lightweight, always-current suggestion, not an audited record)."""

    def get_by_item_supplier(self, item_id: int, supplier_id: int) -> Optional[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM item_free_scheme WHERE item_id = %s AND supplier_id = %s"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (item_id, supplier_id))
                return cur.fetchone()

    def upsert(
        self,
        item_id: int,
        supplier_id: int,
        scheme_qty: float,
        scheme_free_qty: float,
        current_user_id: int,
        updated_at_bs: Optional[str] = None,
    ) -> None:
        get_connection = _get_connection()
        sql = """
            INSERT INTO item_free_scheme
                (item_id, supplier_id, scheme_qty, scheme_free_qty, updated_by, updated_at_bs)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id, supplier_id) DO UPDATE SET
                scheme_qty = EXCLUDED.scheme_qty,
                scheme_free_qty = EXCLUDED.scheme_free_qty,
                updated_by = EXCLUDED.updated_by,
                updated_at_ad = NOW(),
                updated_at_bs = EXCLUDED.updated_at_bs
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (item_id, supplier_id, scheme_qty, scheme_free_qty, current_user_id, updated_at_bs),
                )
                conn.commit()