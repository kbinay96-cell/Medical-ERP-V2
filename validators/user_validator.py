"""
validators/user_validator.py

User Master field-level and business-rule validation - Medical ERP V2.
Function-based, mirrors validators/company_validator.py's shape (a plain
validate_x_data() function returning a list of error strings), consistent
with the rest of the project's Validator layer. Raises nothing itself -
callers (UserEngine) decide how to turn the error list into a ValidationError.
"""

from __future__ import annotations

import re
from typing import List, Optional

from models import user_model

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.]{4,50}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8


def validate_user_data(data: dict, is_update: bool = False, exclude_userid: Optional[int] = None) -> List[str]:
    """
    Validates data for create (is_update=False) or update (is_update=True).
    On update, only the fields actually present in `data` are checked -
    a partial update should not fail because unrelated fields are "missing".
    """
    errors: List[str] = []

    if not is_update or "username" in data:
        errors += _validate_username(data.get("username"))
        username = data.get("username")
        if username and user_model.exists_username(username, exclude_userid=exclude_userid):
            errors.append("Username already exists.")

    if not is_update or "fullname" in data:
        errors += _validate_fullname(data.get("fullname"))

    if "email" in data:
        errors += _validate_email(data.get("email"))

    if not is_update:
        errors += validate_password_strength(data.get("password"))
        if not data.get("role_id"):
            errors.append("Role is required.")

    if errors:
        return errors
    return []


def validate_password_strength(password: Optional[str]) -> List[str]:
    errs: List[str] = []
    if not password:
        errs.append("Password is required.")
        return errs
    if len(password) < MIN_PASSWORD_LENGTH:
        errs.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not re.search(r"[A-Z]", password):
        errs.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errs.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errs.append("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*()\-_=+{};:,<.>]", password):
        errs.append("Password must contain at least one special character.")
    return errs


def validate_password_change(new_password: str, history_rows: List[dict], verify_password_fn) -> List[str]:
    """
    `history_rows` are rows from user_model.get_password_history() -
    each has passwordhash + passwordsalt. `verify_password_fn` is
    engines.password_manager.verify_password(plain, hash, salt).
    """
    errors = validate_password_strength(new_password)
    for row in history_rows:
        if verify_password_fn(new_password, row["passwordhash"], row["passwordsalt"]):
            errors.append("Password matches a previously used password. Choose a different one.")
            break
    return errors


# ---- Field-level rules ----

def _validate_username(username: Optional[str]) -> List[str]:
    errs = []
    if not username:
        errs.append("Username is required.")
    elif not USERNAME_PATTERN.match(username):
        errs.append("Username must be 4-50 characters: letters, numbers, dot, underscore only.")
    return errs


def _validate_fullname(name: Optional[str]) -> List[str]:
    if not name or not name.strip():
        return ["Full name is required."]
    if len(name) > 150:
        return ["Full name exceeds maximum length."]
    return []


def _validate_email(email: Optional[str]) -> List[str]:
    if email and not EMAIL_PATTERN.match(email):
        return ["Email format is invalid."]
    return []
