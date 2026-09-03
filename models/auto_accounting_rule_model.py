"""models/auto_accounting_rule_model.py"""
from __future__ import annotations
from typing import Any


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class AutoAccountingRuleModel:
    def get_active_rules_for_type(self, transaction_type: str) -> list[dict[str, Any]]:
        sql = """
            SELECT aar.*, coa.account_code, coa.account_name
            FROM auto_accounting_rule aar
            JOIN chart_of_accounts coa ON coa.account_id = aar.account_id
            WHERE aar.transaction_type = %(transaction_type)s AND aar.is_active = TRUE
            ORDER BY aar.display_order;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"transaction_type": transaction_type})
                return cur.fetchall()
        finally:
            conn.close()