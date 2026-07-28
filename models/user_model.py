"""
=========================================================
Medical ERP V2
User Model
---------------------------------------------------------
Purpose:
    All database operations for the `users` table.
    Business rules around login attempts / locking live
    here (Model layer), not in the Screen.
=========================================================
"""

from datetime import datetime, timedelta

from database.db import get_connection
from config.settings import MAX_FAILED_LOGIN_ATTEMPTS, ACCOUNT_AUTO_UNLOCK_MINUTES, STATUS_LOCKED, STATUS_ACTIVE
from engines.password_manager import hash_password


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
