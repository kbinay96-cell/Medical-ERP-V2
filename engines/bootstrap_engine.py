"""
engines/bootstrap_engine.py

First-time setup: creates the first company, financial year, and
Administrator user when the database is completely empty. This is
the only path that bypasses the normal permission-checked Company/
User creation flows -- strictly gated on "no users exist yet".
"""

from __future__ import annotations

from engines.authentication_engine import ADMIN_ROLE_NAME
from engines.exceptions import ValidationError
from models import company_model, financialyear_model, role_model, user_model


def is_bootstrap_needed() -> bool:
    """True only when there isn't a single active user in the system yet."""
    return user_model.count_active_users() == 0


def create_first_company_and_admin(
    companyname: str,
    financialyear: str,
    startbsdate: str,
    endbsdate: str,
    admin_username: str,
    admin_password: str,
    admin_fullname: str,
) -> None:
    if not is_bootstrap_needed():
        raise ValidationError(["Setup has already been completed. Please log in normally."])

    errors = []
    if not companyname.strip():
        errors.append("Company name is required.")
    if not (financialyear.strip() and startbsdate.strip() and endbsdate.strip()):
        errors.append("Financial year details are required.")
    if not admin_username.strip():
        errors.append("Admin username is required.")
    if not admin_password:
        errors.append("Admin password is required.")
    if errors:
        raise ValidationError(errors)

    company_id = company_model.insert_company({"companyname": companyname.strip()}, created_by="system")

    financialyear_model.insert_financial_year(
        financialyear=financialyear.strip(),
        startbsdate=startbsdate.strip(),
        endbsdate=endbsdate.strip(),
        startaddate=None,
        endaddate=None,
        isactive=True,
    )

    admin_role = role_model.get_role_by_name(ADMIN_ROLE_NAME)
    if not admin_role:
        raise ValidationError([f"'{ADMIN_ROLE_NAME}' role not found -- database seed may be incomplete."])

    success, message = user_model.create_user(
        username=admin_username.strip(),
        plain_password=admin_password,
        fullname=admin_fullname.strip() or admin_username.strip(),
        roleid=admin_role["roleid"],
        companyid=company_id,
        created_by="system",
    )
    if not success:
        raise ValidationError([message])