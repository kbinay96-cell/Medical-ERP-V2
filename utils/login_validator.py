"""
=========================================================
Medical ERP V2
Login Validator
---------------------------------------------------------
Purpose:
    Validates raw Login screen input BEFORE it reaches the
    Authentication Engine. Pure validation only - no
    database access, no business rules about accounts.
=========================================================
"""

MAX_USERNAME_LENGTH = 50


def validate_login_input(username: str, password: str, company_id: str, financial_year: str) -> tuple[bool, str]:
    """
    Validates the 4 mandatory Login screen fields.

    Returns
    -------
    (is_valid, message) : tuple[bool, str]
        message is empty string when is_valid is True.
    """
    if username is None or username.strip() == "":
        return False, "Username is required."

    if username != username.strip():
        return False, "Username must not have leading or trailing spaces."

    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username must not exceed {MAX_USERNAME_LENGTH} characters."

    if password is None or password == "":
        return False, "Password is required."

    if not company_id:
        return False, "Company is required."

    if not financial_year:
        return False, "Financial Year is required."

    return True, ""
