"""
=========================================================
Medical ERP V2
Session Manager Engine
---------------------------------------------------------
Responsibilities:
    - Create session
    - Destroy session
    - Session timeout check
    - Session validation
    - Current user information (in-memory, for this run
      of the application)

No SQL logic beyond simple session-row read/write here.
No UI code here.
=========================================================
"""

import secrets
import socket
from datetime import datetime, timedelta

from database.db import get_connection
from config.settings import SESSION_TIMEOUT_MINUTES, ALLOW_MULTIPLE_LOGIN, APP_VERSION

# Holds the current logged-in session for THIS running app
# instance (a desktop app has exactly one active user at a
# time per process).
_current_session = None


def create_session(userid: int, companyid: str, financialyear: str) -> dict:
    """
    Creates a new session: writes a row to `sessions`, and
    (if multiple logins are disallowed) deactivates any other
    active sessions for this user.

    Returns the session dict (also kept as the "current" one).
    """
    global _current_session

    session_id = secrets.token_hex(24)
    machine_name = socket.gethostname()

    with get_connection() as conn:
        with conn.cursor() as cur:

            if not ALLOW_MULTIPLE_LOGIN:
                cur.execute(
                    "UPDATE sessions SET isactive = FALSE WHERE userid = %s AND isactive = TRUE",
                    (userid,)
                )

            cur.execute(
                """
                INSERT INTO sessions (
                    sessionid, userid, companyid, financialyear,
                    logintime, lastactivity, machinename, appversion, isactive
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """,
                (
                    session_id, userid, companyid, financialyear,
                    datetime.now(), datetime.now(), machine_name, APP_VERSION,
                )
            )
        conn.commit()

    _current_session = {
        "sessionid": session_id,
        "userid": userid,
        "companyid": companyid,
        "financialyear": financialyear,
        "machinename": machine_name,
    }

    return _current_session


def destroy_session(session_id: str) -> None:
    """
    Ends a session (Logout).
    """
    global _current_session

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET isactive = FALSE WHERE sessionid = %s",
                (session_id,)
            )
        conn.commit()

    if _current_session and _current_session.get("sessionid") == session_id:
        _current_session = None


def touch_session(session_id: str) -> None:
    """
    Updates last-activity time for a session. Call this on
    any user interaction to keep the session alive.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET lastactivity = %s WHERE sessionid = %s",
                (datetime.now(), session_id)
            )
        conn.commit()


def is_session_timed_out(last_activity: datetime, timeout_minutes: int = SESSION_TIMEOUT_MINUTES) -> bool:
    """
    Pure check: has this session been inactive too long?
    """
    if last_activity is None:
        return True

    return datetime.now() > last_activity + timedelta(minutes=timeout_minutes)


def get_current_session() -> dict | None:
    """
    Returns the current in-memory session (or None if no one
    is logged in for this app process).
    """
    return _current_session
