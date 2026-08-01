"""
screens/reset_password_screen.py

Admin-initiated password reset dialog - Medical ERP V2. Mirrors the
company_form_screen.py pattern (thin UI, no SQL/business logic).
Calls UserEngine.reset_password(), which forces the target user to
change their password on next login.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.user_engine import UserEngine
from ui.ui_reset_password import Ui_ResetPasswordDialog
from utils.integration_adapters import get_current_user_id, show_success

logger = logging.getLogger(__name__)


class ResetPasswordScreen(QDialog):
    """Admin resets another user's password. Always operates on an existing user_id."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        user_id: Optional[int] = None,
        username: str = "",
        engine: Optional[UserEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_ResetPasswordDialog()
        self.ui.setupUi(self)

        self._engine = engine or UserEngine()
        self._user_id = user_id

        self.ui.lbl_target_user.setText(username)
        self.ui.chk_force_change_on_login.setChecked(True)

        self._connect_signals()
        self._setup_shortcuts()
        self.ui.input_new_password.setFocus()

    def _connect_signals(self) -> None:
        self.ui.btn_reset.clicked.connect(self._on_reset_clicked)
        self.ui.btn_cancel.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_reset_clicked)

    def _on_reset_clicked(self) -> None:
        self.ui.lbl_validation_message.setText("")

        if self._user_id is None:
            self.ui.lbl_validation_message.setText("No user selected.")
            return

        new_password = self.ui.input_new_password.text()
        confirm_password = self.ui.input_confirm_password.text()

        if new_password != confirm_password:
            self.ui.lbl_validation_message.setText("New Password and Confirm Password do not match.")
            return

        try:
            self._engine.reset_password(
                self._user_id, new_password, reset_by=get_current_user_id()
            )
        except ValidationError as exc:
            self.ui.lbl_validation_message.setText("; ".join(exc.errors))
            return
        except RecordNotFoundError as exc:
            self.ui.lbl_validation_message.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to reset password for user %s.", self._user_id)
            self.ui.lbl_validation_message.setText(f"Failed to reset password: {exc}")
            return

        show_success(self, "User Master", "Password reset successfully.")
        self.accept()


__all__ = ["ResetPasswordScreen"]
