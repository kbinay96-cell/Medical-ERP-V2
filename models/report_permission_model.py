"""models/report_permission_model.py"""
from __future__ import annotations
from typing import Any


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ReportPermissionModel:
    def get_permissions_for_role(self, role_name: str) -> dict[str, bool]:
        sql = "SELECT permission_name, is_granted FROM report_permission WHERE role_name = %(role_name)s;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"role_name": role_name})
                rows = cur.fetchall()
                return {row["permission_name"]: row["is_granted"] for row in rows}
        finally:
            conn.close()