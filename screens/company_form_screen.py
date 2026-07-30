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

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.company_engine import CompanyEngine
from ui.ui_company_form import Ui_CompanyFormDialog
from utils.integration_adapters import get_current_user_id, show_success
from utils.company_form_helpers import build_company_payload

logger = logging.getLogger(__name__)


class CompanyFormScreen(QDialog):
    """Add/Edit dialog for a single company. Create mode when company_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        company_id: Optional[str] = None,
        engine: Optional[CompanyEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_CompanyFormDialog()
        self.ui.setupUi(self)

        self._engine = engine or CompanyEngine()
        self._company_id = company_id
        self._is_edit_mode = company_id is not None

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

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnCancel.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        # Escape already closes/rejects a QDialog by default.

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
        self.ui.cmbStatus.setCurrentText(dto.status or "Active")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

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

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Company Master", f"Company '{dto.company_name}' {action}.")
        self.accept()

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["CompanyFormScreen"]
