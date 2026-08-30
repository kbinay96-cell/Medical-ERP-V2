"""
engines/user_engine.py

User Master business logic - Medical ERP V2.
Mirrors engines/company_engine.py's shape exactly (DTO in/out, shared
exceptions from engines/exceptions.py, no SQL, no UI). This is the ONLY
layer Screens are allowed to call for User Master.

NOTE: This module was rewritten to align with the REAL, live `users`
table (database/schema_auth.sql), which the Login/Session/Audit/
Dashboard modules already depend on. It intentionally does NOT use
security/password_security.py (Argon2id) - that produces a hash format
the Login screen's verify_password() cannot read. User Master uses the
same engines/password_manager.py (PBKDF2) the Login screen already
verifies against, so a user created here can log in immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from config.settings import STATUS_ACTIVE, STATUS_DISABLED, STATUS_DELETED
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.password_manager import verify_password
from models import user_model
from models.user_model import UserModelError
from utils import image_manager
from validators.user_validator import validate_user_data, validate_password_change


@dataclass
class UserDTO:
    user_id: int
    username: str
    fullname: str
    email: Optional[str]
    phone: Optional[str]
    role_id: int
    role_name: Optional[str]
    company_id: Optional[str]
    status: str
    must_change_password: bool
    failed_attempts: int
    created_date: object
    created_by: Optional[str]
    photo_path: Optional[str] = None

    @property
    def is_deleted(self) -> bool:
        return self.status == STATUS_DELETED

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE


def _row_to_dto(row: dict) -> UserDTO:
    return UserDTO(
        user_id=row["userid"],
        username=row["username"],
        fullname=row["fullname"],
        email=row.get("email"),
        phone=row.get("phone"),
        role_id=row["roleid"],
        role_name=row.get("rolename"),
        company_id=row.get("companyid"),
        status=row["status"],
        must_change_password=bool(row.get("mustchangepassword")),
        failed_attempts=row.get("failedattempts") or 0,
        created_date=row.get("createddate"),
        created_by=row.get("createdby"),
        photo_path=row.get("photo_path"),
    )


class UserEngine:
    """Business logic for the User Master. Screens call ONLY this class."""

    # ---------------- CREATE ----------------

    def create_user(self, data: dict, current_user_id) -> UserDTO:
        errors = validate_user_data(data, is_update=False)
        if errors:
            raise ValidationError(errors)

        data = dict(data)
        data["photo_path"] = image_manager.apply_entity_photo(
            data,
            existing_path=None,
            subfolder="users",
            filename_stem=(data.get("username") or "user").strip(),
        )

        try:
            userid = user_model.insert_user(data, created_by=str(current_user_id))
            user_model.insert_user_audit(
                userid=userid, action="CREATE", performed_by=str(current_user_id),
                old_value=None, new_value={"username": data["username"], "role_id": data.get("role_id")},
                remarks="User created",
            )
            row = user_model.get_user_by_id(userid)
            return _row_to_dto(row)
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

    # ---------------- UPDATE ----------------

    def update_user(self, user_id: int, data: dict, current_user_id) -> UserDTO:
        existing = user_model.get_user_by_id(user_id)
        if not existing or existing["status"] == STATUS_DELETED:
            raise RecordNotFoundError(f"User '{user_id}' not found.")

        errors = validate_user_data(data, is_update=True, exclude_userid=user_id)
        if errors:
            raise ValidationError(errors)

        data = dict(data)
        data["photo_path"] = image_manager.apply_entity_photo(
            data,
            existing_path=existing.get("photo_path"),
            subfolder="users",
            filename_stem=(data.get("username") or existing.get("username") or str(user_id)).strip(),
        )

        try:
            user_model.update_user(user_id, data, modified_by=str(current_user_id))
            user_model.insert_user_audit(
                userid=user_id, action="UPDATE", performed_by=str(current_user_id),
                old_value=_snapshot(existing), new_value=data, remarks="User updated",
            )
            row = user_model.get_user_by_id(user_id)
            return _row_to_dto(row)
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

    # ---------------- STATUS ----------------

    def set_active_status(self, user_id: int, is_active: bool, current_user_id) -> UserDTO:
        existing = user_model.get_user_by_id(user_id)
        if not existing or existing["status"] == STATUS_DELETED:
            raise RecordNotFoundError(f"User '{user_id}' not found.")

        new_status = STATUS_ACTIVE if is_active else STATUS_DISABLED
        try:
            user_model.set_user_status(user_id, new_status, modified_by=str(current_user_id))
            user_model.insert_user_audit(
                userid=user_id, action="ACTIVATE" if is_active else "DEACTIVATE",
                performed_by=str(current_user_id), old_value={"status": existing["status"]},
                new_value={"status": new_status}, remarks=None,
            )
            row = user_model.get_user_by_id(user_id)
            return _row_to_dto(row)
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

    # ---------------- SOFT DELETE / RESTORE ----------------

    def delete_user(self, user_id: int, current_user_id, remarks: Optional[str] = None) -> None:
        existing = user_model.get_user_by_id(user_id)
        if not existing or existing["status"] == STATUS_DELETED:
            raise RecordNotFoundError(f"User '{user_id}' not found.")
        try:
            user_model.soft_delete_user(user_id, deleted_by=str(current_user_id))
            user_model.insert_user_audit(
                userid=user_id, action="DELETE", performed_by=str(current_user_id),
                old_value=None, new_value=None, remarks=remarks,
            )
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

    def restore_user(self, user_id: int, current_user_id) -> UserDTO:
        existing = user_model.get_user_by_id(user_id)
        if not existing or existing["status"] != STATUS_DELETED:
            raise RecordNotFoundError(f"User '{user_id}' not found or not deleted.")
        try:
            user_model.restore_user(user_id, restored_by=str(current_user_id))
            user_model.insert_user_audit(
                userid=user_id, action="RESTORE", performed_by=str(current_user_id),
                old_value=None, new_value=None, remarks="User restored",
            )
            row = user_model.get_user_by_id(user_id)
            return _row_to_dto(row)
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

    # ---------------- PASSWORD MANAGEMENT ----------------

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        """Self-service: user changes their own password, knowing the old one."""
        user = user_model.get_user_by_id(user_id)
        if not user or user["status"] == STATUS_DELETED:
            raise RecordNotFoundError("User not found.")

        full_user = user_model.get_user_by_username(user["username"])
        if not verify_password(old_password, full_user["passwordhash"], full_user["passwordsalt"]):
            raise ValidationError(["Current password is incorrect."])

        history = user_model.get_password_history(user_id)
        errors = validate_password_change(new_password, history, verify_password)
        if errors:
            raise ValidationError(errors)

        new_hash, new_salt = user_model.update_user_password(user_id, new_password, must_change=False)
        user_model.insert_password_history(user_id, new_hash, new_salt)
        user_model.insert_user_audit(
            userid=user_id, action="PASSWORD_CHANGE", performed_by=str(user_id),
            old_value=None, new_value=None, remarks=None,
        )

    def reset_password(self, user_id: int, new_password: str, reset_by) -> None:
        """Admin-initiated reset - forces user to change password on next login."""
        user = user_model.get_user_by_id(user_id)
        if not user or user["status"] == STATUS_DELETED:
            raise RecordNotFoundError("User not found.")

        history = user_model.get_password_history(user_id)
        errors = validate_password_change(new_password, history, verify_password)
        if errors:
            raise ValidationError(errors)

        new_hash, new_salt = user_model.update_user_password(user_id, new_password, must_change=True)
        user_model.insert_password_history(user_id, new_hash, new_salt)
        user_model.insert_user_audit(
            userid=user_id, action="PASSWORD_RESET", performed_by=str(reset_by),
            old_value=None, new_value=None, remarks=None,
        )

    # ---------------- SEARCH / RETRIEVAL ----------------

    def get_user(self, user_id: int) -> UserDTO:
        row = user_model.get_user_by_id(user_id)
        if not row:
            raise RecordNotFoundError(f"User '{user_id}' not found.")
        return _row_to_dto(row)

    def search_users(
        self,
        search_text: Optional[str] = None,
        status: Optional[str] = None,
        role_id: Optional[int] = None,
        company_id: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 500,
    ) -> Tuple[List[UserDTO], int]:
        status_filter = status if status else "all"
        try:
            rows = user_model.list_users(
                search_term=search_text, status_filter=status_filter,
                role_id=role_id, company_id=company_id, include_deleted=include_deleted,
            )
        except UserModelError as exc:
            raise RuntimeError(str(exc)) from exc

        total = len(rows)
        start = (page - 1) * page_size
        page_rows = rows[start:start + page_size]
        return [_row_to_dto(r) for r in page_rows], total


def _snapshot(row: dict) -> dict:
    return {
        "username": row.get("username"),
        "fullname": row.get("fullname"),
        "email": row.get("email"),
        "roleid": row.get("roleid"),
        "companyid": row.get("companyid"),
    }


__all__ = ["UserEngine", "UserDTO"]
