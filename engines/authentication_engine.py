"""
=========================================================
Medical ERP V2
Authentication Engine
---------------------------------------------------------
Responsibilities:
    - User authentication (the full Login workflow)
    - Logout workflow

Flow (per Blueprint Part-2 / Part-3):
    Validate Input
    -> Check User Exists
    -> Verify Password
    -> Check User Status
    -> Check License
    -> Check Subscription
    -> Load Role / Permissions
    -> Create Session
    -> Write Login History
    -> Write Audit Log

No SQL is written directly in this file - it calls into
Models and other Engines. No UI code here.
=========================================================
"""

import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.settings import (
    STATUS_LOCKED, STATUS_DISABLED, STATUS_SUSPENDED,
    STATUS_EXPIRED, STATUS_DELETED,
    AUDIT_LOGIN, AUDIT_LOGOUT,
)
from utils.app_logger import get_logger
from utils.login_validator import validate_login_input
from engines.password_manager import verify_password
from engines.license_manager import validate_license
from engines.subscription_manager import validate_subscription
from engines.session_manager import create_session, destroy_session
from engines.authorization_engine import get_accessible_menus
from engines.audit_logger import write_audit_log, write_login_history, write_logout_time, write_failed_login
from models.user_model import get_user_by_username, register_failed_attempt, reset_failed_attempts, auto_unlock_if_due
from models.role_model import get_role_name

logger = get_logger()

ADMIN_ROLE_NAME = "Administrator"


@dataclass
class LoginResult:
    success: bool
    message: str
    userid: int | None = None
    username: str | None = None
    fullname: str | None = None
    roleid: int | None = None
    rolename: str | None = None
    is_admin: bool = False
    companyid: str | None = None
    financialyear: str | None = None
    session_id: str | None = None
    login_time: datetime | None = None
    machine_name: str | None = None
    accessible_menus: list = field(default_factory=list)


def login(username: str, password: str, company_id: str, financial_year: str) -> LoginResult:
    """
    Runs the complete Login workflow and returns a LoginResult.
    This is the ONLY function the Login Screen should call.

    Global exception handling: any unexpected error (e.g. a
    database outage) is caught, logged in full, and turned
    into a safe, generic message for the user - the app must
    never crash here and must never leak internal error
    details to the UI.
    """
    try:
        return _login_workflow(username, password, company_id, financial_year)
    except Exception as e:
        logger.exception(f"Unexpected error during login for username='{username}': {e}")
        return LoginResult(success=False, message="An unexpected error occurred. Please try again or contact support.")


def _login_workflow(username: str, password: str, company_id: str, financial_year: str) -> LoginResult:

    # ---------- 1. Validate Input ----------
    is_valid, message = validate_login_input(username, password, company_id, financial_year)
    if not is_valid:
        return LoginResult(success=False, message=message)

    # ---------- 2. Check User Exists ----------
    user = get_user_by_username(username)
    if user is None:
        write_failed_login(username, "User not found.")
        return LoginResult(success=False, message="Invalid username or password.")

    # ---------- Auto-unlock if lock period has passed ----------
    user = auto_unlock_if_due(user)

    # ---------- 3. Check User Status (before password, so a
    #              locked/disabled account never leaks whether
    #              the password was right) ----------
    if user["status"] == STATUS_LOCKED:
        write_failed_login(username, "Account is locked.")
        return LoginResult(success=False, message="User account is locked. Please try again later or contact the administrator.")

    if user["status"] == STATUS_DISABLED:
        write_failed_login(username, "Account is disabled.")
        return LoginResult(success=False, message="User account is disabled.")

    if user["status"] == STATUS_SUSPENDED:
        write_failed_login(username, "Account is suspended.")
        return LoginResult(success=False, message="User account is suspended.")

    if user["status"] in (STATUS_EXPIRED, STATUS_DELETED):
        write_failed_login(username, "Account is expired or deleted.")
        return LoginResult(success=False, message="Invalid username or password.")

    # ---------- 4. Verify Password ----------
    if not verify_password(password, user["passwordhash"], user["passwordsalt"]):
        register_failed_attempt(username)
        write_failed_login(username, "Incorrect password.")
        return LoginResult(success=False, message="Invalid username or password.")

    # Correct password -> clear any failed-attempt counter
    reset_failed_attempts(username)

    # ---------- 5. Check License ----------
    license_ok, license_message = validate_license()
    if not license_ok:
        write_audit_log(AUDIT_LOGIN, user["userid"], username, f"Blocked - {license_message}")
        return LoginResult(success=False, message=license_message)

    # ---------- 6. Check Subscription ----------
    subscription_ok, subscription_message = validate_subscription()
    if not subscription_ok:
        write_audit_log(AUDIT_LOGIN, user["userid"], username, f"Blocked - {subscription_message}")
        return LoginResult(success=False, message=subscription_message)

    # ---------- 7. Load Role / Permissions ----------
    accessible_menus = get_accessible_menus(user["roleid"])
    role_name = get_role_name(user["roleid"])
    is_admin = role_name == ADMIN_ROLE_NAME

    # ---------- 8. Create Session ----------
    session = create_session(user["userid"], company_id, financial_year)
    login_time = datetime.now()
    machine_name = socket.gethostname()

    # ---------- 9. Write Login History ----------
    write_login_history(user["userid"], username, company_id, financial_year, session["sessionid"])

    # ---------- 10. Write Audit Log ----------
    write_audit_log(AUDIT_LOGIN, user["userid"], username, "Successful login.")

    logger.info(f"Login successful: user='{username}' role='{role_name}' machine='{machine_name}'")

    return LoginResult(
        success=True,
        message="Login successful.",
        userid=user["userid"],
        username=username,
        fullname=user["fullname"],
        roleid=user["roleid"],
        rolename=role_name,
        is_admin=is_admin,
        companyid=company_id,
        financialyear=financial_year,
        session_id=session["sessionid"],
        login_time=login_time,
        machine_name=machine_name,
        accessible_menus=accessible_menus,
    )


def logout(userid: int, username: str, session_id: str) -> None:
    """
    Runs the Logout workflow: ends the session, records the
    logout time, and writes an audit entry. Never raises -
    logout should always succeed from the user's perspective
    even if a background write fails (the failure is logged).
    """
    try:
        destroy_session(session_id)
        write_logout_time(session_id)
        write_audit_log(AUDIT_LOGOUT, userid, username, "User logged out.")
        logger.info(f"Logout: user='{username}' session='{session_id}'")
    except Exception as e:
        logger.exception(f"Unexpected error during logout for username='{username}': {e}")
