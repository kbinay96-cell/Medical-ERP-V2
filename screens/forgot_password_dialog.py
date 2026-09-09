"""
screens/forgot_password_dialog.py

Forgot-password entry point from the login screen. User enters
their username; a 6-digit request code is generated and a
prefilled WhatsApp deep-link opens so they can send it to the
admin from their own phone for manual verification+approval.
"""

from __future__ import annotations

import logging
import webbrowser
from urllib.parse import quote

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.password_reset_engine import request_reset
from engines.settings_engine import get_setting
from utils.integration_adapters import show_error
from utils.message import show_info

logger = logging.getLogger(__name__)


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Forgot Password")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Enter your username. We'll generate a request code\n"
            "you can send to the administrator on WhatsApp."
        ))

        self.input_username = QLineEdit(self)
        self.input_username.setPlaceholderText("Username")
        layout.addWidget(self.input_username)

        button_row = QHBoxLayout()
        self.btn_submit = QPushButton("Request Reset", self)
        self.btn_cancel = QPushButton("Cancel", self)
        button_row.addWidget(self.btn_submit)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

        self.btn_submit.clicked.connect(self._on_submit)
        self.btn_cancel.clicked.connect(self.reject)
        self.input_username.setFocus()

    def _on_submit(self) -> None:
        username = self.input_username.text().strip()
        if not username:
            show_error(self, "Forgot Password", "Please enter your username.")
            return

        try:
            _, code, expiry_minutes = request_reset(username)
        except RecordNotFoundError as exc:
            show_error(self, "Forgot Password", str(exc))
            return
        except ValidationError as exc:
            show_error(self, "Forgot Password", "; ".join(exc.errors))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to create password reset request for %s.", username)
            show_error(self, "Forgot Password", f"Failed to create request: {exc}")
            return

        admin_number = (get_setting("admin.whatsapp_number", "") or "").strip()
        message = f"Password reset request - Username: {username}, Code: {code}"

        if admin_number:
            digits_only = "".join(ch for ch in admin_number if ch.isdigit())
            webbrowser.open(f"whatsapp://send?phone={digits_only}&text={quote(message)}")
            show_info(
                f"Your request code is {code} (valid {expiry_minutes} minutes).\n"
                "WhatsApp has been opened with this message pre-filled — "
                "please send it to the administrator from your own phone.",
                "Forgot Password",
            )
        else:
            show_info(
                f"Your request code is {code} (valid {expiry_minutes} minutes).\n"
                "Please send this code and your username to the administrator "
                "on WhatsApp yourself (admin WhatsApp number isn't configured yet).",
                "Forgot Password",
            )

        self.accept()


__all__ = ["ForgotPasswordDialog"]