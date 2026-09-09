"""
models/password_reset_model.py

Data access for the password_reset_requests table (WhatsApp
deep-link + admin-approval forgot-password flow).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from database.db import get_connection

REQUEST_EXPIRY_MINUTES = 15


class PasswordResetModelError(Exception):
    pass


def insert_request(userid: int, username: str, requestcode: str) -> int:
    expires_at = datetime.now() + timedelta(minutes=REQUEST_EXPIRY_MINUTES)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO password_reset_requests
                        (userid, username, requestcode, status, expiresat)
                    VALUES (%s, %s, %s, 'Pending', %s)
                    RETURNING requestid
                    """,
                    (userid, username, requestcode, expires_at),
                )
                request_id = cur.fetchone()["requestid"]
            conn.commit()
        return request_id
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to create reset request: {exc}") from exc


def get_pending_requests() -> list[dict]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM password_reset_requests
                    WHERE status = 'Pending'
                    ORDER BY createdat DESC
                    LIMIT 200
                    """
                )
                return cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to load reset requests: {exc}") from exc


def get_active_pending_for_user(userid: int) -> dict | None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM password_reset_requests
                    WHERE userid = %s AND status = 'Pending' AND expiresat > %s
                    ORDER BY createdat DESC
                    LIMIT 1
                    """,
                    (userid, datetime.now()),
                )
                return cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to check active reset requests for user {userid}: {exc}") from exc


def count_recent_requests(userid: int, minutes: int) -> int:
    try:
        since = datetime.now() - timedelta(minutes=minutes)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM password_reset_requests WHERE userid = %s AND createdat >= %s",
                    (userid, since),
                )
                row = cur.fetchone()
                return row["cnt"] if row else 0
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to count recent reset requests for user {userid}: {exc}") from exc


def get_request_by_id(request_id: int) -> dict | None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM password_reset_requests WHERE requestid = %s", (request_id,))
                return cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to load reset request {request_id}: {exc}") from exc


def mark_approved(request_id: int, approved_by: str, temp_password: str) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE password_reset_requests
                    SET status = 'Approved', approvedby = %s, approvedat = %s, temppassword = %s
                    WHERE requestid = %s
                    """,
                    (approved_by, datetime.now(), temp_password, request_id),
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to approve reset request {request_id}: {exc}") from exc


def mark_rejected(request_id: int, rejected_by: str) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE password_reset_requests
                    SET status = 'Rejected', approvedby = %s, approvedat = %s
                    WHERE requestid = %s
                    """,
                    (rejected_by, datetime.now(), request_id),
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise PasswordResetModelError(f"Failed to reject reset request {request_id}: {exc}") from exc