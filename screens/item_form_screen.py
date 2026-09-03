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

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QLineEdit, QWidget

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
from screens.master_manage_screen import MasterManageDialog
from ui.ui_item_form import Ui_ItemFormDialog
from utils.combo_helpers import attach_manage_button, make_searchable_many
from utils.integration_adapters import get_current_user_id, show_error, show_success
from utils.item_form_helpers import build_item_payload, combo_id_value, format_qty
from utils.ui_standards import standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome
from widgets.expiry_date_picker import ExpiryDatePicker
from widgets.photo_picker import host_photo_beside_scroll

logger = logging.getLogger(__name__)


class ItemFormScreen(QDialog):
    """Add/Edit dialog for a single item. Create mode when item_id is None."""

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        item_id: Optional[int] = None,
        engine: Optional[ItemEngine] = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._embedded = embedded
        self.ui = Ui_ItemFormDialog()
        self.ui.setupUi(self)
        apply_standard_window_chrome(self, width=920, height=760, embedded=embedded)
        self._photo_picker = host_photo_beside_scroll(self.ui.verticalLayoutRoot, self.ui.scrollArea, side="right")
        self.ui.scrollAreaContents.setStyleSheet("QLineEdit { max-width: 220px; }")
        self._install_batch_fields()
        standardize_action_buttons(self)

        self._engine = engine or ItemEngine(
          manufacturer_lookup_fn=self._safe_manufacturer_lookup,
        )
        self._item_id = item_id
        self._is_edit_mode = item_id is not None
        self._current_manufacturer_margin: Optional[float] = None
        self._purchase_rate_is_autofilled = False
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
          self._load_existing_item()
        else:
          self.setWindowTitle("Add Item")
          self.ui.lblFormTitle.setText("Add Item")
          self.ui.txtItemName.setFocus()

    def _install_batch_fields(self) -> None:
        """Batch registration is part of Save (including qty 0). No extra Add Batch step."""
        self.ui.btnAddBatch.hide()
        self.ui.lblOpeningQty.setText("Batch Quantity:")
        self.ui.txtOpeningQty.setToolTip(
          "May be 0 — registers an initial zero-stock batch when Batch No. is filled."
        )
        self.ui.lblOpeningExpiry.setText("Expiry Date:")
        self.ui.cmbOpeningExpiryMonth.hide()
        self.ui.txtOpeningExpiryYear.hide()
        self._expiry_picker = ExpiryDatePicker(self.ui.grpPricing)
        self.ui.horizontalLayoutOpeningExpiry.addWidget(self._expiry_picker)
        self.ui.lblOpeningExpiryHint.setText(
          "Save registers this batch on the item (qty may be 0). Expiry is stored as AD month/year."
        )
        self.ui.lblOpeningQty.setVisible(True)
        self.ui.txtOpeningQty.setVisible(True)
        self.ui.lblOpeningExpiry.setVisible(True)
        self.ui.lblOpeningExpiryHint.setVisible(True)

        self.txtBatchNo = QLineEdit(self.ui.grpPricing)
        self.txtBatchNo.setObjectName("txtBatchNo")
        self.txtBatchNo.setPlaceholderText("e.g. OPENING or B-2027-045")
        self.ui.formLayoutPricing.insertRow(
          self.ui.formLayoutPricing.indexOf(self.ui.txtOpeningQty),
          "Batch No.",
          self.txtBatchNo,
        )

    def _set_opening_stock_fields_visible(self, visible: bool) -> None:
        self.ui.lblOpeningQty.setVisible(visible)
        self.ui.txtOpeningQty.setVisible(visible)
        self.ui.lblOpeningExpiry.setVisible(visible)
        self._expiry_picker.setVisible(visible)
        self.ui.lblOpeningExpiryHint.setVisible(visible)
        self.txtBatchNo.setVisible(visible)

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
        self.ui.cmbManufacturer.currentIndexChanged.connect(self._on_manufacturer_changed)
        self.ui.txtMrp.editingFinished.connect(self._maybe_autofill_pricing_fields)
        self.ui.txtPurchaseRate.textEdited.connect(self._on_purchase_rate_manually_edited)
        self.ui.txtSuperDiscountPercent.editingFinished.connect(self._on_super_discount_percent_changed)

    def reject(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        super().reject()

    def _finish_success(self) -> None:
        if self._embedded:
            self.saved.emit()
        else:
            self.accept()

    def _finish_partial(self) -> None:
        if self._embedded:
            self.close_requested.emit()
        else:
            self.accept()

    def _reset_for_new_item(self) -> None:
        """Clears the form back to a blank Add-Item state (stay-open multi-add)."""
        self.ui.txtItemCode.clear()
        self.ui.txtItemName.clear()

        self._set_combo_by_data(self.ui.cmbCategory, None)
        self._refresh_sub_category_combo(None)
        self._set_combo_by_data(self.ui.cmbItemGroup, None)
        self._set_combo_by_data(self.ui.cmbManufacturer, None)
        self._set_combo_by_data(self.ui.cmbGeneric, None)
        self.ui.cmbUnit.setCurrentIndex(0)
        self._set_combo_by_data(self.ui.cmbPurchaseUnit, None)

        self.ui.txtPurchaseRate.setText("0.00")
        self.ui.txtSaleRate.setText("0.00")
        self.ui.txtMrp.setText("0.00")
        self.ui.txtMinimumStock.clear()
        self.ui.lblCurrentStockValue.setText("0")

        self.ui.cmbStatus.setCurrentText("Active")
        self.ui.txtRemarks.clear()

        self.ui.radioIndividual.setChecked(False)
        self.ui.radioCountryDefault.setChecked(True)
        self.ui.chkVat.setChecked(False)
        self.ui.txtVatPercent.clear()
        self.ui.chkCustom.setChecked(False)
        self.ui.txtCustomPercent.clear()

        self._photo_picker.load_existing(None)

        self.txtBatchNo.clear()
        self.ui.txtOpeningQty.clear()
        next_year = QDate.currentDate().addYears(1)
        self._expiry_picker.set_month_year(next_year.month(), next_year.year())
        self._existing_batch_id = None

        self._current_manufacturer_margin = None
        self._purchase_rate_is_autofilled = False

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)

    def _safe_manufacturer_lookup(self, manufacturer_id):
        from engines.item_lookup_registry import manufacturer_lookup
        return manufacturer_lookup(manufacturer_id)

    def _on_manufacturer_changed(self, _index: int) -> None:
        manufacturer_id = self.ui.cmbManufacturer.currentData()
        self._current_manufacturer_margin = None
        if manufacturer_id is not None:
          try:
              dto = manufacturer_engine().get_manufacturer(manufacturer_id)
              self._current_manufacturer_margin = dto.default_margin_percent
          except Exception:  # noqa: BLE001 -- margin is a convenience, never block the form
              logger.exception("Failed to load manufacturer margin for id=%s.", manufacturer_id)
        self._maybe_autofill_pricing_fields()

    def _on_super_discount_percent_changed(self) -> None:
        self._maybe_autofill_pricing_fields()

    def _update_sale_rate_field_visibility(self) -> None:
        """Disables the Sale Rate field if business type is Retailer."""
        business_type = self._get_business_type()
        self.ui.txtSaleRate.setEnabled(business_type != 'Retailer')

    # Checks whether the global business type is Wholesaler.
    def _is_wholesaler(self) -> bool:
        """Checks if the business type is Wholesaler."""
        return self._get_business_type() == 'Wholesaler'

    def _get_business_type(self) -> str:
        """Reads the business type setting from the settings engine."""
        try:
          from engines import settings_engine
          return settings_engine.get_setting('general.business_type', 'Retailer')
        except Exception:
          logger.exception("Failed to load business type setting.")
          return 'Retailer'

    def _maybe_autofill_pricing_fields(self) -> None:
        """
        Estimates Purchase Rate (and Sale Rate, in Wholesaler mode) from
        MRP using the selected Manufacturer's default_margin_percent and
        the item's own Super Discount % -- ONLY when the target field is
        still blank/zero (never overwrites a value the user already typed
        or that came from a real Purchase Invoice). Purely a starting
        guess for Opening Stock entry; always stays editable.

        Chain: PTR = MRP x (1 - manufacturer_margin% / 100)
               Purchase Rate = PTR x (1 - super_discount% / 100)
               Sale Rate (Wholesaler mode only) = PTR
        """
        mrp_text = self.ui.txtMrp.text().strip()
        try:
          mrp = float(mrp_text) if mrp_text else 0
        except ValueError:
          mrp = 0

        margin_raw = getattr(self, "_current_manufacturer_margin", None)
        try:
          margin = float(margin_raw) if margin_raw is not None else 0.0
        except (TypeError, ValueError):
          margin = 0.0
        ptr = mrp * (1 - margin / 100)

        super_discount_percent_text = self.ui.txtSuperDiscountPercent.text().strip()
        try:
          super_discount_percent = float(super_discount_percent_text) if super_discount_percent_text else 0
        except ValueError:
          super_discount_percent = 0
        purchase_rate = ptr * (1 - super_discount_percent / 100)

        def _is_blank_or_zero(text: str) -> bool:
          text = text.strip()
          if not text:
              return True
          try:
              return float(text) == 0
          except ValueError:
              return False  # unparseable text -- treat as a real value, leave it alone

        if _is_blank_or_zero(self.ui.txtPurchaseRate.text()) or self._purchase_rate_is_autofilled:
          self.ui.txtPurchaseRate.setText(f"{purchase_rate:.2f}")
          self._purchase_rate_is_autofilled = True

        if self._is_wholesaler() and _is_blank_or_zero(self.ui.txtSaleRate.text()):
          self.ui.txtSaleRate.setText(f"{ptr:.2f}")

    def _on_purchase_rate_manually_edited(self, _text: str) -> None:
        self._purchase_rate_is_autofilled = False

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
        self._photo_picker.load_existing(getattr(dto, "photo_path", None))

        self._existing_batch_id = None
        try:
          batches = self._engine.get_batches(dto.item_id)
        except Exception:  # noqa: BLE001
          batches = []
        if batches:
          batch = batches[0]
          self._existing_batch_id = batch.item_batch_id
          self.txtBatchNo.setText(batch.batch_no or "")
          self.ui.txtOpeningQty.setText(format_qty(batch.batch_qty))
          self._expiry_picker.set_expiry_month_year_ad(int(batch.expiry_month), int(batch.expiry_year))

    @staticmethod
    def _set_combo_by_data(combo, value) -> None:
        if value is None:
          combo.setCurrentIndex(0)
          return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

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

        payload.update(self._photo_picker.get_photo_update())

        opening_batch_payload: Optional[dict] = None
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
              self._engine.add_batch(
                  dto.item_id, opening_batch_payload, self._current_user_id,
                  item_batch_id=opening_batch_payload.pop("item_batch_id", None),
              )
          except (ValidationError, DuplicateRecordError, RecordNotFoundError) as exc:
              # Item itself is already saved (0-qty item creation is valid
              # by design) -- surface the batch problem separately rather
              # than pretending the whole save failed.
              message = "\n".join(exc.errors) if isinstance(exc, ValidationError) else str(exc)
              show_error(
                  self, "Item Master",
                  f"Item '{dto.item_name}' was saved, but the batch could not be registered: {message}"
              )
              self._finish_partial()
              return
          except Exception as exc:  # noqa: BLE001
              logger.exception("Unexpected error saving opening batch for item %s.", dto.item_id)
              show_error(
                  self, "Item Master",
                  f"Item '{dto.item_name}' was saved, but the batch could not be registered: {exc}"
              )
              self._finish_partial()
              return

        action = "updated" if self._is_edit_mode else "created"
        show_success(self, "Item Master", f"Item '{dto.item_name}' {action}.")

        if self._is_edit_mode:
            self._finish_success()
            return

        # Create mode: stay open, reset for the next entry instead of closing --
        # lets the user add several items back-to-back without reopening the form.
        self._reset_for_new_item()
        self.ui.txtItemName.setFocus()

    def _build_opening_batch_payload_if_needed(self) -> Optional[dict]:
        """
        Registers a batch on Save when Batch No. is filled (qty may be 0).
        Empty batch no + qty 0 still allows an item with no batches.
        """
        from utils.item_form_helpers import build_batch_payload, parse_decimal

        qty = parse_decimal(self.ui.txtOpeningQty.text(), "Batch Quantity")
        batch_no = self.txtBatchNo.text().strip()
        if not batch_no and qty == 0:
          return None
        if not batch_no:
          batch_no = "OPENING"

        month, year = self._expiry_picker.expiry_month_year_ad()
        payload = build_batch_payload({
          "batch_no": batch_no,
          "expiry_year_text": str(year),
          "expiry_month_text": str(month),
          "batch_qty_text": self.ui.txtOpeningQty.text(),
          "batch_purchase_rate_text": self.ui.txtPurchaseRate.text(),
          "remarks": "Opening Stock" if not self._is_edit_mode else "Batch entry",
        })
        payload["item_batch_id"] = getattr(self, "_existing_batch_id", None)
        return payload

    def _show_validation_message(self, message: str) -> None:
        self.ui.lblValidationMessage.setText(message)


__all__ = ["ItemFormScreen"]
