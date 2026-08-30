"""
screens/item_list_screen.py

Item List Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/item_list.ui via ui/ui_item_list.py
    - Connect signals to handler methods
    - Call engines/item_engine.py for every data operation
    - Populate the table from what the Engine returns
    - Drive Search / Filter / Soft Delete / Restore / Refresh

STALE-FILTER-DROPDOWN FIX (same bug already found and fixed in the
Customer module's reload()): Category/Manufacturer filter dropdowns are
now refreshed every time `refresh()` runs (not just once at construction),
using blockSignals(True) while repopulating so it never re-triggers
refresh() in a loop. This means adding a new Category via the Item Form's
Manage button shows up in this screen's filter the next time it refreshes,
without needing this screen to be closed and reopened.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.item_engine import ItemDTO, ItemEngine
from engines.item_lookup_registry import category_engine, manufacturer_engine, unit_engine
from screens.item_form_screen import ItemFormScreen
from ui.ui_item_list import Ui_ItemListWidget
from utils.combo_helpers import make_searchable_many
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.item_form_helpers import combo_id_value, dto_to_table_row, format_qty, status_filter_value
from utils.ui_standards import configure_table_columns, install_detail_splitter, standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome
from widgets.master_detail_panel import MasterDetailPanel

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class ItemListScreen(QWidget):
    """Item Master list/search/filter screen. Opens ItemFormScreen for Add/Edit."""

    def __init__(self, parent: Optional[QWidget] = None, engine: Optional[ItemEngine] = None) -> None:
        super().__init__(parent)
        self.ui = Ui_ItemListWidget()
        self.ui.setupUi(self)
        apply_standard_window_chrome(self, width=1360, height=760)
        standardize_action_buttons(self)

        self._engine = engine or ItemEngine()
        self._rows: list[ItemDTO] = []
        self._category_names: dict[int, str] = {}
        self._manufacturer_names: dict[int, str] = {}
        self._unit_names: dict[int, str] = {}

        self._detail = MasterDetailPanel(
            placeholder_title="Select an item",
            placeholder_icon="box.svg",
            field_captions=(
                "Category:", "Manufacturer:", "Unit:", "Purchase Rate:", "Sale Rate:",
                "MRP:", "Stock:", "Min. Stock:", "Nearest Batch:", "Expiry:", "Status:",
                "Created:", "Updated:", "Deleted:",
            ),
        )
        install_detail_splitter(self.ui.verticalLayoutRoot, self.ui.tblItem, self._detail)
        configure_table_columns(self.ui.tblItem, stretch_columns=(1, 2, 3))

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self.refresh)

        self._connect_signals()
        self._setup_shortcuts()
        make_searchable_many(self.ui.cmbCategoryFilter, self.ui.cmbManufacturerFilter)
        self.refresh()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.txtSearch.textChanged.connect(self._on_search_text_changed)
        self.ui.cmbCategoryFilter.currentIndexChanged.connect(self.refresh)
        self.ui.cmbManufacturerFilter.currentIndexChanged.connect(self.refresh)
        self.ui.cmbStatusFilter.currentTextChanged.connect(self.refresh)
        self.ui.chkShowDeleted.toggled.connect(self.refresh)
        self.ui.btnRefresh.clicked.connect(self.refresh)
        self.ui.tblItem.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblItem.doubleClicked.connect(self._on_edit_clicked)
        self.ui.btnAdd.clicked.connect(self._on_add_clicked)
        self.ui.btnEdit.clicked.connect(self._on_edit_clicked)
        self.ui.btnDelete.clicked.connect(self._on_delete_clicked)
        self.ui.btnRestore.clicked.connect(self._on_restore_clicked)
        self.ui.btnClose.clicked.connect(self._on_close_clicked)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_add_clicked)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.ui.txtSearch.setFocus)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._on_delete_clicked)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_close_clicked)

    # ------------------------------------------------------------------ #
    # Filter dropdown population -- refreshed on every refresh(), fixing
    # the stale-dropdown gap (Customer module fix pattern applied here).
    # ------------------------------------------------------------------ #
    def _populate_filter_dropdowns(self) -> None:
        current_category = combo_id_value(self.ui.cmbCategoryFilter.currentData())
        current_manufacturer = combo_id_value(self.ui.cmbManufacturerFilter.currentData())

        self.ui.cmbCategoryFilter.blockSignals(True)
        self.ui.cmbCategoryFilter.clear()
        self.ui.cmbCategoryFilter.addItem("All Categories", None)
        for dto in category_engine().list_active():
            self.ui.cmbCategoryFilter.addItem(dto.name, dto.id)
        restored_index = self.ui.cmbCategoryFilter.findData(current_category)
        self.ui.cmbCategoryFilter.setCurrentIndex(restored_index if restored_index >= 0 else 0)
        self.ui.cmbCategoryFilter.blockSignals(False)

        self.ui.cmbManufacturerFilter.blockSignals(True)
        self.ui.cmbManufacturerFilter.clear()
        self.ui.cmbManufacturerFilter.addItem("All Manufacturers", None)
        try:
            rows, _total = manufacturer_engine().search_manufacturers(status="Active", page_size=1000)
            for dto in rows:
                self.ui.cmbManufacturerFilter.addItem(dto.manufacturer_name, dto.manufacturer_id)
        except Exception:  # noqa: BLE001
            logger.exception("ItemListScreen: failed to load Manufacturer filter list.")
            self.ui.cmbManufacturerFilter.setEnabled(False)
            self.ui.cmbManufacturerFilter.setToolTip("Could not load Manufacturer list.")
        restored_index = self.ui.cmbManufacturerFilter.findData(current_manufacturer)
        self.ui.cmbManufacturerFilter.setCurrentIndex(restored_index if restored_index >= 0 else 0)
        self.ui.cmbManufacturerFilter.blockSignals(False)

        self._category_names = {
            self.ui.cmbCategoryFilter.itemData(i): self.ui.cmbCategoryFilter.itemText(i)
            for i in range(self.ui.cmbCategoryFilter.count())
            if self.ui.cmbCategoryFilter.itemData(i) is not None
        }
        self._manufacturer_names = {
            self.ui.cmbManufacturerFilter.itemData(i): self.ui.cmbManufacturerFilter.itemText(i)
            for i in range(self.ui.cmbManufacturerFilter.count())
            if self.ui.cmbManufacturerFilter.itemData(i) is not None
        }
        self._unit_names = {dto.id: dto.name for dto in unit_engine().list_active()}

    # ------------------------------------------------------------------ #
    # Search / Filter / Refresh
    # ------------------------------------------------------------------ #
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def refresh(self) -> None:
        self._populate_filter_dropdowns()

        search_text = self.ui.txtSearch.text().strip() or None
        category_id = combo_id_value(self.ui.cmbCategoryFilter.currentData())
        manufacturer_id = combo_id_value(self.ui.cmbManufacturerFilter.currentData())
        status = status_filter_value(self.ui.cmbStatusFilter.currentText())
        include_deleted = self.ui.chkShowDeleted.isChecked()

        try:
            rows, total = self._engine.search_items(
                search_text=search_text,
                category_id=category_id,
                manufacturer_id=manufacturer_id,
                status=status,
                include_deleted=include_deleted,
                page=1,
                page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load item list.")
            show_error(self, "Item Master", f"Failed to load items: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.lblRecordCount.setText(f"{total} item(s) found")

    def _populate_table(self, rows: list[ItemDTO]) -> None:
        table = self.ui.tblItem
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            for col_index, value in enumerate(
                dto_to_table_row(
                    dto,                    
                    unit_name=self._unit_names.get(dto.unit_id, ""),
                )
            ):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.item_id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        configure_table_columns(table, stretch_columns=(1, 2, 3))
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[ItemDTO]:
        selected_items = self.ui.tblItem.selectedItems()
        if not selected_items:
            return None
        item_id = selected_items[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.item_id == item_id:
                return dto
        return None

    def _on_selection_changed(self) -> None:
        dto = self._selected_dto()
        has_selection = dto is not None
        is_deleted = bool(dto and dto.is_deleted)

        self.ui.btnEdit.setEnabled(has_selection and not is_deleted)
        self.ui.btnDelete.setEnabled(has_selection and not is_deleted)
        self.ui.btnRestore.setEnabled(has_selection and is_deleted)

        if dto is None:
            self._detail.show_placeholder()
            return
        self._show_detail(dto)

    def _show_detail(self, dto: ItemDTO) -> None:
        self._detail.set_photo(getattr(dto, "photo_path", None))
        self._detail.set_heading(dto.item_name or "-", dto.item_code or "")
        if dto.is_deleted:
            status_text = "Deleted"
        else:
            status_text = dto.status or "-"
        self._detail.set_field("Category:", self._category_names.get(dto.category_id, "") or "-")
        self._detail.set_field("Manufacturer:", self._manufacturer_names.get(dto.manufacturer_id, "") or "-")
        self._detail.set_field("Unit:", self._unit_names.get(dto.unit_id, "") or "-")
        self._detail.set_field("Purchase Rate:", f"{float(dto.purchase_rate or 0):,.2f}")
        self._detail.set_field("Sale Rate:", f"{float(dto.sale_rate or 0):,.2f}")
        self._detail.set_field("MRP:", f"{float(dto.mrp or 0):,.2f}")
        self._detail.set_field("Stock:", format_qty(dto.total_stock))
        self._detail.set_field("Min. Stock:", format_qty(dto.minimum_stock))
        self._detail.set_field("Nearest Batch:", dto.nearest_batch_no or "-")
        self._detail.set_field("Expiry:", dto.nearest_expiry_display or "-")
        self._detail.set_field("Status:", status_text)
        self._detail.set_field(
            "Created:",
            MasterDetailPanel.format_audit(dto.created_by, dto.created_at_bs, dto.created_at_ad),
        )
        self._detail.set_field(
            "Updated:",
            MasterDetailPanel.format_audit(dto.updated_by, dto.updated_at_bs, dto.updated_at_ad),
        )
        self._detail.set_field(
            "Deleted:",
            MasterDetailPanel.format_audit(dto.deleted_by, dto.deleted_at_bs, dto.deleted_at_ad)
            if dto.is_deleted else "-",
        )

    # ------------------------------------------------------------------ #
    # CRUD actions
    # ------------------------------------------------------------------ #
    def _on_add_clicked(self) -> None:
        dialog = ItemFormScreen(self, item_id=None, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = ItemFormScreen(self, item_id=dto.item_id, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(
            self, "Delete Item", f"Delete item '{dto.item_name}'?\n\nThis can be restored later."
        ):
            return
        try:
            self._engine.delete_item(dto.item_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Item Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete item %s.", dto.item_id)
            show_error(self, "Item Master", f"Failed to delete item: {exc}")
        else:
            show_success(self, "Item Master", f"Item '{dto.item_name}' deleted.")
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_item(dto.item_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Item Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore item %s.", dto.item_id)
            show_error(self, "Item Master", f"Failed to restore item: {exc}")
        else:
            show_success(self, "Item Master", f"Item '{restored.item_name}' restored.")
            self.refresh()

    def _on_close_clicked(self) -> None:
        self.close()


__all__ = ["ItemListScreen"]
