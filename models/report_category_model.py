"""models/report_category_model.py"""
from __future__ import annotations
from typing import Any


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ReportCategoryModel:
    def list_active(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM report_category WHERE is_active = TRUE ORDER BY display_order;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()