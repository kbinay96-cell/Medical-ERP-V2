"""
engines/audit_cleanup_engine.py

Automatic retention-based cleanup for the audit/history tables
(audit_log, login_history, failed_login_history, user_audit_log).
Runs once per app startup. Retention period is settings-driven
(security.audit_retention_days, default 90 days; 0 disables
cleanup entirely). This is the ONLY place these tables are ever
deleted from -- no manual/UI delete exists by design, to keep
the audit trail tamper-evident.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from database.db import get_connection

logger = logging.getLogger(__name__)

_TABLES_AND_DATE_COLUMNS = [
    ("audit_log", "createdat"),
    ("login_history", "logintime"),
    ("failed_login_history", "attemptdate"),
    ("user_audit_log", "actionat"),
]


def cleanup_old_audit_data() -> None:
    """Deletes audit/history rows older than the configured retention
    period. Never raises -- a cleanup failure should never block
    app startup."""
    try:
        from engines.settings_engine import get_setting
        retention_days = int(get_setting("security.audit_retention_days", 90))
    except Exception:
        retention_days = 90

    if retention_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for table, date_column in _TABLES_AND_DATE_COLUMNS:
                    cur.execute(f"DELETE FROM {table} WHERE {date_column} < %s", (cutoff,))
            conn.commit()
    except Exception:
        logger.exception("Audit-log cleanup failed; will retry on next startup.")


__all__ = ["cleanup_old_audit_data"]