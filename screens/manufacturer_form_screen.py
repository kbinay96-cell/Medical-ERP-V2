"""
screens/manufacturer_form_screen.py

Manufacturer Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- project rule "No SQL. No business
logic."):
    - Load ui/manufacturer_form.ui via ui/ui_manufacturer_form.py
    - Populate fields when editing an existing manufacturer
    - Live-preview the auto-generated Short Name as the user types the
      Manufacturer Name (calling the Engine's preview_short_name(), never
      computing it itself)
    - Read fields back out, marshal them via utils/manufacturer_form_helpers.py,
      and hand the payload to ManufacturerEngine.create_manufacturer /
      update_manufacturer
    - Surface whatever the Engine/Validator decide back to the user -- this
      screen never decides any of that itself
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.manufacturer_engine import ManufacturerEngine
from ui.ui_manufacturer_form import Ui_ManufacturerFormDialog
from utils.integration_adapters import get_current_user_id, show_success
from utils.manufacturer_form_helpers import build_manufacturer_payload

logger = logging.getLogger(__name__)

SHORT_NAME_PREVIEW_DEBOUNCE_MS = 250


class ManufacturerFormScreen(QDialog):
    """Add/Edit dialog for a single manufacturer. Create mode when manufacturer_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        manufacturer_id: Optional[int] = None,
        engine: Optional[ManufacturerEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_ManufacturerFormDialog()
        self.ui.setupUi(self)

        self._engine = engine or ManufacturerEngine()
        self._manufacturer_id = manufacturer_id
        self._is_edit_mode = manufacturer_id is not None

        self._connect_signals()
        self._setup_shortcuts()

        if self._is_edit_mode:
            self.setWindowTitle("Edit Manufacturer")
            self.ui.lblFormTitle.setText("Edit Manufacturer")
            self.ui.btnSave.setVisible(False)
            self.ui.btnUpdate.setVisible(True)
            self._load_existing_manufacturer()
        else:
            self.setWindowTitle("Add Manufacturer")
            self.ui.lblFormTitle.setText("Add Manufacturer")
            self.ui.cmbStatus.setCurrentText("Active")
            self.ui.txtManufacturerName.setFocus()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnUpdate.clicked.connect(self._on_save_clicked)
        self.ui.btnClear.clicked.connect(self._on_clear_clicked)
        self.ui.btnClose.clicked.connect(self.reject)
        self.ui.txtManufacturerName.textChanged.connect(self._on_name_changed)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        # Escape already closes/rejects a QDialog by default.

    # ------------------------------------------------------------------ #
    # Live Short Name preview (Engine-computed, screen only displays it)
    # ------------------------------------------------------------------ #
    def _on_name_changed(self, text: str) -> None:
        try:
            preview = self._engine.preview_short_name(text, exclude_id=self._manufacturer_id)
        except Exception:  # noqa: BLE001 - preview must never block typing
            logger.debug("Short Name preview failed for '%s'.", text, exc_info=True)
            preview = ""
        self.ui.txtManufacturerShortName.setText(preview)

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_manufacturer(self) -> None:
        try:
            dto = self._engine.get_manufacturer(self._manufacturer_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnUpdate.setEnabled(False)
            return

        self.ui.txtManufacturerCode.setText(dto.manufacturer_code or "")
        self.ui.txtManufacturerCode.setReadOnly(True)
        self.ui.txtManufacturerCode.setToolTip("Manufacturer Code cannot be changed after creation.")

        self.ui.txtManufacturerName.setText(dto.manufacturer_name or "")
        self.ui.txtManufacturerShortName.setText(dto.manufacturer_short_name or "")
        self.ui.txtCountry.setText(dto.country or "")
        self.ui.cmbStatus.setCurrentText(dto.status or "Active")

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "manufacturer_code": self.ui.txtManufacturerCode.text(),
            "manufacturer_name": self.ui.txtManufacturerName.text(),
            "country": self.ui.txtCountry.text(),
            "status": self.ui.cmbStatus.currentText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        payload = build_manufacturer_payload(self._collect_form_values())
        current_user_id = get_current_user_id()

        try:
            if self._is_edit_mode:
                dto = self._engine.update_manufacturer(self._manufacturer_id, payload, current_user_id)
            else:
                dto = self._engine.create_manufacturer(payload, current_user_id)
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
            logger.exception("Unexpected error saving manufacturer.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Manufacturer Master", f"Manufacturer '{dto.manufacturer_name}' {action}.")
        self.accept()

    def _on_clear_clicked(self) -> None:
        self._show_validation_message("")
        if not self._is_edit_mode:
            self.ui.txtManufacturerCode.clear()
        self.ui.txtManufacturerName.clear()
        self.ui.txtManufacturerShortName.clear()
        self.ui.txtCountry.clear()
        self.ui.cmbStatus.setCurrentText("Active")
        self.ui.txtManufacturerName.setFocus()

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["ManufacturerFormScreen"]
