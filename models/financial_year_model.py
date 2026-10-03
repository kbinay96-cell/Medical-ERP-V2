"""Data access for accounting financial years."""

from __future__ import annotations

from typing import Any, Optional

from models.accounting_connection import accounting_connection


class FinancialYearModel:
    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO financial_year
                (fy_label, start_date_ad, end_date_ad, start_date_bs, end_date_bs)
            VALUES (%(fy_label)s, %(start_date_ad)s, %(end_date_ad)s,
                    %(start_date_bs)s, %(end_date_bs)s)
            RETURNING financial_year_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, data)
            return cur.fetchone()["financial_year_id"]

    def get_by_id(self, financial_year_id: int) -> Optional[dict[str, Any]]:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM financial_year WHERE financial_year_id = %s;",
                (financial_year_id,),
            )
            return cur.fetchone()

    def list_all(self) -> list[dict[str, Any]]:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM financial_year ORDER BY start_date_ad DESC;")
            return cur.fetchall()

    def get_current_open_year(self, date_ad=None) -> Optional[dict[str, Any]]:
        if date_ad is None:
            sql = "SELECT * FROM financial_year WHERE status = 'Open' ORDER BY start_date_ad DESC LIMIT 1;"
            params = None
        else:
            sql = """
                SELECT * FROM financial_year
                WHERE status = 'Open' AND %(date_ad)s BETWEEN start_date_ad AND end_date_ad
                ORDER BY start_date_ad DESC LIMIT 1;
            """
            params = {"date_ad": date_ad}
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def close_year(
        self, financial_year_id: int, closing_journal_entry_id: int, closed_by: int
    ) -> None:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE financial_year
                SET status = 'Closed', closing_journal_entry_id = %(journal_id)s
                WHERE financial_year_id = %(financial_year_id)s AND status = 'Open';
                """,
                {"journal_id": closing_journal_entry_id, "financial_year_id": financial_year_id},
            )
            if cur.rowcount != 1:
                raise ValueError("Financial year was not found or is already closed.")
            cur.execute(
                """
                UPDATE accounting_period
                SET status = 'Locked', locked_by = %(closed_by)s, locked_at_ad = NOW()
                WHERE financial_year_id = %(financial_year_id)s AND status = 'Open';
                """,
                {"closed_by": closed_by, "financial_year_id": financial_year_id},
            )

    def get_net_profit_for_year(self, financial_year_id: int) -> float:
        sql = """
            SELECT COALESCE(SUM(
                CASE
                    WHEN coa.normal_balance = 'Credit' THEN jel.credit_amount - jel.debit_amount
                    ELSE jel.debit_amount - jel.credit_amount
                END
            ), 0) AS net_profit
            FROM journal_entry_line jel
            JOIN journal_entry je ON je.journal_entry_id = jel.journal_entry_id
            JOIN chart_of_accounts coa ON coa.account_id = jel.account_id
            WHERE je.financial_year_id = %(financial_year_id)s
              AND je.status = 'Posted' AND je.is_deleted = FALSE
              AND coa.account_group IN ('Revenue', 'Cost of Goods', 'Operating Expenses');
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"financial_year_id": financial_year_id})
            return float(cur.fetchone()["net_profit"] or 0)
