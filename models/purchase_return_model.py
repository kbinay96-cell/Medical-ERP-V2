# models/purchase_return_model.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, List

def _get_connection():
    from database.db import get_connection
    return get_connection


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class PurchaseReturnModel:
    """Data-access layer for purchase_return + purchase_return_item (Phase-2)."""

    def insert_return(self, data: dict[str, Any]) -> int:
        get_connection = _get_connection()
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]
        sql = f"INSERT INTO purchase_return ({cols}) VALUES ({vals}) RETURNING purchase_return_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    def insert_return_item(self, purchase_return_id: int, data: dict[str, Any]) -> int:
        get_connection = _get_connection()
        data = dict(data)
        data["purchase_return_id"] = purchase_return_id
        keys = list(data.keys())
        cols = ", ".join(keys)
        vals = ", ".join(["%s"] * len(keys))
        values = [data[k] for k in keys]
        sql = f"INSERT INTO purchase_return_item ({cols}) VALUES ({vals}) RETURNING purchase_return_item_id"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    def get_by_id(self, purchase_return_id: int) -> Optional[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_return WHERE purchase_return_id = %s AND is_deleted = FALSE"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_return_id,))
                return cur.fetchone()

    def get_items_by_return(self, purchase_return_id: int) -> List[dict]:
        get_connection = _get_connection()
        factory = _dict_cursor_factory()
        sql = "SELECT * FROM purchase_return_item WHERE purchase_return_id = %s ORDER BY purchase_return_item_id"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=factory) as cur:
                cur.execute(sql, (purchase_return_id,))
                return cur.fetchall()