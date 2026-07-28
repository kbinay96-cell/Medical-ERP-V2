"""
=========================================================
Medical ERP V2
Audit Logger Engine
---------------------------------------------------------
Responsibilities:
    - Login / Logout history
    - Failed attempts
    - Security events

Audit log rows are INSERT-only. The application never
provides an UPDATE or DELETE for audit_log.
=========================================================
"""

from datetime import datetime
import socket

from database.db import get_connection


def write_audit_log(action: str, userid: int | None = None, username: str | None = None, details: str = "") -> None:
    """
    Writes one row to audit_log. `action` should be one of the
    AUDIT_* constants in config.settings (Login, Logout,
    PasswordChanged, PasswordReset, UserLocked, UserUnlocked,
    RoleChanged, PermissionChanged), but any short label works.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (userid, username, action, details, createdat)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (userid, username, action, details, datetime.now())
            )
        conn.commit()


def write_login_history(userid: int, username: str, companyid: str, financialyear: str, session_id: str) -> None:
    """
    Writes one row to login_history for a successful login.
    """
    machine_name = socket.gethostname()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO login_history (
                    userid, username, companyid, financialyear,
                    logintime, machinename, appversion, sessionid
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    userid, username, companyid, financialyear,
                    datetime.now(), machine_name, "2.0.0", session_id,
                )
            )
        conn.commit()


def write_logout_time(session_id: str) -> None:
    """
    Marks the logout time on the matching login_history row.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE login_history SET logouttime = %s WHERE sessionid = %s",
                (datetime.now(), session_id)
            )
        conn.commit()


def write_failed_login(username: str, reason: str) -> None:
    """
    Writes one row to failed_login_history.
    """
    machine_name = socket.gethostname()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO failed_login_history (username, attemptdate, machinename, failurereason)
                VALUES (%s, %s, %s, %s)
                """,
                (username, datetime.now(), machine_name, reason)
            )
        conn.commit()
