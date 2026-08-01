"""
=========================================================
Medical ERP V2
User Model
---------------------------------------------------------
Purpose:
    All database operations for the `users` table.
    Business rules around login attempts / locking live
    here (Model layer), not in the Screen.

    Two sections:
    1. LOGIN / AUTHENTICATION SUPPORT (original, unchanged) -
       consumed by engines/authentication_engine.py. Do not
       rename or remove any function here; the Login flow
       depends on these exact names.
    2. USER MASTER CRUD (added) - consumed by
       engines/user_engine.py. Written as module-level
       functions to match the established convention already
       used by models/company_model.py, NOT a class - keeping
       every master module's Model layer consistent.

    Both sections operate on the SAME real `users` table
    (see database/schema_auth.sql + database/0003_user_master_alignment.sql).
    There is only ever one `users` table in this project.
=========================================================
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database.db import get_connection
from config.settings import (
    MAX_FAILED_LOGIN_ATTEMPTS, ACCOUNT_AUTO_UNLOCK_MINUTES,
    STATUS_LOCKED, STATUS_ACTIVE, STATUS_DELETED,
)
from engines.password_manager import hash_password


class UserModelError(Exception):
    """Raised when a database operation on `users` (User Master side) fails."""


# =========================================================
# 1. LOGIN / AUTHENTICATION SUPPORT (UNCHANGED)
# =========================================================

def get_user_by_username(username: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            return cur.fetchone()


def create_user(username: str, plain_password: str, fullname: str, roleid: int, companyid: str, created_by: str) -> tuple[bool, str]:
    username = username.strip()

    if not username:
        return False, "Username is required."

    if get_user_by_username(username):
        return False, "Username already exists."

    password_hash, password_salt = hash_password(plain_password)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    username, passwordhash, passwordsalt, fullname,
                    roleid, companyid, status, passwordchangedat,
                    createddate, createdby
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING userid
                """,
                (
                    username, password_hash, password_salt, fullname,
                    roleid, companyid, STATUS_ACTIVE, datetime.now(),
                    datetime.now(), created_by,
                )
            )
            new_id = cur.fetchone()["userid"]
        conn.commit()

    return True, f"User created (ID: {new_id})."


def register_failed_attempt(username: str) -> None:
    """
    Increments failed-attempt counter. If it reaches the
    configured maximum, locks the account for the configured
    auto-unlock duration.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT failedattempts FROM users WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()

            if row is None:
                return

            new_count = row["failedattempts"] + 1

            if new_count >= MAX_FAILED_LOGIN_ATTEMPTS:
                locked_until = datetime.now() + timedelta(minutes=ACCOUNT_AUTO_UNLOCK_MINUTES)
                cur.execute(
                    "UPDATE users SET failedattempts = %s, status = %s, lockeduntil = %s WHERE username = %s",
                    (new_count, STATUS_LOCKED, locked_until, username)
                )
            else:
                cur.execute(
                    "UPDATE users SET failedattempts = %s WHERE username = %s",
                    (new_count, username)
                )

        conn.commit()


def reset_failed_attempts(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET failedattempts = 0 WHERE username = %s",
                (username,)
            )
        conn.commit()


def auto_unlock_if_due(user: dict) -> dict:
    """
    If the user's lock period has passed, unlocks them and
    returns the updated user dict. Otherwise returns the
    user dict unchanged.
    """
    if user["status"] != STATUS_LOCKED:
        return user

    if user["lockeduntil"] and datetime.now() >= user["lockeduntil"]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET status = %s, failedattempts = 0, lockeduntil = NULL WHERE userid = %s",
                    (STATUS_ACTIVE, user["userid"])
                )
            conn.commit()

        user = dict(user)
        user["status"] = STATUS_ACTIVE
        user["failedattempts"] = 0
        user["lockeduntil"] = None

    return user


def update_password(userid: int, plain_password: str) -> tuple[bool, str]:
    password_hash, password_salt = hash_password(plain_password)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET passwordhash = %s, passwordsalt = %s, passwordchangedat = %s, mustchangepassword = FALSE
                WHERE userid = %s
                """,
                (password_hash, password_salt, datetime.now(), userid)
            )
        conn.commit()

    return True, "Password updated successfully."


def count_active_users() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM users WHERE status = %s", (STATUS_ACTIVE,))
            return cur.fetchone()["total"]


# =========================================================
# 2. USER MASTER CRUD (ADDED - real schema, module-level
#    functions, mirrors models/company_model.py's shape)
# =========================================================

_USER_MASTER_COLUMNS = (
    "userid, username, fullname, email, phone, roleid, companyid, status, "
    "mustchangepassword, failedattempts, lockeduntil, passwordchangedat, "
    "createddate, createdby, modifieddate, modifiedby"
)


