"""
models/stock_transaction_model.py

Stock Transaction Model - Medical ERP V2

Project rule: "No SQL outside the Model." Every statement touching
`stock_transaction` lives here and nowhere else. This table is APPEND-ONLY
(mirrors models design intent of audit_log) -- this class deliberately has
NO update() and NO delete() method. A correction is made by inserting a
new reversing row (e.g. transaction_type='Adjustment' with quantity_out
set), never by editing history.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class StockTransactionModel:
    """Data-access layer for `stock_transaction`. Insert + read only -- no update/delete."""

    def insert(self, data: dict[str, Any]) -> int:
        """
        `data` keys: item_id, item_batch_id, transaction_type, quantity_in,
        quantity_out, reference_table, reference_id, remarks, created_by,
        created_at_ad, created_at_bs. Returns the new stock_transaction_id.
        """
        sql = """
            INSERT INTO stock_transaction (
                item_id, item_batch_id, transaction_type, quantity_in, quantity_out,
                reference_table, reference_id, remarks,
                created_by, created_at_ad, created_at_bs
            ) VALUES (
                %(item_id)s, %(item_batch_id)s, %(transaction_type)s, %(quantity_in)s, %(quantity_out)s,
                %(reference_table)s, %(reference_id)s, %(remarks)s,
                %(created_by)s, %(created_at_ad)s, %(created_at_bs)s
            )
            RETURNING stock_transaction_id;
        """
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
                new_id = cur.fetchone()["stock_transaction_id"]
                conn.commit()
                logger.info(
                    "Stock transaction inserted: id=%s item_id=%s type=%s in=%s out=%s",
                    new_id, data.get("item_id"), data.get("transaction_type"),
                    data.get("quantity_in"), data.get("quantity_out"),
                )
                return new_id

    def get_by_item(self, item_id: int) -> list[dict]:
        sql = """
            SELECT * FROM stock_transaction
            WHERE item_id = %(item_id)s
            ORDER BY created_at_ad ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_id": item_id})
                return [dict(r) for r in cur.fetchall()]

    def get_by_batch(self, item_batch_id: int) -> list[dict]:
        sql = """
            SELECT * FROM stock_transaction
            WHERE item_batch_id = %(item_batch_id)s
            ORDER BY created_at_ad ASC;
        """
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"item_batch_id": item_batch_id})
                return [dict(r) for r in cur.fetchall()]


__all__ = ["StockTransactionModel"]