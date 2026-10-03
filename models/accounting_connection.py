"""Connection lifecycle helper shared by the Accounts data models."""

from __future__ import annotations

from contextlib import contextmanager

from database.db import get_connection


@contextmanager
def accounting_connection():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()

