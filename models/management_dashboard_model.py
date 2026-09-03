"""
models/management_dashboard_model.py

CRUD/listing only, same reasoning as ReportDefinitionModel post-refactor
-- widget QUERY EXECUTION now goes through the shared
models/report_query_executor.py (section 2.2), not a method here.
"""

from __future__ import annotations
from typing import Any


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ManagementDashboardModel:
    def list_active_widgets(self) -> list[dict[str, Any]]:
        sql = "SELECT * FROM management_dashboard_widget WHERE is_active = TRUE ORDER BY display_order;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()