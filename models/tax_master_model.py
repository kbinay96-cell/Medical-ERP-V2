"""Data access for configurable accounting tax mappings."""

from __future__ import annotations

from typing import Any, Optional

from models.accounting_connection import accounting_connection


class TaxMasterModel:
    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO tax_master (tax_name, tax_rate_percent, tax_direction, account_id, is_active, remarks)
            VALUES (%(tax_name)s, %(tax_rate_percent)s, %(tax_direction)s, %(account_id)s,
                    %(is_active)s, %(remarks)s)
            RETURNING tax_master_id;
        """
        values = {**data, "is_active": data.get("is_active", True)}
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, values)
            return cur.fetchone()["tax_master_id"]

    def get_by_id(self, tax_master_id: int) -> Optional[dict[str, Any]]:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM tax_master WHERE tax_master_id = %s;", (tax_master_id,))
            return cur.fetchone()

    def list_active(self, direction: Optional[str] = None) -> list[dict[str, Any]]:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT tm.*, coa.account_code, coa.account_name
                FROM tax_master tm
                JOIN chart_of_accounts coa ON coa.account_id = tm.account_id
                WHERE tm.is_active = TRUE
                  AND (%(direction)s IS NULL OR tm.tax_direction = %(direction)s)
                ORDER BY tm.tax_name;
                """,
                {"direction": direction},
            )
            return cur.fetchall()

    def update(self, tax_master_id: int, data: dict[str, Any]) -> None:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tax_master SET tax_name = %(tax_name)s,
                    tax_rate_percent = %(tax_rate_percent)s,
                    tax_direction = %(tax_direction)s, account_id = %(account_id)s,
                    is_active = %(is_active)s, remarks = %(remarks)s
                WHERE tax_master_id = %(tax_master_id)s;
                """,
                {**data, "tax_master_id": tax_master_id},
            )

    def deactivate(self, tax_master_id: int) -> None:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE tax_master SET is_active = FALSE WHERE tax_master_id = %s;", (tax_master_id,))