def exists_username(username: str, exclude_userid: Optional[int] = None) -> bool:
    """Case-insensitive uniqueness check, excluding a given userid (for edit)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if exclude_userid is not None:
                cur.execute(
                    "SELECT 1 FROM users WHERE LOWER(username) = LOWER(%s) AND userid != %s",
                    (username, exclude_userid)
                )
            else:
                cur.execute(
                    "SELECT 1 FROM users WHERE LOWER(username) = LOWER(%s)",
                    (username,)
                )
            return cur.fetchone() is not None


def get_user_by_id(userid: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_USER_MASTER_COLUMNS} FROM users WHERE userid = %s", (userid,))
            return cur.fetchone()


def insert_user(data: Dict[str, Any], created_by: str) -> int:
    """
    Creates a new user via the User Master screen. Uses the SAME
    PBKDF2 hashing as the Login screen (engines/password_manager.py)
    so a newly-created user can log in immediately - the User Master
    module must never issue a password hash format the Login screen
    cannot verify.
    """
    password_hash, password_salt = hash_password(data["password"])

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (
                        username, fullname, email, phone, passwordhash, passwordsalt,
                        roleid, companyid, status, mustchangepassword,
                        passwordchangedat, createddate, createdby
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING userid
                    """,
                    (
                        data["username"].strip(), data["fullname"].strip(),
                        data.get("email"), data.get("phone"),
                        password_hash, password_salt,
                        data["role_id"], data.get("company_id"), STATUS_ACTIVE,
                        data.get("must_change_password", True),
                        datetime.now(), datetime.now(), created_by,
                    )
                )
                new_userid = cur.fetchone()["userid"]

                cur.execute(
                    """
                    INSERT INTO user_password_history (userid, passwordhash, passwordsalt, createdat)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (new_userid, password_hash, password_salt, datetime.now())
                )
            conn.commit()
        return new_userid
    except Exception as exc:  # noqa: BLE001
        raise UserModelError(f"Failed to create user: {exc}") from exc


def update_user(userid: int, data: Dict[str, Any], modified_by: str) -> None:
    allowed_fields = {"username": "username", "fullname": "fullname", "email": "email",
                       "phone": "phone", "role_id": "roleid", "company_id": "companyid"}
    set_clauses = []
    params: List[Any] = []

    for key, column in allowed_fields.items():
        if key in data:
            set_clauses.append(f"{column} = %s")
            params.append(data[key])

    if not set_clauses:
        return

    set_clauses.append("modifieddate = %s")
    set_clauses.append("modifiedby = %s")
    params.extend([datetime.now(), modified_by])
    params.append(userid)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE users SET {', '.join(set_clauses)} WHERE userid = %s",
                    tuple(params)
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise UserModelError(f"Failed to update user {userid}: {exc}") from exc


def set_user_status(userid: int, status: str, modified_by: str) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET status = %s, modifieddate = %s, modifiedby = %s WHERE userid = %s",
                    (status, datetime.now(), modified_by, userid)
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise UserModelError(f"Failed to change status for user {userid}: {exc}") from exc


def soft_delete_user(userid: int, deleted_by: str) -> None:
    """Soft delete = status set to Deleted (reuses the existing status enum;
    no separate is_deleted column - keeps one source of truth for user state)."""
    set_user_status(userid, STATUS_DELETED, deleted_by)


def restore_user(userid: int, restored_by: str) -> None:
    set_user_status(userid, STATUS_ACTIVE, restored_by)


def update_user_password(userid: int, plain_password: str, must_change: bool) -> tuple[str, str]:
    """Used by both change_password (self-service) and reset_password (admin)."""
    password_hash, password_salt = hash_password(plain_password)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET passwordhash = %s, passwordsalt = %s, passwordchangedat = %s, mustchangepassword = %s
                    WHERE userid = %s
                    """,
                    (password_hash, password_salt, datetime.now(), must_change, userid)
                )
            conn.commit()
        return password_hash, password_salt
    except Exception as exc:  # noqa: BLE001
        raise UserModelError(f"Failed to update password for user {userid}: {exc}") from exc


def list_users(
    search_term: Optional[str] = None,
    status_filter: str = "all",
    role_id: Optional[int] = None,
    include_deleted: bool = False,
) -> List[dict]:
    where = []
    params: List[Any] = []

    if not include_deleted:
        where.append("status != %s")
        params.append(STATUS_DELETED)

    if status_filter and status_filter != "all":
        where.append("status = %s")
        params.append(status_filter)

    if role_id:
        where.append("roleid = %s")
        params.append(role_id)

    if search_term:
        where.append("(username ILIKE %s OR fullname ILIKE %s OR email ILIKE %s)")
        keyword = f"%{search_term.strip()}%"
        params.extend([keyword, keyword, keyword])

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_USER_MASTER_COLUMNS} FROM users {where_clause} ORDER BY fullname",
                    tuple(params)
                )
                return cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        raise UserModelError(f"Failed to list users: {exc}") from exc


def insert_password_history(userid: int, passwordhash: str, passwordsalt: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_password_history (userid, passwordhash, passwordsalt, createdat) VALUES (%s, %s, %s, %s)",
                (userid, passwordhash, passwordsalt, datetime.now())
            )
        conn.commit()


def get_password_history(userid: int, limit: int = 5) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM user_password_history WHERE userid = %s ORDER BY createdat DESC LIMIT %s",
                (userid, limit)
            )
            return cur.fetchall()


def insert_user_audit(
    userid: int, action: str, performed_by: str,
    old_value: Optional[dict] = None, new_value: Optional[dict] = None,
    remarks: Optional[str] = None,
) -> None:
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_audit_log (userid, action, performedby, oldvalue, newvalue, remarks, actionat)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    userid, action, performed_by,
                    json.dumps(old_value) if old_value is not None else None,
                    json.dumps(new_value) if new_value is not None else None,
                    remarks, datetime.now(),
                )
            )
        conn.commit()
