"""
screens/supplier_manufacturer_discount_form_screen.py

Supplier-Manufacturer Discount Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/supplier_manufacturer_discount_form.ui via
      ui/ui_supplier_manufacturer_discount_form.py
    - Populate the Supplier and Manufacturer combos from the EXISTING
      SupplierEngine.search_suppliers() / ManufacturerEngine.search_manufacturers()
      -- this screen never queries either table itself, and never
      duplicates Supplier/Manufacturer lookup logic
    - Make both combos searchable via utils.combo_helpers.make_searchable,
      same reasoning already used by screens/item_form_screen.py for its
      Category/Sub Category/Manufacturer/Generic combos
    - Populate fields when editing an existing mapping
    - Read fields back out, marshal them via
      utils/supplier_manufacturer_discount_form_helpers.py, and hand the
      payload to SupplierManufacturerDiscountEngine.create_discount /
      update_discount
    - Surface whatever the Engine/Validator decide (defaults, uniqueness,
      allowed values) back to the user -- this screen never decides any of
      that itself
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.manufacturer_engine import ManufacturerEngine
from engines.supplier_engine import SupplierEngine
from engines.supplier_manufacturer_discount_engine import SupplierManufacturerDiscountEngine
from ui.ui_supplier_manufacturer_discount_form import Ui_SupplierManufacturerDiscountFormDialog
from utils.combo_helpers import make_searchable_many
from utils.integration_adapters import get_current_user_id, show_success
from utils.supplier_manufacturer_discount_form_helpers import build_discount_payload
from utils.ui_standards import standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)


class SupplierManufacturerDiscountFormScreen(QDialog):
    """Add/Edit dialog for a single discount mapping. Create mode when discount_id is None."""

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        discount_id: Optional[int] = None,
        engine: Optional[SupplierManufacturerDiscountEngine] = None,
        supplier_engine: Optional[SupplierEngine] = None,
        manufacturer_engine: Optional[ManufacturerEngine] = None,
        initial_supplier_id: Optional[int] = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_SupplierManufacturerDiscountFormDialog()
        self.ui.setupUi(self)
        self._embedded = embedded
        apply_standard_window_chrome(self, width=720, height=560, embedded=embedded)
        standardize_action_buttons(self)

        self._engine = engine or SupplierManufacturerDiscountEngine()
        self._supplier_engine = supplier_engine or SupplierEngine()
        self._manufacturer_engine = manufacturer_engine or ManufacturerEngine()
        self._discount_id = discount_id
        self._is_edit_mode = discount_id is not None
        self._initial_supplier_id = initial_supplier_id

        if self._embedded:
            self._setup_back_button()

        self._connect_signals()
        self._setup_shortcuts()
        self._populate_supplier_combo()
        self._populate_manufacturer_combo()
        make_searchable_many(self.ui.cmbSupplier, self.ui.cmbManufacturer)

        if self._is_edit_mode:
            self.setWindowTitle("Edit Discount Mapping")
            self.ui.lblFormTitle.setText("Edit Discount Mapping")
            self._load_existing_discount()
        else:
            self.setWindowTitle("Add Discount Mapping")
            self.ui.lblFormTitle.setText("Add Discount Mapping")
            if initial_supplier_id is not None:
                index = self.ui.cmbSupplier.findData(initial_supplier_id)
                if index >= 0:
                    self.ui.cmbSupplier.setCurrentIndex(index)
                    self.ui.cmbManufacturer.setFocus()
                else:
                    self.ui.cmbSupplier.setFocus()
            else:
                self.ui.cmbSupplier.setFocus()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnCancel.clicked.connect(self.reject)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        # Escape already closes/rejects a QDialog by default.

    def _setup_back_button(self) -> None:
        """Text-based back button wrapping lblFormTitle in a new header row."""
        root_layout = self.ui.verticalLayoutRoot
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

    def reject(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        super().reject()

    # ------------------------------------------------------------------ #
    # Lookup combo population -- via the EXISTING Supplier/Manufacturer
    # Engines only. This screen never touches their models/tables directly.
    # ------------------------------------------------------------------ #
    def _populate_supplier_combo(self) -> None:
        self.ui.cmbSupplier.clear()
        self.ui.cmbSupplier.addItem("-- Select --", None)
        try:
            rows, _total = self._supplier_engine.search_suppliers(status="Active", page_size=1000)
            for dto in rows:
                self.ui.cmbSupplier.addItem(dto.supplier_name, dto.supplier_id)
        except Exception:  # noqa: BLE001
            logger.exception("SupplierManufacturerDiscountFormScreen: failed to load Supplier list.")
            self.ui.cmbSupplier.setEnabled(False)
            self.ui.cmbSupplier.setToolTip("Could not load Supplier list.")

    def _populate_manufacturer_combo(self) -> None:
        self.ui.cmbManufacturer.clear()
        self.ui.cmbManufacturer.addItem("-- Select --", None)
        try:
            rows, _total = self._manufacturer_engine.search_manufacturers(status="Active", page_size=1000)
            for dto in rows:
                self.ui.cmbManufacturer.addItem(dto.manufacturer_name, dto.manufacturer_id)
        except Exception:  # noqa: BLE001
            logger.exception("SupplierManufacturerDiscountFormScreen: failed to load Manufacturer list.")
            self.ui.cmbManufacturer.setEnabled(False)
            self.ui.cmbManufacturer.setToolTip("Could not load Manufacturer list.")

    @staticmethod
    def _set_combo_by_data(combo, value) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_discount(self) -> None:
        try:
            dto = self._engine.get_discount_record(self._discount_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnSave.setEnabled(False)
            return

        self._set_combo_by_data(self.ui.cmbSupplier, dto.supplier_id)
        self._set_combo_by_data(self.ui.cmbManufacturer, dto.manufacturer_id)
        self.ui.txtDiscountPercent.setText(f"{float(dto.discount_percent or 0):.2f}")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

    def _reset_for_new_mapping(self) -> None:
        """Clear the form for the next entry after a create-mode save (multi-add)."""
        if self._initial_supplier_id is not None:
            self._set_combo_by_data(self.ui.cmbSupplier, self._initial_supplier_id)
        else:
            self.ui.cmbSupplier.setCurrentIndex(0)
        self.ui.cmbManufacturer.setCurrentIndex(0)
        self.ui.txtDiscountPercent.setText("0.00")
        self.ui.txtRemarks.clear()
        self._show_validation_message("")
        self.ui.cmbManufacturer.setFocus()

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "supplier_id": self.ui.cmbSupplier.currentData(),
            "manufacturer_id": self.ui.cmbManufacturer.currentData(),
            "discount_percent_text": self.ui.txtDiscountPercent.text(),
            "remarks": self.ui.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        try:
            payload = build_discount_payload(self._collect_form_values())
        except ValueError as exc:
            self._show_validation_message(str(exc))
            return

        current_user_id = get_current_user_id()

        try:
            if self._is_edit_mode:
                dto = self._engine.update_discount(self._discount_id, payload, current_user_id)
            else:
                dto = self._engine.create_discount(payload, current_user_id)
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
            logger.exception("Unexpected error saving supplier-manufacturer discount.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        action = "updated" if self._is_edit_mode else "created"
        show_success(
            self, "Supplier-Manufacturer Discount",
            f"Discount mapping for '{dto.supplier_name}' / '{dto.manufacturer_name}' {action}.",
        )

        if self._embedded:
            self.saved.emit()
            if self._is_edit_mode:
                self.close_requested.emit()
            else:
                self._reset_for_new_mapping()
            return
        self.accept()

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["SupplierManufacturerDiscountFormScreen"]
