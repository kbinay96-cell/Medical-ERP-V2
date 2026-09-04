"""
screens/company_form_screen.py

Company Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/company_form.ui via ui/ui_company_form.py
    - Populate fields when editing an existing company
    - Read fields back out, marshal them via utils/company_form_helpers.py
      (pure functions, no business rules), and hand the payload to
      CompanyEngine.create_company / update_company
    - Surface whatever the Engine/Validator decide (defaults, uniqueness,
      allowed values) back to the user -- this screen never decides any of
      that itself
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QPushButton, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.company_engine import CompanyEngine
from engines.settings_engine import get_company_setting, save_company_setting_value
from ui.ui_company_form import Ui_CompanyFormDialog
from utils.integration_adapters import get_current_user_id, show_success
from utils.company_form_helpers import build_company_payload
from utils.ui_standards import standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)


class CompanyFormScreen(QDialog):
    """Add/Edit dialog for a single company. Create mode when company_id is None."""

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        company_id: Optional[str] = None,
        engine: Optional[CompanyEngine] = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_CompanyFormDialog()
        self.ui.setupUi(self)
        self._embedded = embedded
        apply_standard_window_chrome(self, width=780, height=640, embedded=embedded)
        standardize_action_buttons(self)

        self._engine = engine or CompanyEngine()
        self._company_id = company_id
        self._is_edit_mode = company_id is not None

        if self._embedded:
            self._setup_back_button()

        self._connect_signals()
        self._setup_shortcuts()

        if self._is_edit_mode:
            self.setWindowTitle("Edit Company")
            self.ui.lblFormTitle.setText("Edit Company")
            self._load_existing_company()
        else:
            self.setWindowTitle("Add Company")
            self.ui.lblFormTitle.setText("Add Company")
            self.ui.txtCompanyName.setFocus()

    def _setup_back_button(self) -> None:
        """Wrap lblFormTitle in a new header row with a text-based back button on the left —
        matches the existing repo convention ("\u2190 Back" QPushButton), no icon asset needed."""
        root_layout = self.ui.verticalLayout_root
        title_label = self.ui.lblFormTitle
        index = root_layout.indexOf(title_label)
        root_layout.removeWidget(title_label)
        self.btnBack = QPushButton("\u2190 Back", self)
        self.btnBack.setCursor(Qt.PointingHandCursor)
        self.btnBack.setFlat(True)
        self.btnBack.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 4px 8px; }"
            "QPushButton:hover { background: rgba(127,127,127,40); border-radius: 4px; }"
        )
        self.btnBack.clicked.connect(self.reject)
        header_row = QHBoxLayout()
        header_row.addWidget(self.btnBack)
        header_row.addWidget(title_label)
        header_row.addStretch()
        root_layout.insertLayout(index, header_row)

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnCancel.clicked.connect(self.reject)
        self.ui.btnBrowseLogo.clicked.connect(self._on_browse_logo_clicked)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        # Escape already closes/rejects a QDialog by default.

    def reject(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        super().reject()

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_company(self) -> None:
        try:
            dto = self._engine.get_company(self._company_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnSave.setEnabled(False)
            return

        self.ui.txtCompanyCode.setText(dto.company_id or "")
        self.ui.txtCompanyCode.setReadOnly(True)
        self.ui.txtCompanyCode.setToolTip("Company ID cannot be changed after creation.")

        self.ui.txtCompanyName.setText(dto.company_name or "")
        self.ui.txtAddress.setText(dto.address or "")
        self.ui.txtContactPerson.setText(dto.contact_person or "")
        self.ui.txtMobileNo.setText(dto.mobile_no or "")
        self.ui.txtPhoneNo.setText(dto.phone_no or "")
        self.ui.txtEmail.setText(dto.email or "")
        self.ui.txtPanVatNo.setText(dto.pan_vat_no or "")
        self.ui.txtRegistrationNo.setText(dto.registration_no or "")
        self.ui.txtDdaNo.setText(dto.dda_no or "")
        self.ui.txtLogoPath.setText(dto.logo_path or "")
        self.ui.cmbStatus.setCurrentText(dto.status or "Active")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

        self.ui.txtSmtpHost.setText(str(get_company_setting(self._company_id, "smtp.host", "") or ""))
        self.ui.txtSmtpPort.setText(str(get_company_setting(self._company_id, "smtp.port", "587") or "587"))
        self.ui.txtSmtpEmail.setText(str(get_company_setting(self._company_id, "smtp.email", "") or ""))
        self.ui.txtSmtpAppPassword.setText(str(get_company_setting(self._company_id, "smtp.app_password", "") or ""))

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "companyname": self.ui.txtCompanyName.text(),
            "address": self.ui.txtAddress.text(),
            "contactperson": self.ui.txtContactPerson.text(),
            "mobileno": self.ui.txtMobileNo.text(),
            "phone": self.ui.txtPhoneNo.text(),
            "email": self.ui.txtEmail.text(),
            "panno": self.ui.txtPanVatNo.text(),
            "registrationno": self.ui.txtRegistrationNo.text(),
            "ddano": self.ui.txtDdaNo.text(),
            "logopath": self.ui.txtLogoPath.text(),
            "status": self.ui.cmbStatus.currentText(),
            "remarks": self.ui.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        try:
            payload = build_company_payload(self._collect_form_values())
        except ValueError as exc:
            self._show_validation_message(str(exc))
            return

        current_user_id = get_current_user_id()

        try:
            if self._is_edit_mode:
                dto = self._engine.update_company(self._company_id, payload, current_user_id)
            else:
                dto = self._engine.create_company(payload, current_user_id)
        except ValidationError as exc:
            self._show_validation_message("\n".join(exc.errors))
            return
        except DuplicateRecordError as exc:
            self._show_validation_message(str(exc))
            return
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error saving company.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        self._save_smtp_settings(dto.company_id, current_user_id)

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Company Master", f"Company '{dto.company_name}' {action}.")

        if self._embedded:
            self.saved.emit()
            self.close_requested.emit()
            return
        self.accept()

    def _save_smtp_settings(self, company_id: str, current_user_id) -> None:
        """SMTP fields aren't part of CompanyDTO/company table -- they're
        company-scoped Settings entries, saved separately after the
        company record itself is created/updated."""
        smtp_fields = {
            "smtp.host": self.ui.txtSmtpHost.text().strip(),
            "smtp.port": self.ui.txtSmtpPort.text().strip() or "587",
            "smtp.email": self.ui.txtSmtpEmail.text().strip(),
            "smtp.app_password": self.ui.txtSmtpAppPassword.text(),
        }
        for key, value in smtp_fields.items():
            success, message = save_company_setting_value(
                company_id, key, value, str(current_user_id), reason="Company Form save"
            )
            if not success:
                logger.warning(f"Could not save '{key}' for company '{company_id}': {message}")

    def _on_browse_logo_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Company Logo", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.ui.txtLogoPath.setText(file_path)

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["CompanyFormScreen"]
