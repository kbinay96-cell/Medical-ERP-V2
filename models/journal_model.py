"""
models/journal_model.py

Journal Model - Medical ERP V2

Project rule: "No SQL outside the Model." Balance validation
(SUM(debit) = SUM(credit)) and period-lock checking are the Engine's
job (Part 2) -- this Model only persists what it's given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


@dataclass
class JournalSearchFilters:
    source_document_type: Optional[str] = None
    source_document_id: Optional[int] = None
    account_id: Optional[int] = None
    sub_ledger_type: Optional[str] = None
    sub_ledger_id: Optional[int] = None
    status: Optional[str] = None
    date_from_ad: Optional[Any] = None
    date_to_ad: Optional[Any] = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50


JOURNAL_HEADER_COLUMNS = (
    "journal_number", "journal_date_ad", "journal_date_bs", "financial_year_id",
    "accounting_period_id", "source_document_type", "source_document_id",
    "narration", "status", "reversal_of_journal_entry_id",
)

JOURNAL_LINE_COLUMNS = (
    "account_id", "debit_amount", "credit_amount", "sub_ledger_type",
    "sub_ledger_id", "branch_id", "department_id", "cost_center_id",
    "line_narration", "line_order",
)


class JournalModel:
    """Data-access layer for `journal_entry` + `journal_entry_line`."""

    def insert_with_lines(self, header_data: dict[str, Any], line_rows: list[dict[str, Any]]) -> int:
        header_columns = list(JOURNAL_HEADER_COLUMNS) + ["created_by", "created_at_ad", "created_at_bs"]
        header_col_sql = ", ".join(header_columns)
        header_placeholder_sql = ", ".join(f"%({c})s" for c in header_columns)
        header_sql = f"""
            INSERT INTO journal_entry ({header_col_sql})
            VALUES ({header_placeholder_sql})
            RETURNING journal_entry_id;
        """

        line_columns = ["journal_entry_id"] + list(JOURNAL_LINE_COLUMNS)
        line_col_sql = ", ".join(line_columns)
        line_placeholder_sql = ", ".join(f"%({c})s" for c in line_columns)
        line_sql = f"INSERT INTO journal_entry_line ({line_col_sql}) VALUES ({line_placeholder_sql});"

        conn = _get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                    cur.execute(header_sql, header_data)
                    journal_entry_id = cur.fetchone()["journal_entry_id"]
                    for row in line_rows:
                        row = dict(row)
                        row["journal_entry_id"] = journal_entry_id
                        cur.execute(line_sql, row)
            return journal_entry_id
        except Exception:
            logger.exception("insert_with_lines failed for journal_entry")
            raise
        finally:
            conn.close()

    def get_by_id(self, journal_entry_id: int) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM journal_entry WHERE journal_entry_id = %(id)s AND is_deleted = FALSE;"
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": journal_entry_id})
                return cur.fetchone()
        finally:
            conn.close()

    def get_lines_by_journal_id(self, journal_entry_id: int) -> list[dict[str, Any]]:
        sql = """
            SELECT jel.*, coa.account_code, coa.account_name
            FROM journal_entry_line jel
            JOIN chart_of_accounts coa ON coa.account_id = jel.account_id
            WHERE jel.journal_entry_id = %(id)s
            ORDER BY jel.line_order;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"id": journal_entry_id})
                return cur.fetchall()
        finally:
            conn.close()

    def get_journals_for_document(self, source_document_type: str, source_document_id: int) -> list[dict[str, Any]]:
        """The 'Journal -> Document' reverse lookup, and also the
        'Document -> Journal' forward lookup used by every source
        Screen's "View Journal" button."""
        sql = """
            SELECT * FROM journal_entry
            WHERE source_document_type = %(type)s AND source_document_id = %(id)s
              AND is_deleted = FALSE
            ORDER BY journal_entry_id;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, {"type": source_document_type, "id": source_document_id})
                return cur.fetchall()
        finally:
            conn.close()

    def get_account_ledger(self, account_id: int, sub_ledger_type: Optional[str] = None,
                            sub_ledger_id: Optional[int] = None,
                            date_from_ad: Optional[Any] = None, date_to_ad: Optional[Any] = None) -> list[dict[str, Any]]:
        """Powers the General Ledger / Customer Ledger / Supplier Ledger
        reports (Reports Module, next blueprint) -- returns every POSTED
        line against this account (optionally filtered to one
        sub-ledger), oldest first, for running-balance calculation."""
        conditions = ["jel.account_id = %(account_id)s", "je.status = 'Posted'", "je.is_deleted = FALSE"]
        params: dict[str, Any] = {"account_id": account_id}
        if sub_ledger_type:
            conditions.append("jel.sub_ledger_type = %(sub_ledger_type)s")
            params["sub_ledger_type"] = sub_ledger_type
        if sub_ledger_id:
            conditions.append("jel.sub_ledger_id = %(sub_ledger_id)s")
            params["sub_ledger_id"] = sub_ledger_id
        if date_from_ad:
            conditions.append("je.journal_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = date_from_ad
        if date_to_ad:
            conditions.append("je.journal_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = date_to_ad

        sql = f"""
            SELECT je.journal_number, je.journal_date_ad, je.narration,
                   jel.debit_amount, jel.credit_amount, jel.line_narration
            FROM journal_entry_line jel
            JOIN journal_entry je ON je.journal_entry_id = jel.journal_entry_id
            WHERE {' AND '.join(conditions)}
            ORDER BY je.journal_date_ad ASC, je.journal_entry_id ASC;
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def search(self, filters: JournalSearchFilters) -> list[dict[str, Any]]:
        conditions = ["je.is_deleted = FALSE" if not filters.include_deleted else "1=1"]
        params: dict[str, Any] = {}
        if filters.source_document_type:
            conditions.append("je.source_document_type = %(source_document_type)s")
            params["source_document_type"] = filters.source_document_type
        if filters.source_document_id:
            conditions.append("je.source_document_id = %(source_document_id)s")
            params["source_document_id"] = filters.source_document_id
        if filters.status:
            conditions.append("je.status = %(status)s")
            params["status"] = filters.status
        if filters.date_from_ad:
            conditions.append("je.journal_date_ad >= %(date_from_ad)s")
            params["date_from_ad"] = filters.date_from_ad
        if filters.date_to_ad:
            conditions.append("je.journal_date_ad <= %(date_to_ad)s")
            params["date_to_ad"] = filters.date_to_ad

        where_sql = " AND ".join(conditions)
        offset = (filters.page - 1) * filters.page_size
        sql = f"""
            SELECT je.* FROM journal_entry je
            WHERE {where_sql}
            ORDER BY je.journal_entry_id DESC
            LIMIT %(limit)s OFFSET %(offset)s;
        """
        params["limit"] = filters.page_size
        params["offset"] = offset
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()

    def update_status(self, journal_entry_id: int, status: str, cancellation_reason: Optional[str],
                       updated_by: int, updated_at_ad: Any, updated_at_bs: str) -> None:
        sql = """
            UPDATE journal_entry
            SET status = %(status)s, cancellation_reason = %(cancellation_reason)s,
                updated_by = %(updated_by)s, updated_at_ad = %(updated_at_ad)s, updated_at_bs = %(updated_at_bs)s
            WHERE journal_entry_id = %(journal_entry_id)s;
        """
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, {
                        "journal_entry_id": journal_entry_id, "status": status,
                        "cancellation_reason": cancellation_reason, "updated_by": updated_by,
                        "updated_at_ad": updated_at_ad, "updated_at_bs": updated_at_bs,
                    })
        finally:
            conn.close()