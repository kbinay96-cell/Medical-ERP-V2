"""
screens/item_form_screen.py

Item Add/Edit Form Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/item_form.ui via ui/ui_item_form.py
    - Populate fields when editing an existing item
    - Populate + wire all six lookup combos (Category, Sub Category, Item
      Type, Manufacturer, Generic, Unit/Purchase Unit) via
      engines/item_lookup_registry.py -- never a direct import of
      engines/simple_master_engine.py or Manufacturer's module
    - Apply searchable (type-ahead) filtering to the long-list combos
      (Category, Sub Category, Manufacturer, Generic) via
      utils/combo_helpers.make_searchable_many -- Item Type/Unit are
      short, fixed lists and stay plain
    - Attach a "Manage..." button to every one of the six combos via
      utils/combo_helpers.attach_manage_button, opening
      screens/master_manage_screen.MasterManageDialog
    - Read fields back out, marshal them via utils/item_form_helpers.py,
      hand the payload to ItemEngine.create_item / update_item
    - Offer "Add Batch" (screens/item_batch_dialog.ItemBatchDialog) for
      Opening Stock entry -- optional; an item can be saved with 0 batches
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QWidget

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.item_engine import ItemEngine
from engines.item_lookup_registry import (
    category_engine,
    generic_engine,
    item_group_engine,
    manufacturer_engine,
    sub_category_engine,
    unit_engine,
)
from screens.item_batch_dialog import ItemBatchDialog
from screens.master_manage_screen import MasterManageDialog
from ui.ui_item_form import Ui_ItemFormDialog
from utils.combo_helpers import attach_manage_button, make_searchable_many
from utils.integration_adapters import get_current_user_id, show_error, show_success
from utils.item_form_helpers import build_item_payload, combo_id_value, format_qty

logger = logging.getLogger(__name__)


class ItemFormScreen(QDialog):
    """Add/Edit dialog for a single item. Create mode when item_id is None."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        item_id: Optional[int] = None,
        engine: Optional[ItemEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_ItemFormDialog()
        self.ui.setupUi(self)
        self._fit_to_screen()

        self._engine = engine or ItemEngine(
            manufacturer_lookup_fn=self._safe_manufacturer_lookup,
        )
        self._item_id = item_id
        self._is_edit_mode = item_id is not None
        self._current_user_id = get_current_user_id()

        self._connect_signals()
        self._setup_shortcuts()
        self._populate_static_lookup_combos()
        self._wire_manage_buttons()
        make_searchable_many(
            self.ui.cmbCategory, self.ui.cmbSubCategory,
            self.ui.cmbManufacturer, self.ui.cmbGeneric,
        )

        if self._is_edit_mode:
            self.setWindowTitle("Edit Item")
            self.ui.lblFormTitle.setText("Edit Item")
            self._set_opening_stock_fields_visible(False)
            self._load_existing_item()
        else:
            self.setWindowTitle("Add Item")
            self.ui.lblFormTitle.setText("Add Item")
            self.ui.txtItemName.setFocus()
            self._set_opening_stock_fields_visible(True)
            self.ui.btnAddBatch.setEnabled(False)
            self.ui.btnAddBatch.setToolTip("Save the item first, then use Add Batch for any further stock.")
            from PySide6.QtCore import QDate
            self.ui.txtOpeningExpiryYear.setText(str(QDate.currentDate().year() + 1))

    def _set_opening_stock_fields_visible(self, visible: bool) -> None:
        """
        Opening Quantity/Expiry only make sense while CREATING an item --
        they create the item's first batch in the same save click. In
        Edit mode, "Add Batch" is the way to add further stock instead
        (Purchase will use the same mechanism later).
        """
        self.ui.lblOpeningQty.setVisible(visible)
        self.ui.txtOpeningQty.setVisible(visible)
        self.ui.lblOpeningExpiry.setVisible(visible)
        self.ui.cmbOpeningExpiryMonth.setVisible(visible)
        self.ui.txtOpeningExpiryYear.setVisible(visible)
        self.ui.lblOpeningExpiryHint.setVisible(visible)

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _fit_to_screen(self) -> None:
        """
        The form's default height (760px) can exceed a laptop's available
        screen height (taskbar + title bar included), pushing Save/Cancel
        off-screen with no way to reach them. Clamp to 90% of the current
        screen's available height and re-center, so the button row always
        stays visible regardless of monitor resolution.
        """
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        max_height = int(available.height() * 0.9)
        if self.height() > max_height:
            self.resize(self.width(), max_height)
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _connect_signals(self) -> None:
        self.ui.btnSave.clicked.connect(self._on_save_clicked)
        self.ui.btnCancel.clicked.connect(self.reject)
        self.ui.radioCountryDefault.toggled.connect(self._on_tax_mode_toggled)
        self.ui.chkVat.toggled.connect(self.ui.txtVatPercent.setEnabled)
        self.ui.chkCustom.toggled.connect(self.ui.txtCustomPercent.setEnabled)
        self.ui.cmbCategory.currentIndexChanged.connect(self._on_category_changed)
        self.ui.btnAddBatch.clicked.connect(self._on_add_batch_clicked)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)

    def _safe_manufacturer_lookup(self, manufacturer_id):
        from engines.item_lookup_registry import manufacturer_lookup
        return manufacturer_lookup(manufacturer_id)

    # ------------------------------------------------------------------ #
    # Lookup combo population
    # ------------------------------------------------------------------ #
    def _populate_static_lookup_combos(self) -> None:
        self.ui.cmbCategory.blockSignals(True)
        self.ui.cmbCategory.clear()
        self.ui.cmbCategory.addItem("-- Select --", None)
        for dto in category_engine().list_active():
            self.ui.cmbCategory.addItem(dto.name, dto.id)
        self.ui.cmbCategory.blockSignals(False)

        self.ui.cmbItemGroup.clear()
        self.ui.cmbItemGroup.addItem("-- Select --", None)
        for dto in item_group_engine().list_active():
            self.ui.cmbItemGroup.addItem(dto.name, dto.id)

        self.ui.cmbGeneric.clear()
        self.ui.cmbGeneric.addItem("-- Select --", None)
        for dto in generic_engine().list_active():
            self.ui.cmbGeneric.addItem(dto.name, dto.id)

        self.ui.cmbUnit.clear()
        self.ui.cmbPurchaseUnit.clear()
        self.ui.cmbPurchaseUnit.addItem("-- Same as Unit --", None)
        for dto in unit_engine().list_active():
            self.ui.cmbUnit.addItem(dto.name, dto.id)
            self.ui.cmbPurchaseUnit.addItem(dto.name, dto.id)

        self._populate_manufacturer_combo()
        self._refresh_sub_category_combo(combo_id_value(self.ui.cmbCategory.currentData()))

    def _populate_manufacturer_combo(self) -> None:
        self.ui.cmbManufacturer.clear()
        self.ui.cmbManufacturer.addItem("-- Select --", None)
        try:
            rows, _total = manufacturer_engine().search_manufacturers(status="Active", page_size=1000)
            for dto in rows:
                self.ui.cmbManufacturer.addItem(dto.manufacturer_name, dto.manufacturer_id)
        except Exception:  # noqa: BLE001
            logger.exception("ItemFormScreen: failed to load Manufacturer list.")
            self.ui.cmbManufacturer.setEnabled(False)
            self.ui.cmbManufacturer.setToolTip("Could not load Manufacturer list.")

    def _refresh_sub_category_combo(self, category_id: Optional[int]) -> None:
        self.ui.cmbSubCategory.blockSignals(True)
        self.ui.cmbSubCategory.clear()
        self.ui.cmbSubCategory.addItem("-- Select --", None)
        if category_id is not None:
            all_sub = sub_category_engine().search(search_text=None, include_deleted=False)
            for dto in all_sub:
                if dto.extra.get("category_id") == category_id and dto.status == "Active":
                    self.ui.cmbSubCategory.addItem(dto.name, dto.id)
        self.ui.cmbSubCategory.setEnabled(category_id is not None)
        self.ui.cmbSubCategory.blockSignals(False)

    def _on_category_changed(self, _index: int) -> None:
        self._refresh_sub_category_combo(combo_id_value(self.ui.cmbCategory.currentData()))

    # ------------------------------------------------------------------ #
    # Manage... buttons (all six combos)
    # ------------------------------------------------------------------ #
    def _wire_manage_buttons(self) -> None:
        attach_manage_button(
            self.ui.formLayoutClassification, self.ui.cmbCategory,
            lambda: self._open_manage_dialog(category_engine(), "Category", self._populate_static_lookup_combos),
        )
        attach_manage_button(
            self.ui.formLayoutClassification, self.ui.cmbSubCategory,
            lambda: self._open_manage_dialog(
                sub_category_engine(), "Sub Category", self._populate_static_lookup_combos,
                scope_engine=category_engine(), scope_label="Category",
            ),
        )
        attach_manage_button(
            self.ui.formLayoutClassification, self.ui.cmbItemGroup,
            lambda: self._open_manage_dialog(item_group_engine(), "Item Type", self._populate_static_lookup_combos),
        )
        attach_manage_button(
            self.ui.formLayoutClassification, self.ui.cmbManufacturer,
            lambda: self._open_manufacturer_manage_dialog(),
        )
        attach_manage_button(
            self.ui.formLayoutClassification, self.ui.cmbGeneric,
            lambda: self._open_manage_dialog(generic_engine(), "Generic", self._populate_static_lookup_combos),
        )
        attach_manage_button(
            self.ui.formLayoutUnits, self.ui.cmbUnit,
            lambda: self._open_manage_dialog(unit_engine(), "Unit", self._populate_static_lookup_combos),
        )

    def _open_manage_dialog(self, engine, label, refresh_fn, scope_engine=None, scope_label=None) -> None:
        snapshot = self._snapshot_combo_selections()
        dialog = MasterManageDialog(
            self, engine, label, self._current_user_id,
            scope_engine=scope_engine, scope_label=scope_label,
        )
        dialog.exec()
        refresh_fn()
        self._restore_combo_selections(snapshot)

    def _snapshot_combo_selections(self) -> dict:
        """Captures the currently selected id of every classification/unit
        combo so a Manage-dialog-triggered refresh() can restore them --
        refresh_fn() rebuilds ALL combos together (not just the one whose
        Manage button was clicked), so every combo's selection needs
        saving, not just one."""
        return {
            "category_id": combo_id_value(self.ui.cmbCategory.currentData()),
            "sub_category_id": combo_id_value(self.ui.cmbSubCategory.currentData()),
            "item_group_id": combo_id_value(self.ui.cmbItemGroup.currentData()),
            "generic_id": combo_id_value(self.ui.cmbGeneric.currentData()),
            "unit_id": combo_id_value(self.ui.cmbUnit.currentData()),
            "purchase_unit_id": combo_id_value(self.ui.cmbPurchaseUnit.currentData()),
        }

    def _restore_combo_selections(self, snapshot: dict) -> None:
        self._set_combo_by_data(self.ui.cmbCategory, snapshot["category_id"])
        # Sub Category's own list depends on Category, so rebuild it for the
        # restored Category before trying to re-select the Sub Category itself.
        self._refresh_sub_category_combo(snapshot["category_id"])
        self._set_combo_by_data(self.ui.cmbSubCategory, snapshot["sub_category_id"])
        self._set_combo_by_data(self.ui.cmbItemGroup, snapshot["item_group_id"])
        self._set_combo_by_data(self.ui.cmbGeneric, snapshot["generic_id"])
        self._set_combo_by_data(self.ui.cmbUnit, snapshot["unit_id"])
        self._set_combo_by_data(self.ui.cmbPurchaseUnit, snapshot["purchase_unit_id"])

    def _open_manufacturer_manage_dialog(self) -> None:
        # ManufacturerEngine's API shape (search_manufacturers/get_manufacturer/
        # ManufacturerDTO.manufacturer_name) does NOT match what
        # MasterManageDialog expects (SimpleMasterEngine/MasterDTO) -- see
        # engines/item_lookup_registry.py's module docstring. Manufacturer
        # already has its own dedicated management screen (same one wired
        # on the Dashboard sidebar), so open that instead.
        try:
            from screens.manufacturer_list_screen import ManufacturerListScreen
        except ImportError:
            show_error(
                self, "Manufacturer",
                "Could not open Manufacturer management -- "
                "screens/manufacturer_list_screen.py (ManufacturerListScreen) not found. "
                "Check the actual module path and update _open_manufacturer_manage_dialog() in item_form_screen.py.",
            )
            return
        dialog = ManufacturerListScreen(self)
        dialog.setWindowFlag(Qt.Window)
        if hasattr(dialog, "exec"):
            dialog.exec()
            self._populate_manufacturer_combo()
        else:
            # Non-modal (QWidget, same as the Dashboard's own usage) --
            # refresh the combo once this window actually closes rather
            # than immediately, since show() returns right away.
            dialog.destroyed.connect(self._populate_manufacturer_combo)
            dialog.show()

    # ------------------------------------------------------------------ #
    # Tax Mode UI behaviour
    # ------------------------------------------------------------------ #
    def _on_tax_mode_toggled(self, checked: bool) -> None:
        # checked == True means "Use Country Default" is selected.
        self.ui.lblCountryDefaultPreview.setVisible(checked)
        self.ui.frameIndividualTax.setVisible(not checked)

    # ------------------------------------------------------------------ #
    # Load (edit mode)
    # ------------------------------------------------------------------ #
    def _load_existing_item(self) -> None:
        try:
            dto = self._engine.get_item(self._item_id)
        except RecordNotFoundError as exc:
            self._show_validation_message(str(exc))
            self.ui.btnSave.setEnabled(False)
            return

        self.ui.txtItemCode.setText(dto.item_code or "")
        self.ui.txtItemCode.setReadOnly(True)
        self.ui.txtItemCode.setToolTip("Item Code cannot be changed after creation.")

        self.ui.txtItemName.setText(dto.item_name or "")

        self._set_combo_by_data(self.ui.cmbCategory, dto.category_id)
        self._refresh_sub_category_combo(dto.category_id)
        self._set_combo_by_data(self.ui.cmbSubCategory, dto.sub_category_id)
        self._set_combo_by_data(self.ui.cmbItemGroup, dto.item_group_id)
        self._set_combo_by_data(self.ui.cmbManufacturer, dto.manufacturer_id)
        self._set_combo_by_data(self.ui.cmbGeneric, dto.generic_id)
        self._set_combo_by_data(self.ui.cmbUnit, dto.unit_id)
        self._set_combo_by_data(self.ui.cmbPurchaseUnit, dto.purchase_unit_id)

        self.ui.txtPurchaseRate.setText(f"{float(dto.purchase_rate or 0):.2f}")
        self.ui.txtSaleRate.setText(f"{float(dto.sale_rate or 0):.2f}")
        self.ui.txtMrp.setText(f"{float(dto.mrp or 0):.2f}")
        self.ui.txtMinimumStock.setText(format_qty(dto.minimum_stock))
        self.ui.lblCurrentStockValue.setText(format_qty(dto.total_stock))

        self.ui.cmbStatus.setCurrentText(dto.status or "Active")
        self.ui.txtRemarks.setPlainText(dto.remarks or "")

        is_individual = dto.tax_mode == "individual"
        self.ui.radioIndividual.setChecked(is_individual)
        self.ui.radioCountryDefault.setChecked(not is_individual)
        self.ui.chkVat.setChecked(bool(dto.item_vat_checked))
        self.ui.txtVatPercent.setText(f"{float(dto.item_vat_percent or 0):.2f}" if dto.item_vat_percent is not None else "")
        self.ui.chkCustom.setChecked(bool(dto.item_custom_checked))
        self.ui.txtCustomPercent.setText(f"{float(dto.item_custom_percent or 0):.2f}" if dto.item_custom_percent is not None else "")

        self.ui.btnAddBatch.setEnabled(True)
        self.ui.btnAddBatch.setToolTip("Add a batch with quantity + expiry.")

    @staticmethod
    def _set_combo_by_data(combo, value) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    # ------------------------------------------------------------------ #
    # Add Batch
    # ------------------------------------------------------------------ #
    def _on_add_batch_clicked(self) -> None:
        if self._item_id is None:
            return
        dialog = ItemBatchDialog(self, self._engine, self._item_id, self.ui.txtItemName.text())
        if dialog.exec():
            total_stock = self._engine.get_total_stock(self._item_id)
            self.ui.lblCurrentStockValue.setText(format_qty(total_stock))

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "item_code": self.ui.txtItemCode.text(),
            "item_name": self.ui.txtItemName.text(),
            "category_id": self.ui.cmbCategory.currentData(),
            "sub_category_id": self.ui.cmbSubCategory.currentData(),
            "item_group_id": self.ui.cmbItemGroup.currentData(),
            "manufacturer_id": self.ui.cmbManufacturer.currentData(),
            "generic_id": self.ui.cmbGeneric.currentData(),
            "unit_id": self.ui.cmbUnit.currentData(),
            "purchase_unit_id": self.ui.cmbPurchaseUnit.currentData(),
            "purchase_rate_text": self.ui.txtPurchaseRate.text(),
            "sale_rate_text": self.ui.txtSaleRate.text(),
            "mrp_text": self.ui.txtMrp.text(),
            "minimum_stock_text": self.ui.txtMinimumStock.text(),
            "tax_mode": "individual" if self.ui.radioIndividual.isChecked() else "country_default",
            "item_vat_checked": self.ui.chkVat.isChecked(),
            "item_vat_percent_text": self.ui.txtVatPercent.text(),
            "item_custom_checked": self.ui.chkCustom.isChecked(),
            "item_custom_percent_text": self.ui.txtCustomPercent.text(),
            "status": self.ui.cmbStatus.currentText(),
            "remarks": self.ui.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self._show_validation_message("")

        try:
            payload = build_item_payload(self._collect_form_values())
        except ValueError as exc:
            self._show_validation_message(str(exc))
            return

        # Opening Stock (create mode only) -- validate BEFORE creating the
        # item, so a bad expiry never leaves an item saved without its
        # intended opening batch.
        opening_batch_payload: Optional[dict] = None
        if not self._is_edit_mode:
            try:
                opening_batch_payload = self._build_opening_batch_payload_if_needed()
            except ValueError as exc:
                self._show_validation_message(str(exc))
                return

        try:
            if self._is_edit_mode:
                dto = self._engine.update_item(self._item_id, payload, self._current_user_id)
            else:
                dto = self._engine.create_item(payload, self._current_user_id)
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
            logger.exception("Unexpected error saving item.")
            self._show_validation_message(f"Unexpected error: {exc}")
            return

        if opening_batch_payload is not None:
            try:
                self._engine.add_batch(dto.item_id, opening_batch_payload, self._current_user_id)
            except (ValidationError, DuplicateRecordError, RecordNotFoundError) as exc:
                # Item itself is already saved (0-qty item creation is valid
                # by design) -- surface the batch problem separately rather
                # than pretending the whole save failed.
                message = "\n".join(exc.errors) if isinstance(exc, ValidationError) else str(exc)
                show_error(
                    self, "Item Master",
                    f"Item '{dto.item_name}' was created, but Opening Stock could not be saved: {message}\n"
                    f"Use 'Add Batch' after reopening this item to add it.",
                )
                self.accept()
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error saving opening batch for item %s.", dto.item_id)
                show_error(
                    self, "Item Master",
                    f"Item '{dto.item_name}' was created, but Opening Stock could not be saved: {exc}\n"
                    f"Use 'Add Batch' after reopening this item to add it.",
                )
                self.accept()
                return

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Item Master", f"Item '{dto.item_name}' {action}.")
        self.accept()

    def _build_opening_batch_payload_if_needed(self) -> Optional[dict]:
        """
        Returns None if Opening Quantity is 0 (perfectly valid -- item
        just has no batch yet). Returns a ready-to-use add_batch() payload
        if Opening Quantity > 0, after validating Expiry was given.
        Raises ValueError (shown to the user directly) on bad input.
        """
        from utils.item_form_helpers import build_batch_payload, parse_decimal

        qty = parse_decimal(self.ui.txtOpeningQty.text(), "Opening Quantity")
        if qty <= 0:
            return None

        expiry_year_text = self.ui.txtOpeningExpiryYear.text().strip()
        if not expiry_year_text:
            raise ValueError("Expiry Year is required when Opening Quantity is more than 0.")

        return build_batch_payload({
            "batch_no": "OPENING",
            "expiry_year_text": expiry_year_text,
            "expiry_month_text": str(self.ui.cmbOpeningExpiryMonth.currentIndex() + 1),
            "batch_qty_text": self.ui.txtOpeningQty.text(),
            "batch_purchase_rate_text": self.ui.txtPurchaseRate.text(),
            "remarks": "Opening Stock",
        })

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["ItemFormScreen"]
