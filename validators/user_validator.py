"""
User Validator
Layer: Validator
Responsibility: Field-level and business-rule validation for User Master.
Raises ValidationError. Never touches SQL directly except read-only
uniqueness checks delegated to UserModel.
"""

import re
from typing import Optional, List
from models.user_model import UserModel


class ValidationError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.]{4,50}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8


class UserValidator:

    def __init__(self, user_model: UserModel):
        self._model = user_model

    def validate_create(self, data: dict) -> None:
        errors = []
        errors += self._validate_username(data.get("username"))
        errors += self._validate_display_name(data.get("display_name"))
        errors += self._validate_email(data.get("email"))
        errors += self._validate_password_strength(data.get("password"))

        if self._model.exists_username(data.get("username", "")):
            errors.append("Username already exists.")

        if errors:
            raise ValidationError(errors)

    def validate_update(self, user_id: int, data: dict) -> None:
        errors = []
        if "username" in data:
            errors += self._validate_username(data["username"])
            if self._model.exists_username(data["username"], exclude_user_id=user_id):
                errors.append("Username already exists.")
        if "display_name" in data:
            errors += self._validate_display_name(data["display_name"])
        if "email" in data:
            errors += self._validate_email(data["email"])

        if errors:
            raise ValidationError(errors)

    def validate_password_change(self, new_password: str, history_hashes: List[str],
                                   hash_check_fn) -> None:
        errors = self._validate_password_strength(new_password)
        for old_hash in history_hashes:
            if hash_check_fn(new_password, old_hash):
                errors.append("Password matches a previously used password. Choose a different one.")
                break
        if errors:
            raise ValidationError(errors)

    # ---- Field-level rules ----

    @staticmethod
    def _validate_username(username: Optional[str]) -> List[str]:
        errs = []
        if not username:
            errs.append("Username is required.")
        elif not USERNAME_PATTERN.match(username):
            errs.append("Username must be 4-50 characters: letters, numbers, dot, underscore only.")
        return errs

    @staticmethod
    def _validate_display_name(name: Optional[str]) -> List[str]:
        if not name or not name.strip():
            return ["Display name is required."]
        if len(name) > 150:
            return ["Display name exceeds maximum length."]
        return []

    @staticmethod
    def _validate_email(email: Optional[str]) -> List[str]:
        if email and not EMAIL_PATTERN.match(email):
            return ["Email format is invalid."]
        return []

    @staticmethod
    def _validate_password_strength(password: Optional[str]) -> List[str]:
        errs = []
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
