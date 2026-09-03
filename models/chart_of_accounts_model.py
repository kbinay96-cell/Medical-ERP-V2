"""
models/chart_of_accounts_model.py

Chart of Accounts Model - Medical ERP V2
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


COA_COLUMNS = (
    "account_code", "account_name", "account_group", "parent_account_id",
    "is_control_account", "normal_balance", "is_active", "remarks",
)


class ChartOfAccountsModel:
    """Data-access layer for `chart_of_accounts`."""

    def insert(self, data: dict[str, Any]) -> int:
        columns = list(COA_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        col_sql = ", ".join(columns)
        placeholder_sql = ", ".join(f"%({c})s" for c in columns)
        sql = f"INSERT INTO chart_of_accounts ({col_sql}) VALUES ({placeholder_sql}) RETURNING account_id;"
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(sql, data)
                    return cur.fetchone()["account_id"]
        finally:
            conn.close()

    def get_by_id(self, account_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM chart_of_accounts WHERE account_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": account_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_by_code(self, account_code: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM chart_of_accounts WHERE account_code = %(code)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"code": account_code})
                return cur.fetchone()
        finally:
            conn.close()

    def get_hierarchy(self) -> list[dict[str, Any]]:
        """Returns every active account ordered so a Screen can build the
        Group -> Parent -> Ledger tree by walking parent_account_id."""
        sql = """
            SELECT * FROM chart_of_accounts
            WHERE is_deleted = FALSE AND is_active = TRUE
            ORDER BY account_code;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql)
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, search_text: Optional[str] = None) -> list[dict[str, Any]]:
        conditions = ["is_deleted = FALSE"]
        params: dict[str, Any] = {}
        if search_text:
            conditions.append("(account_code ILIKE %(search_text)s OR account_name ILIKE %(search_text)s)")
            params["search_text"] = f"%{search_text}%"
        sql = f"SELECT * FROM chart_of_accounts WHERE {' AND '.join(conditions)} ORDER BY account_code;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def update(self, account_id: int, changed_fields: dict[str, Any], updated_by: int,
               updated_at_ad: Any, updated_at_bs: str) -> None:
        if not changed_fields:
            return
        set_clause = ", ".join(f"{col} = %({col})s" for col in changed_fields)
        sql = f"""
            UPDATE chart_of_accounts
            SET {set_clause}, updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE account_id = %(account_id)s;
        """
        params = dict(changed_fields)
        params.update({"account_id": account_id, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs})
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            conn.close()