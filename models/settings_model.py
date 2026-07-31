"""
=========================================================
Medical ERP V2
Settings Model
---------------------------------------------------------
Purpose:
    All database operations for the `settings` and
    `settings_history` tables (see database/schema_auth.sql).

    Business logic (caching, validation, applying settings)
    lives in engines/settings_engine.py - this file is
    PostgreSQL access only, per MVC.
=========================================================
"""

from datetime import datetime

from database.db import get_connection


def get_all_settings(companyid: str | None = None, userid: int | None = None) -> list[dict]:
    """
    Returns every GLOBAL setting row (companyid/userid both NULL).
    Company/user-specific overrides are a future enhancement -
    this function's signature already accepts those parameters
    so callers don't need to change later.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM settings
                WHERE companyid IS NOT DISTINCT FROM %s
                  AND userid IS NOT DISTINCT FROM %s
                ORDER BY setting_group, display_order, setting_key
                """,
                (companyid, userid)
            )
            return cur.fetchall()


def get_setting_by_key(key: str, companyid: str | None = None, userid: int | None = None) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM settings
                WHERE setting_key = %s
                  AND companyid IS NOT DISTINCT FROM %s
                  AND userid IS NOT DISTINCT FROM %s
                """,
                (key, companyid, userid)
            )
            return cur.fetchone()


def get_settings_by_group(setting_group: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM settings
                WHERE setting_group = %s AND companyid IS NULL AND userid IS NULL
                ORDER BY display_order, setting_key
                """,
                (setting_group,)
            )
            return cur.fetchall()


def get_all_groups() -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT setting_group FROM settings
                WHERE companyid IS NULL AND userid IS NULL
                ORDER BY setting_group
                """
            )
            return [row["setting_group"] for row in cur.fetchall()]


def search_settings(search_text: str) -> list[dict]:
    """
    Searches key, description, and group - this backs the
    Settings screen's global search box.
    """
    keyword = f"%{search_text.strip()}%"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM settings
                WHERE companyid IS NULL AND userid IS NULL
                  AND (
                        setting_key ILIKE %s
                        OR description ILIKE %s
                        OR setting_group ILIKE %s
                      )
                ORDER BY setting_group, display_order
                """,
                (keyword, keyword, keyword)
            )
            return cur.fetchall()


def update_setting_value(key: str, value: str, updated_by: str, reason: str = "") -> tuple[bool, str]:
    """
    Updates a global setting's value and writes a
    settings_history row recording the change.
    """
    existing = get_setting_by_key(key)

    if existing is None:
        return False, f"Setting '{key}' not found."

    old_value = existing["setting_value"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE settings
                SET setting_value = %s, updated_at = %s, updated_by = %s
                WHERE setting_key = %s AND companyid IS NULL AND userid IS NULL
                """,
                (value, datetime.now(), updated_by, key)
            )

            cur.execute(
                """
                INSERT INTO settings_history (setting_key, old_value, new_value, changed_by, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (key, old_value, value, updated_by, reason)
            )
        conn.commit()

    return True, "Setting updated successfully."


def reset_setting_to_default(key: str, updated_by: str) -> tuple[bool, str]:
    existing = get_setting_by_key(key)

    if existing is None:
        return False, f"Setting '{key}' not found."

    return update_setting_value(key, existing["default_value"], updated_by, reason="Reset to default")


def create_setting(
    key: str, value: str, setting_group: str, data_type: str,
    default_value: str, description: str, display_order: int, created_by: str
) -> tuple[bool, str]:
    key = key.strip()

    if not key:
        return False, "Setting key is required."

    if get_setting_by_key(key):
        return False, "A setting with this key already exists."

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO settings (
                    setting_key, setting_value, setting_group, data_type,
                    default_value, description, display_order, updated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (key, value, setting_group, data_type, default_value, description, display_order, created_by)
            )
        conn.commit()

    return True, f"Setting '{key}' created."


def get_setting_history(key: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM settings_history WHERE setting_key = %s ORDER BY changed_at DESC",
                (key,)
            )
            return cur.fetchall()


def get_recent_history(limit: int = 10) -> list[dict]:
    """
    Returns the most recent settings_history rows across ALL
    keys, with the owning setting's group joined in - backs the
    Settings screen's "Recently changed" panel with real audit
    data instead of anything fabricated.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.*, s.setting_group
                FROM settings_history h
                LEFT JOIN settings s
                       ON s.setting_key = h.setting_key
                      AND s.companyid IS NULL AND s.userid IS NULL
                ORDER BY h.changed_at DESC
                LIMIT %s
                """,
                (limit,)
            )
            return cur.fetchall()

