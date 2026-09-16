"""
=========================================================
Medical ERP V2
Remembered Logins (Login screen "Remember Me")
---------------------------------------------------------
Purpose:
    Locally stores username/password/company/financial-year
    combinations the user has chosen to remember on the Login
    screen, so the username field can autocomplete and, on
    selecting a suggestion, the rest of the form autofills --
    the same UX as a browser's saved-password autofill.

    Passwords are NEVER stored in plain text. Each password is
    encrypted with Windows DPAPI (CryptProtectData), which ties
    the encrypted bytes to the current Windows user account --
    only a process running as that same Windows user can decrypt
    them (CryptUnprotectData). This mirrors how Chrome/Edge store
    saved passwords locally. If a different Windows user account
    runs this app, decryption fails for entries saved by another
    account -- such entries are treated as unreadable and skipped.

    Storage location: %APPDATA%\\MedicalERP\\remembered_logins.json
=========================================================
"""

import base64
import json
import os

import win32crypt

from utils.app_logger import get_logger

logger = get_logger()

_STORE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MedicalERP")
_STORE_FILE = os.path.join(_STORE_DIR, "remembered_logins.json")


def _encrypt(plain_text: str) -> str:
    encrypted_bytes = win32crypt.CryptProtectData(plain_text.encode("utf-8"), None, None, None, None, 0)
    return base64.b64encode(encrypted_bytes).decode("ascii")


def _decrypt(encrypted_b64: str):
    try:
        encrypted_bytes = base64.b64decode(encrypted_b64)
        decrypted = win32crypt.CryptUnprotectData(encrypted_bytes, None, None, None, 0)
        return decrypted[1].decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to decrypt a remembered login (likely saved by a different Windows account): {e}")
        return None


def _load_store() -> dict:
    if not os.path.exists(_STORE_FILE):
        return {}
    try:
        with open(_STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read remembered logins store: {e}")
        return {}


def _write_store(store: dict) -> None:
    os.makedirs(_STORE_DIR, exist_ok=True)
    try:
        with open(_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f)
    except OSError as e:
        logger.error(f"Failed to write remembered logins store: {e}")


def get_remembered_usernames() -> list:
    """Returns usernames with a locally saved login, for the
    Login screen's username autocomplete."""
    return list(_load_store().keys())


def load_remembered_login(username: str):
    """Returns {"password": str, "company_id": ..., "financial_year": ...}
    for a remembered username, or None if not found / undecryptable."""
    store = _load_store()
    entry = store.get(username)
    if entry is None:
        return None
    password = _decrypt(entry.get("password_encrypted", ""))
    if password is None:
        return None
    return {
        "password": password,
        "company_id": entry.get("company_id"),
        "financial_year": entry.get("financial_year"),
    }


def save_remembered_login(username: str, password: str, company_id, financial_year) -> None:
    store = _load_store()
    store[username] = {
        "password_encrypted": _encrypt(password),
        "company_id": company_id,
        "financial_year": financial_year,
    }
    _write_store(store)


def remove_remembered_login(username: str) -> None:
    store = _load_store()
    if username in store:
        del store[username]
        _write_store(store)