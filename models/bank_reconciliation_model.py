"""Data access for bank reconciliation entries."""

from __future__ import annotations

from typing import Any, Optional

from models.accounting_connection import accounting_connection


class BankReconciliationModel:
    def insert(self, journal_entry_line_id: int, account_id: int) -> int:
        sql = """
            INSERT INTO bank_reconciliation (journal_entry_line_id, account_id)
            VALUES (%(journal_entry_line_id)s, %(account_id)s)
            ON CONFLICT (journal_entry_line_id) DO NOTHING
            RETURNING bank_reconciliation_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {
                "journal_entry_line_id": journal_entry_line_id,
                "account_id": account_id,
            })
            row = cur.fetchone()
            if row:
                return row["bank_reconciliation_id"]
            cur.execute(
                "SELECT bank_reconciliation_id FROM bank_reconciliation WHERE journal_entry_line_id = %s;",
                (journal_entry_line_id,),
            )
            return cur.fetchone()["bank_reconciliation_id"]

    def get_unreconciled(self, account_id: Optional[int] = None) -> list[dict[str, Any]]:
        sql = """
            SELECT br.bank_reconciliation_id, br.account_id, coa.account_code, coa.account_name,
                   br.journal_entry_line_id, br.bank_statement_reference,
                   br.difference_amount, je.journal_number, je.journal_date_ad, je.narration,
                   jel.debit_amount, jel.credit_amount
            FROM bank_reconciliation br
            JOIN chart_of_accounts coa ON coa.account_id = br.account_id
            JOIN journal_entry_line jel ON jel.journal_entry_line_id = br.journal_entry_line_id
            JOIN journal_entry je ON je.journal_entry_id = jel.journal_entry_id
            WHERE br.reconciliation_status = 'Unreconciled'
              AND (%(account_id)s IS NULL OR br.account_id = %(account_id)s)
              AND je.status = 'Posted' AND je.is_deleted = FALSE
            ORDER BY je.journal_date_ad, je.journal_entry_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"account_id": account_id})
            return cur.fetchall()

    def mark_reconciled(
        self,
        bank_reconciliation_id: int,
        bank_statement_reference: str,
        reconciled_date_ad,
        reconciled_by: int,
        difference_amount: float,
    ) -> None:
        sql = """
            UPDATE bank_reconciliation
            SET bank_statement_reference = %(bank_statement_reference)s,
                reconciliation_status = 'Reconciled',
                reconciled_date_ad = %(reconciled_date_ad)s,
                reconciled_by = %(reconciled_by)s,
                difference_amount = %(difference_amount)s
            WHERE bank_reconciliation_id = %(bank_reconciliation_id)s
              AND reconciliation_status = 'Unreconciled';
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {
                "bank_reconciliation_id": bank_reconciliation_id,
                "bank_statement_reference": bank_statement_reference,
                "reconciled_date_ad": reconciled_date_ad,
                "reconciled_by": reconciled_by,
                "difference_amount": difference_amount,
            })
            if cur.rowcount != 1:
                raise ValueError("Unreconciled bank entry was not found.")
