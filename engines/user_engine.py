"""
User Engine
Layer: Engine (Business Logic)
Responsibility: Orchestrates Model + Validator + PasswordSecurity + AuditLog.
This is the ONLY layer Screens/Controllers are allowed to call for User Master.
"""

from typing import Optional, List
from models.user_model import UserModel, UserRecord
from validators.user_validator import UserValidator, ValidationError
from security.password_security import PasswordSecurity, ALGO_NAME
from core.date_engine import DateEngine  # existing frozen engine


class UserEngine:

    def __init__(self, user_model: UserModel, validator: UserValidator):
        self._model = user_model
        self._validator = validator

    # ---------------- CREATE ----------------

    def create_user(self, data: dict, created_by: int) -> int:
        self._validator.validate_create(data)

        password_hash = PasswordSecurity.hash_password(data["password"])
        bs_today = DateEngine.today_bs()

        record = UserRecord(
            user_id=None,
            username=data["username"].strip(),
            display_name=data["display_name"].strip(),
            email=data.get("email"),
            phone=data.get("phone"),
            password_hash=password_hash,
            password_algo=ALGO_NAME,
            must_change_password=data.get("must_change_password", True),
            role_id=data.get("role_id"),
            company_id=data.get("company_id"),
            is_active=data.get("is_active", True),
            is_deleted=False,
            created_on_bs=bs_today,
            created_by=created_by,
            updated_on_bs=None,
            updated_by=None,
        )

        user_id = self._model.insert(record)
        self._model.insert_password_history(user_id, password_hash, ALGO_NAME, bs_today)

        self._model.insert_audit(
            user_id=user_id, action="CREATE", performed_by=created_by,
            old_value=None, new_value={"username": record.username, "role_id": record.role_id},
            remarks="User created", action_on_bs=bs_today
        )
        return user_id

    # ---------------- UPDATE ----------------

    def update_user(self, user_id: int, data: dict, updated_by: int) -> None:
        self._validator.validate_update(user_id, data)

        existing = self._model.get_by_id(user_id)
        if not existing or existing.is_deleted:
            raise ValidationError(["User not found or has been deleted."])

        bs_today = DateEngine.today_bs()
        allowed_fields = {"username", "display_name", "email", "phone", "role_id", "company_id"}
        update_fields = {k: v for k, v in data.items() if k in allowed_fields}

        self._model.update(user_id, update_fields, updated_by, bs_today)

        self._model.insert_audit(
            user_id=user_id, action="UPDATE", performed_by=updated_by,
            old_value=self._snapshot(existing), new_value=update_fields,
            remarks="User updated", action_on_bs=bs_today
        )

    # ---------------- STATUS ----------------

    def set_active_status(self, user_id: int, is_active: bool, changed_by: int) -> None:
        bs_today = DateEngine.today_bs()
        self._model.update(user_id, {"is_active": is_active}, changed_by, bs_today)
        self._model.insert_audit(
            user_id=user_id,
            action="ACTIVATE" if is_active else "DEACTIVATE",
            performed_by=changed_by, old_value=None, new_value={"is_active": is_active},
            remarks=None, action_on_bs=bs_today
        )

    # ---------------- SOFT DELETE / RESTORE ----------------

    def delete_user(self, user_id: int, deleted_by: int, remarks: Optional[str] = None) -> None:
        bs_today = DateEngine.today_bs()
        self._model.soft_delete(user_id, deleted_by, bs_today)
        self._model.insert_audit(
            user_id=user_id, action="DELETE", performed_by=deleted_by,
            old_value=None, new_value=None, remarks=remarks, action_on_bs=bs_today
        )

    def restore_user(self, user_id: int, restored_by: int) -> None:
        bs_today = DateEngine.today_bs()
        self._model.restore(user_id, restored_by, bs_today)
        self._model.insert_audit(
            user_id=user_id, action="RESTORE", performed_by=restored_by,
            old_value=None, new_value=None, remarks="User restored", action_on_bs=bs_today
        )

    # ---------------- PASSWORD MANAGEMENT ----------------

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        user = self._model.get_by_id(user_id)
        if not user or user.is_deleted:
            raise ValidationError(["User not found."])

        if not PasswordSecurity.verify_password(old_password, user.password_hash):
            raise ValidationError(["Current password is incorrect."])

        history = self._model.get_password_history(user_id)
        history_hashes = [h["password_hash"] for h in history]

        self._validator.validate_password_change(
            new_password, history_hashes, PasswordSecurity.verify_password
        )

        self._apply_new_password(user_id, new_password, must_change=False, action="PASSWORD_CHANGE",
                                  performed_by=user_id)

    def reset_password(self, user_id: int, new_password: str, reset_by: int) -> None:
        """Admin-initiated reset — forces user to change password on next login."""
        history = self._model.get_password_history(user_id)
        history_hashes = [h["password_hash"] for h in history]

        self._validator.validate_password_change(
            new_password, history_hashes, PasswordSecurity.verify_password
        )

        self._apply_new_password(user_id, new_password, must_change=True, action="PASSWORD_RESET",
                                  performed_by=reset_by)

    def _apply_new_password(self, user_id: int, new_password: str, must_change: bool,
                             action: str, performed_by: int) -> None:
        bs_today = DateEngine.today_bs()
        new_hash = PasswordSecurity.hash_password(new_password)

        self._model.update_password(user_id, new_hash, ALGO_NAME, must_change)
        self._model.insert_password_history(user_id, new_hash, ALGO_NAME, bs_today)
        self._model.insert_audit(
            user_id=user_id, action=action, performed_by=performed_by,
            old_value=None, new_value=None, remarks=None, action_on_bs=bs_today
        )

    # ---------------- AUTHENTICATION SUPPORT ----------------

    def authenticate(self, username: str, password: str) -> Optional[UserRecord]:
        """
        Single source of truth for username/password verification.
        Authentication module should call this rather than re-implementing
        password checks against the users table.
        Returns the UserRecord on success, or None on failure.
        Does not raise on bad credentials (auth failure is not a validation error).
        """
        user = self._model.get_by_username(username)
        if not user or user.is_deleted or not user.is_active:
            return None
        if not PasswordSecurity.verify_password(password, user.password_hash):
            return None
        return user

    # ---------------- SEARCH / RETRIEVAL ----------------

    def get_user(self, user_id: int) -> Optional[UserRecord]:
        return self._model.get_by_id(user_id)

    def search_users(self, filters: dict, page: int = 1, page_size: int = 50) -> List[UserRecord]:
        offset = (page - 1) * page_size
        return self._model.search(filters, limit=page_size, offset=offset)

    @staticmethod
    def _snapshot(record: UserRecord) -> dict:
        return {
            "username": record.username,
            "display_name": record.display_name,
            "email": record.email,
            "role_id": record.role_id,
            "company_id": record.company_id,
        }
