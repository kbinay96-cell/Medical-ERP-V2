"""
engines/password_reset_engine.py

Forgot-password flow: WhatsApp deep-link request + admin approval.
"""

from __future__ import annotations

import secrets

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.audit_logger import write_audit_log
from engines.user_engine import UserEngine
from models import user_model, password_reset_model
from config.settings import AUDIT_PASSWORD_RESET


REQUEST_RATE_LIMIT_WINDOW_MINUTES = 60
REQUEST_RATE_LIMIT_MAX = 3


def request_reset(username: str) -> tuple[int, str, int]:
    """
    Creates a pending reset request for `username`.
    Returns (request_id, request_code, expiry_minutes).
    Raises ValidationError if there's already an active pending
    request, or if the per-user rate limit has been hit.
    """
    user = user_model.get_user_by_username(username)
    if not user:
        raise RecordNotFoundError("No account found with that username.")

    active = password_reset_model.get_active_pending_for_user(user["userid"])
    if active:
        raise ValidationError([
            "You already have a pending reset request. Please check WhatsApp, "
            "or wait for it to expire before requesting a new one."
        ])

    recent_count = password_reset_model.count_recent_requests(user["userid"], REQUEST_RATE_LIMIT_WINDOW_MINUTES)
    if recent_count >= REQUEST_RATE_LIMIT_MAX:
        raise ValidationError([
            "Too many reset requests recently. Please wait before trying again, "
            "or contact the administrator."
        ])

    request_code = f"{secrets.randbelow(1_000_000):06d}"
    request_id = password_reset_model.insert_request(user["userid"], username, request_code)
    return request_id, request_code, password_reset_model.REQUEST_EXPIRY_MINUTES


def get_pending_requests() -> list[dict]:
    return password_reset_model.get_pending_requests()


def approve_request(request_id: int, approved_by: str) -> str:
    """
    Approves a pending request: generates a policy-valid temp
    password (via UserEngine.reset_password, reusing its existing
    history-validation + mustchangepassword=True + audit logic),
    and returns the temp password so the admin can relay it back
    to the user via WhatsApp reply.
    """
    request = password_reset_model.get_request_by_id(request_id)
    if not request:
        raise RecordNotFoundError("Reset request not found.")
    if request["status"] != "Pending":
        raise ValidationError([f"Request is already {request['status']}."])

    engine = UserEngine()
    temp_password = None
    last_error = None
    for _ in range(5):
        candidate = _generate_temp_password()
        try:
            engine.reset_password(request["userid"], candidate, approved_by)
            temp_password = candidate
            break
        except ValidationError as exc:
            last_error = exc
            continue
    if temp_password is None:
        raise last_error or ValidationError(["Could not generate a valid temporary password."])

    write_audit_log(
        AUDIT_PASSWORD_RESET, userid=request["userid"], username=request["username"],
        details=f"Approved forgot-password request #{request_id} by {approved_by}",
    )
    password_reset_model.mark_approved(request_id, approved_by, temp_password)

    reset_user = user_model.get_user_by_username(request["username"])
    phone = (reset_user.get("phone") if reset_user else None) or None
    return temp_password, phone


def reject_request(request_id: int, rejected_by: str) -> None:
    request = password_reset_model.get_request_by_id(request_id)
    if not request:
        raise RecordNotFoundError("Reset request not found.")
    password_reset_model.mark_rejected(request_id, rejected_by)


def _generate_temp_password() -> str:
    """Generates a readable temp password satisfying the password policy."""
    upper, lower, digits, special = "ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789", "!@#$%"
    parts = [secrets.choice(upper), secrets.choice(lower), secrets.choice(digits), secrets.choice(special)]
    parts += [secrets.choice(upper + lower + digits) for _ in range(4)]
    secrets.SystemRandom().shuffle(parts)
    return "".join(parts)