"""
models/report_definition_model.py

Report Definition Model - Medical ERP V2

Project rule: "No SQL outside the Model." CRUD on `report_definition`
only, same shape/responsibility as every Masters-style Model in this
project (Supplier, Customer, Item, ...). Running a report's stored
`sql_template` is a genuinely different responsibility and lives in its
own dedicated file -- see models/report_query_executor.py (section 2.2).
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


REPORT_DEFINITION_COLUMNS = (
    "report_code", "report_name", "report_category_id", "sql_template",
    "applicable_filters", "columns_definition", "drill_down_report_code",
    "drill_down_source_type", "required_permission", "is_financial_statement",
    "is_active", "remarks",
)


class ReportDefinitionModel:
    """Data-access layer for `report_definition` + query execution."""

    # ------------------------------------------------------------------ #
    # DEFINITION CRUD
    # ------------------------------------------------------------------ #
    def insert(self, data: dict[str, Any]) -> int:
        col_sql = ", ".join(REPORT_DEFINITION_COLUMNS)
        placeholder_sql = ", ".join(f"%({c})s" for c in REPORT_DEFINITION_COLUMNS)
        sql = f"INSERT INTO report_definition ({col_sql}) VALUES ({placeholder_sql}) RETURNING report_definition_id;"
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(sql, data)
                    return cur.fetchone()["report_definition_id"]
        finally:
            conn.close()

    def get_by_code(self, report_code: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM report_definition WHERE report_code = %(code)s AND is_active = TRUE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"code": report_code})
                return cur.fetchone()
        finally:
            conn.close()

    def list_by_category(self, report_category_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM report_definition
            WHERE report_category_id = %(category_id)s AND is_active = TRUE
            ORDER BY report_name;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"category_id": report_category_id})
                return cur.fetchall()
        finally:
            conn.close()

    def search_by_name(self, search_text: str) -> list[dict[str, Any]]:
        """Powers the Master Search bar's 'report name' matching."""
        sql = """
            SELECT rd.*, rc.category_name FROM report_definition rd
            JOIN report_category rc ON rc.report_category_id = rd.report_category_id
            WHERE rd.is_active = TRUE AND rd.report_name ILIKE %(search_text)s
            ORDER BY rd.report_name;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"search_text": f"%{search_text}%"})
                return cur.fetchall()
        finally:
            conn.close()

    def update(self, report_definition_id: int, changed_fields: dict[str, Any]) -> None:
        if not changed_fields:
            return
        set_clause = ", ".join(f"{col} = %({col})s" for col in changed_fields)
        sql = f"UPDATE report_definition SET {set_clause} WHERE report_definition_id = %(id)s;"
        params = dict(changed_fields)
        params["id"] = report_definition_id
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            conn.close()