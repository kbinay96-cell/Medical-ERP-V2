"""
models/audit_log_model.py

Read-only queries for the four audit/history tables (audit_log,
login_history, failed_login_history, user_audit_log). These
tables are insert-only from elsewhere in the app -- this module
never writes to them.
"""

from __future__ import annotations

from database.db import get_connection

MAX_ROWS = 500


def get_audit_log(username: str | None = None, start_date=None, end_date=None) -> list[dict]:
    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []
    if username:
        query += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if start_date:
        query += " AND createdat >= %s"
        params.append(start_date)
    if end_date:
        query += " AND createdat <= %s"
        params.append(end_date)
    query += " ORDER BY createdat DESC LIMIT %s"
    params.append(MAX_ROWS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_login_history(username: str | None = None, start_date=None, end_date=None) -> list[dict]:
    query = "SELECT * FROM login_history WHERE 1=1"
    params: list = []
    if username:
        query += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if start_date:
        query += " AND logintime >= %s"
        params.append(start_date)
    if end_date:
        query += " AND logintime <= %s"
        params.append(end_date)
    query += " ORDER BY logintime DESC LIMIT %s"
    params.append(MAX_ROWS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_failed_login_history(username: str | None = None, start_date=None, end_date=None) -> list[dict]:
    query = "SELECT * FROM failed_login_history WHERE 1=1"
    params: list = []
    if username:
        query += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if start_date:
        query += " AND attemptdate >= %s"
        params.append(start_date)
    if end_date:
        query += " AND attemptdate <= %s"
        params.append(end_date)
    query += " ORDER BY attemptdate DESC LIMIT %s"
    params.append(MAX_ROWS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_user_audit_log(username: str | None = None, start_date=None, end_date=None) -> list[dict]:
    query = "SELECT * FROM user_audit_log WHERE 1=1"
    params: list = []
    if username:
        query += " AND performedby ILIKE %s"
        params.append(f"%{username}%")
    if start_date:
        query += " AND actionat >= %s"
        params.append(start_date)
    if end_date:
        query += " AND actionat <= %s"
        params.append(end_date)
    query += " ORDER BY actionat DESC LIMIT %s"
    params.append(MAX_ROWS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()