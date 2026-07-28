"""
=========================================================
Medical ERP V2
Subscription Manager Engine
---------------------------------------------------------
Responsibilities:
    - Subscription active check
    - Renewal / grace period check
    - Max users / max branches check

Same philosophy as license_manager.py: if no subscription
row exists yet, the app runs unrestricted. This becomes
enforced automatically once a real subscription row is
added (i.e. once this ERP starts being sold/licensed).
=========================================================
"""

from datetime import date, timedelta

from database.db import get_connection
from utils.app_logger import get_logger

logger = get_logger()


def validate_subscription() -> tuple[bool, str]:
    """
    Validates the current subscription (if any). Never raises -
    degrades to "unrestricted" on a database problem rather than
    blocking a legitimate user's login.

    Returns
    -------
    (is_valid, message) : tuple[bool, str]
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM subscription ORDER BY subscriptionid DESC LIMIT 1")
                row = cur.fetchone()
    except Exception as e:
        logger.exception(f"validate_subscription: database error ({e})")
        return True, "Subscription check skipped (database unavailable)."

    if row is None:
        return True, "No subscription configured (unrestricted mode)."

    if row["status"] != "Active":
        return False, "Subscription is not active."

    if row["enddate"] is not None:
        grace_deadline = row["enddate"] + timedelta(days=row["gracedays"] or 0)

        if date.today() > grace_deadline:
            return False, "Subscription and grace period have expired."

        if date.today() > row["enddate"]:
            days_left_in_grace = (grace_deadline - date.today()).days
            return True, f"Subscription expired, {days_left_in_grace} grace day(s) remaining."

    return True, "Subscription is active."


def check_user_limit(current_user_count: int) -> tuple[bool, str]:
    """
    Checks current_user_count against the subscription's
    maxusers limit.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT maxusers FROM subscription ORDER BY subscriptionid DESC LIMIT 1")
                row = cur.fetchone()
    except Exception as e:
        logger.exception(f"check_user_limit: database error ({e})")
        return True, "User limit check skipped (database unavailable)."

    if row is None:
        return True, "No user limit configured."

    if current_user_count >= row["maxusers"]:
        return False, f"Maximum user limit ({row['maxusers']}) reached for this subscription plan."

    return True, "Within user limit."
