"""
screens/supplier_form_screen.py

Supplier Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/supplier_form.ui via ui/ui_supplier_form.py
    - Populate fields when editing an existing supplier
    - Read fields back out, marshal them via utils/supplier_form_helpers.py
      (pure functions, no business rules), and hand the payload to
      SupplierEngine.create_supplier / update_supplier
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
from engines.supplier_engine import SupplierEngine
from ui.ui_supplier_form import Ui_SupplierFormDialog
from utils.integration_adapters import get_current_user_id, show_success
from utils.supplier_form_helpers import build_supplier_payload

logger = logging.getLogger(__name__)


class SupplierFormScreen(QDialog):
    """Add/Edit dialog for a single supplier. Create mode when supplier_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        supplier_id: Optional[int] = None,
        engine: Optional[SupplierEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_SupplierFormDialog()
        self.ui.setupUi(self)

        self._engine = engine or SupplierEngine()
        self._supplier_id = supplier_id
        self._is_edit_mode = supplier_id is not None

        self._connect_signals()
        self._setup_shortcuts()

        if self._is_edit_mode:
            self.setWindowTitle("Edit Supplier")
            self.ui.lblFormTitle.setText("Edit Supplier")
            self._load_existing_supplier()
        else:
            self.setWindowTitle("Add Supplier")
            self.ui.lblFormTitle.setText("Add Supplier")
            self.ui.txtSupplierName.setFocus()

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
    def _load_existing_supplier(self) -> None:
        try:
            dto = self._engine.get_supplier(self._supplier_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnSave.setEnabled(False)
            return

        self.ui.txtSupplierCode.setText(dto.supplier_code or "")
        self.ui.txtSupplierCode.setReadOnly(True)
        self.ui.txtSupplierCode.setToolTip("Supplier Code cannot be changed after creation.")

        self.ui.txtSupplierName.setText(dto.supplier_name or "")
        self.ui.txtContactPerson.setText(dto.contact_person or "")
        self.ui.txtMobileNo.setText(dto.mobile_no or "")
        self.ui.txtPhoneNo.setText(dto.phone_no or "")
        self.ui.txtEmail.setText(dto.email or "")
        self.ui.txtAddress.setText(dto.address or "")
        self.ui.txtCity.setText(dto.city or "")
        self.ui.txtPanVatNo.setText(dto.pan_vat_no or "")
        self.ui.txtOpeningBalance.setText(f"{float(dto.opening_balance or 0):.2f}")
        self.ui.cmbBalanceType.setCurrentText(dto.balance_type or "Dr")
        self.ui.txtCreditLimit.setText(f"{float(dto.credit_limit or 0):.2f}")
        self.ui.txtCreditDays.setText(str(dto.credit_days or 0))
        self.ui.cmbStatus.setCurrentText(dto.status or "Active")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "supplier_code": self.ui.txtSupplierCode.text(),
            "supplier_name": self.ui.txtSupplierName.text(),
            "contact_person": self.ui.txtContactPerson.text(),
            "mobile_no": self.ui.txtMobileNo.text(),
            "phone_no": self.ui.txtPhoneNo.text(),
            "email": self.ui.txtEmail.text(),
            "address": self.ui.txtAddress.text(),
            "city": self.ui.txtCity.text(),
            "pan_vat_no": self.ui.txtPanVatNo.text(),
            "opening_balance_text": self.ui.txtOpeningBalance.text(),
            "balance_type": self.ui.cmbBalanceType.currentText(),
            "credit_limit_text": self.ui.txtCreditLimit.text(),
            "credit_days_text": self.ui.txtCreditDays.text(),
            "status": self.ui.cmbStatus.currentText(),
            "remarks": self.ui.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        try:
            payload = build_supplier_payload(self._collect_form_values())
        except ValueError as exc:
            self._show_validation_message(str(exc))
            return

        current_user_id = get_current_user_id()

        try:
            if self._is_edit_mode:
                dto = self._engine.update_supplier(self._supplier_id, payload, current_user_id)
            else:
                dto = self._engine.create_supplier(payload, current_user_id)
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
            logger.exception("Unexpected error saving supplier.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Supplier Master", f"Supplier '{dto.supplier_name}' {action}.")
        self.accept()

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["SupplierFormScreen"]
