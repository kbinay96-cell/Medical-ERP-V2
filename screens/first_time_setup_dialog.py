"""
screens/first_time_setup_dialog.py

First-time setup wizard shown from the Login screen when the
database has no company/user yet. Creates the first company, an
initial financial year, and the first Administrator user in one
step, via engines.bootstrap_engine (bypasses normal permission
checks since there's no session to check against yet).
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from engines.bootstrap_engine import create_first_company_and_admin
from engines.exceptions import ValidationError
from engines.password_manager import check_password_policy
from utils.integration_adapters import show_error
from utils.message import show_info

logger = logging.getLogger(__name__)


class FirstTimeSetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("First-Time Setup")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "No company is set up yet. Fill in the details below to\n"
            "create your first company and administrator account."
        ))

        form = QFormLayout()
        self.input_companyname = QLineEdit(self)
        self.input_financialyear = QLineEdit(self)
        self.input_financialyear.setPlaceholderText("e.g. 2082/2083")
        self.input_startbsdate = QLineEdit(self)
        self.input_startbsdate.setPlaceholderText("YYYY-MM-DD (BS)")
        self.input_endbsdate = QLineEdit(self)
        self.input_endbsdate.setPlaceholderText("YYYY-MM-DD (BS)")
        self.input_admin_username = QLineEdit(self)
        self.input_admin_fullname = QLineEdit(self)
        self.input_admin_password = QLineEdit(self)
        self.input_admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_admin_confirm = QLineEdit(self)
        self.input_admin_confirm.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Company Name*:", self.input_companyname)
        form.addRow("Financial Year*:", self.input_financialyear)
        form.addRow("FY Start (BS)*:", self.input_startbsdate)
        form.addRow("FY End (BS)*:", self.input_endbsdate)
        form.addRow("Admin Username*:", self.input_admin_username)
        form.addRow("Admin Full Name:", self.input_admin_fullname)
        form.addRow("Admin Password*:", self.input_admin_password)
        form.addRow("Confirm Password*:", self.input_admin_confirm)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.btn_create = QPushButton("Create", self)
        self.btn_cancel = QPushButton("Cancel", self)
        button_row.addWidget(self.btn_create)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

        self.btn_create.clicked.connect(self._on_create_clicked)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_create_clicked(self) -> None:
        password = self.input_admin_password.text()
        confirm = self.input_admin_confirm.text()

        if password != confirm:
            show_error(self, "First-Time Setup", "Password and Confirm Password do not match.")
            return

        is_valid, policy_message = check_password_policy(password)
        if not is_valid:
            show_error(self, "First-Time Setup", policy_message)
            return

        try:
            create_first_company_and_admin(
                companyname=self.input_companyname.text().strip(),
                financialyear=self.input_financialyear.text().strip(),
                startbsdate=self.input_startbsdate.text().strip(),
                endbsdate=self.input_endbsdate.text().strip(),
                admin_username=self.input_admin_username.text().strip(),
                admin_password=password,
                admin_fullname=self.input_admin_fullname.text().strip(),
            )
        except ValidationError as exc:
            show_error(self, "First-Time Setup", "; ".join(exc.errors))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("First-time setup failed.")
            show_error(self, "First-Time Setup", f"Setup failed: {exc}")
            return

        show_info(
            f"Company and administrator account '{self.input_admin_username.text().strip()}' "
            "created successfully.\nYou can now log in.",
            "First-Time Setup",
        )
        self.accept()


__all__ = ["FirstTimeSetupDialog"]