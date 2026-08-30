"""
screens/country_tax_form_screen.py

Country Tax Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/country_tax_form.ui via ui/ui_country_tax_form.py
    - Populate fields when editing an existing row
    - Read fields back out, marshal them via utils/country_tax_form_helpers.py
      (pure functions, no business rules), and hand the payload to
      CountryTaxEngine.create_country_tax / update_country_tax
    - Surface whatever the Engine/Validator decide (defaults, uniqueness,
      allowed values) back to the user -- this screen never decides any of
      that itself

Mirrors screens/manufacturer_form_screen.py exactly.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.country_tax_engine import CountryTaxEngine
from engines.manufacturer_engine import ManufacturerEngine
from ui.ui_country_tax_form import Ui_CountryTaxFormDialog
from utils.integration_adapters import get_current_user_id, show_success
from utils.country_tax_form_helpers import build_country_tax_payload
from utils.ui_standards import standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)


class CountryTaxFormScreen(QDialog):
    """Add/Edit dialog for a single country tax row. Create mode when country_tax_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        country_tax_id: Optional[int] = None,
        engine: Optional[CountryTaxEngine] = None,
        manufacturer_engine: Optional[ManufacturerEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_CountryTaxFormDialog()
        self.ui.setupUi(self)
        apply_standard_window_chrome(self, width=720, height=560)
        standardize_action_buttons(self)

        self._engine = engine or CountryTaxEngine()
        self._manufacturer_engine = manufacturer_engine or ManufacturerEngine()
        self._country_tax_id = country_tax_id
        self._is_edit_mode = country_tax_id is not None

        self._connect_signals()
        self._setup_shortcuts()
        self._populate_country_combo()

        if self._is_edit_mode:
            self.setWindowTitle("Edit Country Tax")
            self.ui.lblFormTitle.setText("Edit Country Tax")
            self.ui.btnSave.setVisible(False)
            self.ui.btnUpdate.setVisible(True)
            self._load_existing_country_tax()
        else:
            self.setWindowTitle("Add Country Tax")
            self.ui.lblFormTitle.setText("Add Country Tax")
            self.ui.cmbStatus.setCurrentText("Active")
            self.ui.cmbCountry.setCurrentText("")
            self.ui.cmbCountry.setFocus()

    # ------------------------------------------------------------------ #
    # Country dropdown -- sourced from Manufacturer's distinct countries
    # ------------------------------------------------------------------ #
    def _populate_country_combo(self) -> None:
        """
        Populates cmbCountry from ManufacturerEngine.list_countries() so tax
        rows are defined against real, already-in-use country names. Stays
        editable (see ui/country_tax_form.ui) so a country can still be
        typed manually before any Manufacturer of that country exists --
        this dropdown must never block the form.
        """
        current_text = self.ui.cmbCountry.currentText()
        self.ui.cmbCountry.blockSignals(True)
        self.ui.cmbCountry.clear()
        for country in self._manufacturer_engine.list_countries():
            self.ui.cmbCountry.addItem(country)
        if current_text:
            self.ui.cmbCountry.setCurrentText(current_text)
        else:
            self.ui.cmbCountry.setCurrentIndex(-1)
            self.ui.cmbCountry.clearEditText()
        self.ui.cmbCountry.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnUpdate.clicked.connect(self._on_save_clicked)
        self.ui.btnClear.clicked.connect(self._on_clear_clicked)
        self.ui.btnClose.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        # Escape already closes/rejects a QDialog by default.

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_country_tax(self) -> None:
        try:
            dto = self._engine.get_tax_record(self._country_tax_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnUpdate.setEnabled(False)
            return

        self.ui.cmbCountry.setCurrentText(dto.country or "")
        self.ui.txtVatPercent.setText(f"{float(dto.vat_percent or 0):.2f}")
        self.ui.txtCustomPercent.setText(f"{float(dto.custom_percent or 0):.2f}")
        self.ui.cmbStatus.setCurrentText(dto.status or "Active")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "country": self.ui.cmbCountry.currentText(),
            "vat_percent_text": self.ui.txtVatPercent.text(),
            "custom_percent_text": self.ui.txtCustomPercent.text(),
            "status": self.ui.cmbStatus.currentText(),
            "remarks": self.ui.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        try:
            payload = build_country_tax_payload(self._collect_form_values())
        except ValueError as exc:
            self._show_validation_message(str(exc))
            return

        current_user_id = get_current_user_id()

        try:
            if self._is_edit_mode:
                dto = self._engine.update_tax(self._country_tax_id, payload, current_user_id)
            else:
                dto = self._engine.create_tax(payload, current_user_id)
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
            logger.exception("Unexpected error saving country tax.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Country Tax", f"Country Tax for '{dto.country}' {action}.")
        self.accept()

    def _on_clear_clicked(self) -> None:
        self._show_validation_message("")
        if not self._is_edit_mode:
            self.ui.cmbCountry.setCurrentIndex(-1)
            self.ui.cmbCountry.clearEditText()
        self.ui.txtVatPercent.setText("0.00")
        self.ui.txtCustomPercent.setText("0.00")
        self.ui.cmbStatus.setCurrentText("Active")
        self.ui.txtRemarks.clear()
        self.ui.cmbCountry.setFocus()

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["CountryTaxFormScreen"]
