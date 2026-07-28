"""
=========================================================
Medical ERP V2
Password Manager Engine
---------------------------------------------------------
Responsibilities:
    - Password hashing
    - Password verification
    - Password policy check
    - Password expiration check

Passwords are NEVER stored or logged in plain text.
Uses PBKDF2-HMAC-SHA256 (Python standard library `hashlib`,
no extra dependency needed) with a random salt per user.
=========================================================
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from config.settings import PASSWORD_MIN_LENGTH, PASSWORD_EXPIRY_DAYS

PBKDF2_ITERATIONS = 200_000


def hash_password(plain_password: str) -> tuple[str, str]:
    """
    Hashes a plain-text password.

    Returns
    -------
    (password_hash, password_salt) : tuple[str, str]
        Both are hex strings, safe to store in the database.
    """
    salt = secrets.token_hex(16)
    hashed = _derive(plain_password, salt)
    return hashed, salt


def verify_password(plain_password: str, stored_hash: str, stored_salt: str) -> bool:
    """
    Verifies a plain-text password against a stored hash+salt.
    Uses constant-time comparison to avoid timing attacks.
    """
    computed = _derive(plain_password, stored_salt)
    return hmac.compare_digest(computed, stored_hash)


def _derive(plain_password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )
    return derived.hex()


def check_password_policy(plain_password: str) -> tuple[bool, str]:
    """
    Checks a plain-text password against the password policy.

    Returns
    -------
    (is_valid, message) : tuple[bool, str]
    """
    if len(plain_password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."

    if not any(c.isupper() for c in plain_password):
        return False, "Password must contain an uppercase letter."

    if not any(c.islower() for c in plain_password):
        return False, "Password must contain a lowercase letter."

    if not any(c.isdigit() for c in plain_password):
        return False, "Password must contain a number."

    if not any(not c.isalnum() for c in plain_password):
        return False, "Password must contain a special character."

    return True, "Password meets policy."


def is_password_expired(password_changed_at: datetime, expiry_days: int = PASSWORD_EXPIRY_DAYS) -> bool:
    """
    Returns True if the password is older than the expiry policy.
    """
    if password_changed_at is None:
        return False

    expiry_date = password_changed_at + timedelta(days=expiry_days)
    return datetime.now() > expiry_date


def generate_remember_token() -> str:
    """
    Generates a secure random token for 'Remember Me'.
    The plain token is what gets stored in an encrypted
    cookie/local file on the client; only its hash is
    stored in the database (never the plain password).
    """
    return secrets.token_urlsafe(32)
