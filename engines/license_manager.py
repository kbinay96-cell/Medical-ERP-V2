"""
=========================================================
Medical ERP V2
License Manager Engine
---------------------------------------------------------
Responsibilities:
    - License validation
    - Expiration check
    - Machine verification
    - Enabled module check

NOTE: Since this ERP is currently for single/direct use
(not yet being sold to other pharmacies), this engine
defaults to a permissive "no license row = unrestricted"
behaviour. Once ready to sell/license the product, insert
a real row into the `license` table and this engine will
start enforcing it automatically - no code change needed.
=========================================================
"""

from datetime import date
import uuid

from database.db import get_connection
from utils.app_logger import get_logger

logger = get_logger()


def get_machine_id() -> str:
    """
    Returns a stable identifier for the current machine,
    used for machine-locked licensing.
    """
    return str(uuid.getnode())


def validate_license() -> tuple[bool, str]:
    """
    Validates the license row (if any) against this machine
    and the current date. Never raises - a database problem
    here degrades to "unrestricted" rather than blocking login
    entirely, since license infrastructure failing should not
    lock a legitimate user out of their own business data.

    Returns
    -------
    (is_valid, message) : tuple[bool, str]
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM license ORDER BY licenseid DESC LIMIT 1")
                row = cur.fetchone()
    except Exception as e:
        logger.exception(f"validate_license: database error ({e})")
        return True, "License check skipped (database unavailable)."

    if row is None:
        # No license configured yet -> not being sold/licensed yet, allow.
        return True, "No license configured (unrestricted mode)."

    if row["status"] != "Active":
        return False, "License is not active."

    if row["expirydate"] is not None and date.today() > row["expirydate"]:
        return False, "License has expired."

    if row["machineid"] and row["machineid"] != get_machine_id():
        return False, "License is not valid for this machine."

    return True, "License is valid."


def is_module_enabled(module_name: str) -> bool:
    """
    Checks whether a given module name is included in the
    license's enabled-modules list. If no license row exists,
    every module is considered enabled (unrestricted mode).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT enabledmodules FROM license ORDER BY licenseid DESC LIMIT 1")
                row = cur.fetchone()
    except Exception as e:
        logger.exception(f"is_module_enabled: database error ({e})")
        return True

    if row is None or not row["enabledmodules"]:
        return True

    enabled = [m.strip() for m in row["enabledmodules"].split(",")]
    return module_name in enabled
