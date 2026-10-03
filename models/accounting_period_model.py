"""Data access for accounting periods and period-lock audit fields."""

from __future__ import annotations

from typing import Any, Optional

from models.accounting_connection import accounting_connection


class AccountingPeriodModel:
    def get_period_for_date(self, date_ad) -> Optional[dict[str, Any]]:
        sql = """
            SELECT ap.*, fy.status AS financial_year_status
            FROM accounting_period ap
            JOIN financial_year fy ON fy.financial_year_id = ap.financial_year_id
            WHERE %(date_ad)s BETWEEN ap.start_date_ad AND ap.end_date_ad
            ORDER BY ap.start_date_ad DESC
            LIMIT 1;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"date_ad": date_ad})
            return cur.fetchone()

    def list_periods(self, financial_year_id: Optional[int] = None) -> list[dict[str, Any]]:
        sql = """
            SELECT ap.*, fy.fy_label
            FROM accounting_period ap
            JOIN financial_year fy ON fy.financial_year_id = ap.financial_year_id
            WHERE (%(financial_year_id)s IS NULL OR ap.financial_year_id = %(financial_year_id)s)
            ORDER BY ap.start_date_ad, ap.accounting_period_id;
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {"financial_year_id": financial_year_id})
            return cur.fetchall()

    def insert(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO accounting_period
                (financial_year_id, period_label, start_date_ad, end_date_ad, status)
            VALUES (%(financial_year_id)s, %(period_label)s, %(start_date_ad)s,
                    %(end_date_ad)s, %(status)s)
            RETURNING accounting_period_id;
        """
        values = {**data, "status": data.get("status", "Open")}
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, values)
            return cur.fetchone()["accounting_period_id"]

    def lock_period(self, accounting_period_id: int, locked_by: int, locked_at_ad=None) -> None:
        sql = """
            UPDATE accounting_period
            SET status = 'Locked', locked_by = %(locked_by)s,
                locked_at_ad = COALESCE(%(locked_at_ad)s, NOW()),
                reopened_by = NULL, reopened_at_ad = NULL, reopen_reason = NULL
            WHERE accounting_period_id = %(accounting_period_id)s AND status = 'Open';
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {
                "accounting_period_id": accounting_period_id,
                "locked_by": locked_by,
                "locked_at_ad": locked_at_ad,
            })
            if cur.rowcount != 1:
                raise ValueError("Accounting period was not found or is already locked.")

    def reopen_period(
        self, accounting_period_id: int, reopened_by: int, reopen_reason: str, reopened_at_ad=None
    ) -> None:
        sql = """
            UPDATE accounting_period
            SET status = 'Open', reopened_by = %(reopened_by)s,
                reopened_at_ad = COALESCE(%(reopened_at_ad)s, NOW()), reopen_reason = %(reopen_reason)s
            WHERE accounting_period_id = %(accounting_period_id)s AND status = 'Locked';
        """
        with accounting_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, {
                "accounting_period_id": accounting_period_id,
                "reopened_by": reopened_by,
                "reopened_at_ad": reopened_at_ad,
                "reopen_reason": reopen_reason,
            })
            if cur.rowcount != 1:
                raise ValueError("Accounting period was not found or is not locked.")
