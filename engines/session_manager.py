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
    global _current_session
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sessions SET isactive = FALSE WHERE sessionid = %s", (session_id,))
        conn.commit()
    if _current_session and _current_session.get("sessionid") == session_id:
        _current_session = None
    reset_activity_tracking()
    clear_current_role()

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

def get_current_session() -> dict | None:
    """
    Returns the current in-memory session (or None if no one
    is logged in for this app process).
    """
    return _current_session


# ---------------------------------------------------------
# Settings-driven timeout/lock configuration (live from DB,
# falling back to config.settings constants if unavailable)
# ---------------------------------------------------------

def _get_settings_engine():
    """Lazy import to avoid circular import at module load time."""
    from engines import settings_engine
    return settings_engine


def get_session_timeout_minutes() -> int:
    try:
        se = _get_settings_engine()
        return int(se.get_setting("security.session_timeout_minutes", SESSION_TIMEOUT_MINUTES))
    except Exception:
        return SESSION_TIMEOUT_MINUTES


def is_session_timeout_enabled() -> bool:
    try:
        se = _get_settings_engine()
        return bool(se.get_setting("security.enable_session_timeout", True))
    except Exception:
        return True


def get_auto_lock_minutes() -> int:
    try:
        se = _get_settings_engine()
        return int(se.get_setting("security.auto_lock_minutes", 10))
    except Exception:
        return 10


def is_auto_lock_enabled() -> bool:
    try:
        se = _get_settings_engine()
        return bool(se.get_setting("security.enable_auto_lock", True))
    except Exception:
        return True


# ---------------------------------------------------------
# Idle-activity tracking (in-memory, throttled DB writes)
# ---------------------------------------------------------

_last_activity_time = None   # datetime, updated on every user interaction (in-memory only)
_last_db_touch_time = None   # datetime, updated only when touch_session() actually writes to DB
_DB_TOUCH_THROTTLE_SECONDS = 30


def record_activity() -> None:
    """
    Call this on every detected user interaction (mouse/key event).
    In-memory update happens every time (cheap); the DB touch_session()
    write is throttled to at most once per _DB_TOUCH_THROTTLE_SECONDS
    to avoid hammering the database on every mouse move.
    """
    global _last_activity_time, _last_db_touch_time

    now = datetime.now()
    _last_activity_time = now

    if _current_session is None:
        return

    session_id = _current_session.get("sessionid")
    if session_id is None:
        return

    if _last_db_touch_time is None or (now - _last_db_touch_time).total_seconds() >= _DB_TOUCH_THROTTLE_SECONDS:
        touch_session(session_id)
        _last_db_touch_time = now


def get_last_activity_time():
    """Returns the in-memory last-activity datetime, or None if no activity recorded yet."""
    return _last_activity_time


def reset_activity_tracking() -> None:
    """Call on login, on unlock, and on logout/timeout to reset the idle clock."""
    global _last_activity_time, _last_db_touch_time
    _last_activity_time = datetime.now()
    _last_db_touch_time = None


def minutes_since_last_activity() -> float:
    """Returns minutes elapsed since last recorded activity, or 0 if none recorded yet."""
    if _last_activity_time is None:
        return 0.0
    return (datetime.now() - _last_activity_time).total_seconds() / 60.0


# ---------------------------------------------------------
# Current user's role (in-memory) - needed for backend
# permission enforcement, since the DB `sessions` row and
# the in-memory _current_session dict do NOT store roleid.
# ---------------------------------------------------------

_current_role = {"roleid": None, "is_admin": False}


def set_current_role(roleid: int, is_admin: bool) -> None:
    global _current_role
    _current_role = {"roleid": roleid, "is_admin": bool(is_admin)}


def get_current_roleid():
    return _current_role["roleid"]


def is_current_user_admin() -> bool:
    return _current_role["is_admin"]


def clear_current_role() -> None:
    global _current_role
    _current_role = {"roleid": None, "is_admin": False}
