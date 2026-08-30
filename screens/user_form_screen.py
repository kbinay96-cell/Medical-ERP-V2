"""
screens/user_form_screen.py

User Add/Edit Form Screen - Medical ERP V2. Mirrors company_form_screen.py.
UI-only: loads ui/ui_user_form.py, reads/writes fields, hands the payload
to UserEngine.create_user / update_user. No SQL, no business logic here.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QLabel, QWidget

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.user_engine import UserEngine
from models import company_model, role_model
from ui.ui_user_form import Ui_UserFormView
from utils.integration_adapters import get_current_user_id, show_error, show_success
from utils.password_field_helper import attach_show_password_toggle
from utils.ui_standards import standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome
from widgets.photo_picker import host_photo_beside_scroll

logger = logging.getLogger(__name__)


class UserFormScreen(QDialog):
    """Add/Edit dialog for a single user. Create mode when user_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        user_id: Optional[int] = None,
        engine: Optional[UserEngine] = None,
        current_user_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_UserFormView()
        self.ui.setupUi(self)
        apply_standard_window_chrome(self, width=780, height=680)
        self._photo_picker = host_photo_beside_scroll(self.ui.verticalLayout_root, self.ui.scroll_area)
        standardize_action_buttons(self)

        self._engine = engine or UserEngine()
        self._user_id = user_id
        self._current_user_id = current_user_id
        self._is_edit_mode = user_id is not None

        self._engine = engine or UserEngine()
        self._user_id = user_id
        self._is_edit_mode = user_id is not None

        self._load_roles()
        self._load_companies()
        attach_show_password_toggle(self.ui.input_password)
        attach_show_password_toggle(self.ui.input_confirm_password)
        from PySide6.QtWidgets import QLabel  # ensure this import exists at top of file

        password_rule_hint = "Min 8 characters: uppercase, lowercase, digit & special character."
        self.ui.lbl_password_hint = QLabel(password_rule_hint)
        self.ui.lbl_password_hint.setStyleSheet("color: #666666; font-size: 11px;")
        self.ui.lbl_password_hint.setWordWrap(True)
        self.ui.gridLayout_password.addWidget(self.ui.lbl_password_hint, 2, 0, 1, 2)
        self._connect_signals()
        self._setup_shortcuts()

        if self._is_edit_mode:
            self.setWindowTitle("Edit User")
            self.ui.lbl_form_title.setText("Edit User")
            self._load_existing_user()
        else:
            self.setWindowTitle("Add User")
            self.ui.lbl_form_title.setText("Add User")
            self.ui.chk_is_active.setChecked(True)
            self.ui.chk_must_change_password.setChecked(True)
            self.ui.input_username.setFocus()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btn_save.clicked.connect(self._on_save_clicked)
        self.ui.btn_cancel.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)

    def _show_validation_message(self, message: str) -> None:
        if message:
            show_error(self, "User Master", message)

    def _clear_validation_message(self) -> None:
        self._show_validation_message("")

    def _load_roles(self) -> None:
        self.ui.combo_role.clear()
        try:
            for role in role_model.list_roles():
                self.ui.combo_role.addItem(role["rolename"], role["roleid"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load roles for User form.")
            self._show_validation_message(f"Could not load roles: {exc}")

    def _load_companies(self) -> None:
        self.ui.combo_company.clear()
        self.ui.combo_company.addItem("-- None --", None)
        try:
            for company in company_model.list_companies(status_filter="all"):
                self.ui.combo_company.addItem(company["companyname"], company["companyid"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load companies for User form.")
            self._show_validation_message(f"Could not load companies: {exc}")

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_user(self) -> None:
        try:
            dto = self._engine.get_user(self._user_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            return

        self.ui.input_username.setText(dto.username)
        self.ui.input_username.setEnabled(True)
        self.ui.input_username.setToolTip(
            "Changing the username changes this user's login ID immediately after Save."
        )
        self.ui.input_display_name.setText(dto.fullname)
        self.ui.input_email.setText(dto.email or "")
        self.ui.input_phone.setText(dto.phone or "")
        self.ui.chk_is_active.setChecked(dto.is_active)
        self.ui.chk_must_change_password.setChecked(dto.must_change_password)

        role_index = self.ui.combo_role.findData(dto.role_id)
        if role_index >= 0:
            self.ui.combo_role.setCurrentIndex(role_index)

        company_index = self.ui.combo_company.findData(dto.company_id)
        if company_index >= 0:
            self.ui.combo_company.setCurrentIndex(company_index)

        # Password fields stay blank on edit - only filled in to actually change
        # the password (which this form does not do; use Reset Password instead).
        self.ui.input_password.setEnabled(False)
        self.ui.input_confirm_password.setEnabled(False)
        self.ui.input_password.setPlaceholderText("Use 'Reset Password' to change")
        self._photo_picker.load_existing(getattr(dto, "photo_path", None))

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _on_save_clicked(self) -> None:
        self._clear_validation_message()

        data = {
            "username": self.ui.input_username.text().strip(),
            "fullname": self.ui.input_display_name.text().strip(),
            "email": self.ui.input_email.text().strip() or None,
            "phone": self.ui.input_phone.text().strip() or None,
            "role_id": self.ui.combo_role.currentData(),
            "company_id": self.ui.combo_company.currentData(),
            "must_change_password": self.ui.chk_must_change_password.isChecked(),
        }

        if not self._is_edit_mode:
            password = self.ui.input_password.text()
            confirm_password = self.ui.input_confirm_password.text()
            if password != confirm_password:
                self._show_validation_message("Password and Confirm Password do not match.")
                return
            data["password"] = password

        data.update(self._photo_picker.get_photo_update())

        try:
            if self._is_edit_mode:
                dto = self._engine.update_user(self._user_id, data, current_user_id=self._current_user_id)
                if dto.is_active != self.ui.chk_is_active.isChecked():
                    dto = self._engine.set_active_status(
                        self._user_id, self.ui.chk_is_active.isChecked(), current_user_id=self._current_user_id
                    )
                show_success(self, "User Master", f"User '{dto.username}' updated.")
            else:
                dto = self._engine.create_user(data, current_user_id=self._current_user_id)
                show_success(self, "User Master", f"User '{dto.username}' created.")
        except ValidationError as exc:
            self._show_validation_message("; ".join(exc.errors))
            return
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to save user.")
            self._show_validation_message(f"Failed to save user: {exc}")
            return

        self.accept()


__all__ = ["UserFormScreen"]
