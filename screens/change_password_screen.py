"""
screens/change_password_screen.py

Self-service "Change My Password" dialog - Medical ERP V2. The logged-in
user changes their own password, knowing the current one. Calls
UserEngine.change_password(). Opened from the Dashboard (user menu),
not from the User Master list.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.user_engine import UserEngine
from ui.ui_change_password import Ui_ChangePasswordDialog
from utils.integration_adapters import show_error, show_success
from utils.password_field_helper import attach_show_password_toggle

logger = logging.getLogger(__name__)


class ChangePasswordScreen(QDialog):
    """Logged-in user changes their own password."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        user_id: Optional[int] = None,
        engine: Optional[UserEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_ChangePasswordDialog()
        self.ui.setupUi(self)

        self._engine = engine or UserEngine()
        self._user_id = user_id

        self._connect_signals()
        self._setup_shortcuts()
        attach_show_password_toggle(self.ui.input_old_password)
        attach_show_password_toggle(self.ui.input_new_password)
        attach_show_password_toggle(self.ui.input_confirm_password)
        password_rule_hint = "Min 8 characters, with uppercase, lowercase, digit & special character."
        self.ui.input_new_password.setToolTip(password_rule_hint)
        self.ui.input_new_password.setPlaceholderText(password_rule_hint)
        self.ui.input_old_password.setFocus()

    def _connect_signals(self) -> None:
        self.ui.btn_change.clicked.connect(self._on_change_clicked)
        self.ui.btn_cancel.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_change_clicked)

    def _show_validation_message(self, message: str) -> None:
        if message:
            show_error(self, "User Master", message)

    def _on_change_clicked(self) -> None:
        self._show_validation_message("")

        if self._user_id is None:
            self._show_validation_message("No logged-in user context.")
            return

        old_password = self.ui.input_old_password.text()
        new_password = self.ui.input_new_password.text()
        confirm_password = self.ui.input_confirm_password.text()

        if new_password != confirm_password:
            self._show_validation_message("New Password and Confirm Password do not match.")
            return

        try:
            self._engine.change_password(self._user_id, old_password, new_password)
        except ValidationError as exc:
            self._show_validation_message("; ".join(exc.errors))
            return
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to change password for user %s.", self._user_id)
            self._show_validation_message(f"Failed to change password: {exc}")
            return

        show_success(self, "Change Password", "Password changed successfully.")
        self.accept()


__all__ = ["ChangePasswordScreen"]
