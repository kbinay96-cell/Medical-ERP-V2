"""
models/report_query_executor.py

Report Query Executor - Medical ERP V2

A dedicated layer, separate from any single table's Model, whose ONLY
job is running a report's stored `sql_template` (from either
report_definition or management_dashboard_widget) with filter VALUES
bound as query parameters. Kept out of ReportDefinitionModel and
ManagementDashboardModel on purpose: those two Models' job is CRUD on
their OWN table, exactly like every other Masters-style Model in this
project (Supplier, Customer, Item, ...) -- executing a dynamically-
sourced, arbitrary SELECT statement is a fundamentally different
responsibility and both report_definition AND management_dashboard_widget
need the exact same execution mechanism, so it is written once here
instead of duplicated in two Models.

This remains the ONE place in the whole project that runs a
dynamically-sourced SQL string -- justified because that string is
trusted developer-authored config data (same trust level as
auto_accounting_rule's Dr/Cr mapping), never end-user input. Filter
VALUES are always bound as psycopg2 parameters, exactly like every
other parameterized query in this codebase -- never string-concatenated.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_connection():
    from database.db import get_connection
    return get_connection()


def _dict_cursor_factory():
    import psycopg2.extras
    return psycopg2.extras.RealDictCursor


class ReportQueryExecutor:
    """Runs a trusted SQL template with parameterized filter values.
    Stateless -- a single instance is shared by both
    ReportEngine (Part 2) and any Management Dashboard widget loader."""

    def run(self, sql_template: str, filter_params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Executes `sql_template` with `filter_params` bound as named
        query parameters -- standard psycopg2 parameter binding.
        Callers (the Engine, Part 2) are responsible for ensuring every
        placeholder the template expects has a corresponding (possibly
        None) entry in filter_params before calling this -- this method
        itself does no filter resolution, just execution.
        """
        conn = _get_connection()
        try:
            with conn.cursor(cursor_factory=_dict_cursor_factory()) as cur:
                cur.execute(sql_template, filter_params)
                return cur.fetchall()
        except Exception:
            logger.exception("ReportQueryExecutor.run failed for a report/widget template")
            raise
        finally:
            conn.close()