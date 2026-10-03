"""Data access for financial-year opening-balance input rows."""

from __future__ import annotations

from typing import Any

from models.accounting_connection import accounting_connection


class OpeningBalanceModel:
    def insert_batch(self, rows: list[dict[str, Any]]) -> list[int]:
        if not rows:
            return []
        sql = """
            INSERT INTO opening_balance
                (financial_year_id, account_id, sub_ledger_type, sub_ledger_id,
                 debit_amount, credit_amount, posted_journal_entry_id,
                 created_by, created_at_bs)
            VALUES
                (%(financial_year_id)s, %(account_id)s, %(sub_ledger_type)s, %(sub_ledger_id)s,
                 %(debit_amount)s, %(credit_amount)s, %(posted_journal_entry_id)s,
                 %(created_by)s, %(created_at_bs)s)
            RETURNING opening_balance_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            ids = []
            for row in rows:
                cur.execute(sql, row)
                ids.append(cur.fetchone()["opening_balance_id"])
            return ids

    def get_by_financial_year(self, financial_year_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT ob.*, coa.account_code, coa.account_name
            FROM opening_balance ob
            JOIN chart_of_accounts coa ON coa.account_id = ob.account_id
            WHERE ob.financial_year_id = %(financial_year_id)s
            ORDER BY coa.account_code, ob.sub_ledger_type, ob.sub_ledger_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"financial_year_id": financial_year_id})
            return cur.fetchall()

    def mark_posted(self, opening_balance_id: int, posted_journal_entry_id: int) -> None:
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE opening_balance
                SET posted_journal_entry_id = %(posted_journal_entry_id)s
                WHERE opening_balance_id = %(opening_balance_id)s
                  AND posted_journal_entry_id IS NULL;
                """,
                {
                    "opening_balance_id": opening_balance_id,
                    "posted_journal_entry_id": posted_journal_entry_id,
                },
            )
            if cur.rowcount == 0:
                raise ValueError("No unposted opening balances were found for the financial year.")
