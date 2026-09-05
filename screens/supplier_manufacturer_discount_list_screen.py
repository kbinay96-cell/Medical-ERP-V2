"""
screens/supplier_manufacturer_discount_list_screen.py

Supplier-Manufacturer Discount List Screen/Controller - Medical ERP V2

Three-level drill-down inside ONE screen/table (no extra dialogs):
    Level 1 "suppliers"    -> list of Suppliers
    Level 2 "mappings"     -> selected supplier's Manufacturer + Discount% rows
    Level 3 "items"        -> selected manufacturer's full Item Master items

Breadcrumb + Back button navigate between levels. Search + Prev/Next
pagination work independently at each level.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QPushButton, QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.item_engine import ItemDTO, ItemEngine
from engines.supplier_engine import SupplierDTO, SupplierEngine
from engines.supplier_manufacturer_discount_engine import (
    SupplierManufacturerDiscountDTO,
    SupplierManufacturerDiscountEngine,
)
from screens.supplier_manufacturer_discount_form_screen import SupplierManufacturerDiscountFormScreen
from ui.ui_supplier_manufacturer_discount_list import Ui_SupplierManufacturerDiscountListWidget
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.ui_standards import configure_table_columns, standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300
PAGE_SIZE = 50

STATE_SUPPLIERS = "suppliers"
STATE_MAPPINGS = "mappings"
STATE_ITEMS = "items"


class SupplierManufacturerDiscountListScreen(QWidget):
    """Supplier -> Manufacturer/Discount -> Item drill-down, all in one table."""

    close_requested = Signal()
    form_requested = Signal(object)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        engine: Optional[SupplierManufacturerDiscountEngine] = None,
        supplier_engine: Optional[SupplierEngine] = None,
        item_engine: Optional[ItemEngine] = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_SupplierManufacturerDiscountListWidget()
        self.ui.setupUi(self)
        self._embedded = embedded
        apply_standard_window_chrome(self, width=1100, height=700, embedded=embedded)
        standardize_action_buttons(self)

        self._engine = engine or SupplierManufacturerDiscountEngine()
        self._supplier_engine = supplier_engine or SupplierEngine()
        self._item_engine = item_engine or ItemEngine()

        self._view_state = STATE_SUPPLIERS
        self._current_supplier: Optional[SupplierDTO] = None
        self._current_manufacturer_id: Optional[int] = None
        self._current_manufacturer_name: str = ""

        self._rows: list = []  # holds whichever DTO type is current for this level
        self._page = 1
        self._total = 0

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._reload_current_level)

        self._connect_signals()
        self._setup_shortcuts()
        self._enter_suppliers_level()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.txtSearch.textChanged.connect(self._on_search_text_changed)
        self.ui.chkShowDeleted.toggled.connect(self._reload_current_level)
        self.ui.btnRefresh.clicked.connect(self._reload_current_level)
        self.ui.tblDiscount.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblDiscount.doubleClicked.connect(self._on_row_double_clicked)
        self.ui.btnAdd.clicked.connect(self._on_add_clicked)
        self.ui.btnEdit.clicked.connect(self._on_edit_clicked)
        self.ui.btnDelete.clicked.connect(self._on_delete_clicked)
        self.ui.btnRestore.clicked.connect(self._on_restore_clicked)
        self.ui.btnBack.clicked.connect(self._on_back_clicked)
        self.ui.btnPrev.clicked.connect(self._on_prev_page)
        self.ui.btnNext.clicked.connect(self._on_next_page)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_add_clicked)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.ui.txtSearch.setFocus)
        QShortcut(QKeySequence("F5"), self).activated.connect(self._reload_current_level)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._on_delete_clicked)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_close_clicked)

    # ------------------------------------------------------------------ #
    # Level transitions
    # ------------------------------------------------------------------ #
    def _enter_suppliers_level(self) -> None:
        self._view_state = STATE_SUPPLIERS
        self._current_supplier = None
        self._current_manufacturer_id = None
        self._current_manufacturer_name = ""
        self._page = 1
        self.ui.txtSearch.blockSignals(True)
        self.ui.txtSearch.clear()
        self.ui.txtSearch.setPlaceholderText("Search Suppliers...")
        self.ui.txtSearch.blockSignals(False)
        self.ui.lblBreadcrumb.setText("Suppliers")
        self._apply_level_button_visibility()
        self._reload_current_level()

    def _enter_mappings_level(self, supplier: SupplierDTO) -> None:
        self._view_state = STATE_MAPPINGS
        self._current_supplier = supplier
        self._current_manufacturer_id = None
        self._current_manufacturer_name = ""
        self._page = 1
        self.ui.txtSearch.blockSignals(True)
        self.ui.txtSearch.clear()
        self.ui.txtSearch.setPlaceholderText("Search by Manufacturer or Item name...")
        self.ui.txtSearch.blockSignals(False)
        self.ui.lblBreadcrumb.setText(f"Suppliers > {supplier.supplier_name}")
        self._apply_level_button_visibility()
        self._reload_current_level()

    def _enter_items_level(self, manufacturer_id: int, manufacturer_name: str) -> None:
        self._view_state = STATE_ITEMS
        self._current_manufacturer_id = manufacturer_id
        self._current_manufacturer_name = manufacturer_name
        self._page = 1
        self.ui.txtSearch.blockSignals(True)
        self.ui.txtSearch.clear()
        self.ui.txtSearch.setPlaceholderText("Search Items...")
        self.ui.txtSearch.blockSignals(False)
        supplier_name = self._current_supplier.supplier_name if self._current_supplier else ""
        self.ui.lblBreadcrumb.setText(f"Suppliers > {supplier_name} > {manufacturer_name}")
        self._apply_level_button_visibility()
        self._reload_current_level()

    def _on_back_clicked(self) -> None:
        if self._view_state == STATE_ITEMS:
            self._enter_mappings_level(self._current_supplier)
        elif self._view_state == STATE_MAPPINGS:
            self._enter_suppliers_level()
        else:
            self._on_close_clicked()

    def _apply_level_button_visibility(self) -> None:
        is_mappings = self._view_state == STATE_MAPPINGS
        self.ui.btnAdd.setVisible(is_mappings)
        self.ui.btnEdit.setVisible(is_mappings)
        self.ui.btnDelete.setVisible(is_mappings)
        self.ui.btnRestore.setVisible(is_mappings)
        self.ui.chkShowDeleted.setVisible(is_mappings)

    # ------------------------------------------------------------------ #
    # Search / Refresh (dispatches by level)
    # ------------------------------------------------------------------ #
    def _on_search_text_changed(self, _text: str) -> None:
        self._page = 1
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def _reload_current_level(self) -> None:
        if self._view_state == STATE_SUPPLIERS:
            self._load_suppliers()
        elif self._view_state == STATE_MAPPINGS:
            self._load_mappings()
        else:
            self._load_items()

    def _load_suppliers(self) -> None:
        search_text = self.ui.txtSearch.text().strip() or None
        try:
            rows, total = self._supplier_engine.search_suppliers(
                search_text=search_text,
                include_deleted=False,
                page=self._page,
                page_size=PAGE_SIZE,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load supplier list.")
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to load suppliers: {exc}")
            return
        self._rows = rows
        self._total = total
        self._populate_suppliers_table(rows)
        self.ui.lblRecordCount.setText(f"{total} supplier(s) found")
        self._update_pagination_label()

    def _load_mappings(self) -> None:
        if self._current_supplier is None:
            return
        search_text = self.ui.txtSearch.text().strip() or None
        include_deleted = self.ui.chkShowDeleted.isChecked()

        try:
            rows, total = self._engine.search_discounts(
                search_text=search_text,
                supplier_id=self._current_supplier.supplier_id,
                include_deleted=include_deleted,
                page=self._page,
                page_size=PAGE_SIZE,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load discount mappings.")
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to load mappings: {exc}")
            return

        # Search by manufacturer/remarks won't catch an item-name search --
        # additionally resolve any items matching the text to their
        # manufacturer_id and pull in those mappings too (merged, deduped).
        if search_text:
            try:
                item_rows, _ = self._item_engine.search_items(
                    search_text=search_text, page=1, page_size=100
                )
                extra_manufacturer_ids = {
                    i.manufacturer_id for i in item_rows if i.manufacturer_id
                }
                existing_ids = {r.id for r in rows}
                for manufacturer_id in extra_manufacturer_ids:
                    extra_rows, _ = self._engine.search_discounts(
                        supplier_id=self._current_supplier.supplier_id,
                        manufacturer_id=manufacturer_id,
                        include_deleted=include_deleted,
                        page=1,
                        page_size=PAGE_SIZE,
                    )
                    for r in extra_rows:
                        if r.id not in existing_ids:
                            rows.append(r)
                            existing_ids.add(r.id)
                total = len(rows)
            except Exception:  # noqa: BLE001
                logger.exception("Item-name fallback search failed; showing manufacturer/remarks matches only.")

        self._rows = rows
        self._total = total
        self._populate_mappings_table(rows)
        self.ui.lblRecordCount.setText(f"{total} mapping(s) found")
        self._update_pagination_label()

    def _load_items(self) -> None:
        if self._current_manufacturer_id is None:
            return
        search_text = self.ui.txtSearch.text().strip() or None
        try:
            rows, total = self._item_engine.search_items(
                search_text=search_text,
                manufacturer_id=self._current_manufacturer_id,
                page=self._page,
                page_size=PAGE_SIZE,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load items for manufacturer.")
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to load items: {exc}")
            return
        self._rows = rows
        self._total = total
        self._populate_items_table(rows)
        self.ui.lblRecordCount.setText(f"{total} item(s) found")
        self._update_pagination_label()

    # ------------------------------------------------------------------ #
    # Table population (per level)
    # ------------------------------------------------------------------ #
    def _populate_suppliers_table(self, rows: list[SupplierDTO]) -> None:
        table = self.ui.tblDiscount
        table.setSortingEnabled(False)
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["Supplier Name"])
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            item = QTableWidgetItem(dto.supplier_name or "")
            item.setData(Qt.UserRole, dto.supplier_id)
            table.setItem(row_index, 0, item)
        table.setSortingEnabled(True)
        configure_table_columns(table, stretch_columns=(0,))
        self._on_selection_changed()

    def _populate_mappings_table(self, rows: list[SupplierManufacturerDiscountDTO]) -> None:
        table = self.ui.tblDiscount
        table.setSortingEnabled(False)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Manufacturer Name", "Discount %", "Status"])
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            values = [
                dto.manufacturer_name or "",
                f"{dto.discount_percent:.2f}",
                "Deleted" if dto.is_deleted else "Active",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.id)
                item.setData(Qt.UserRole + 1, dto.manufacturer_id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        configure_table_columns(table, stretch_columns=(0,))
        self._on_selection_changed()

    def _populate_items_table(self, rows: list[ItemDTO]) -> None:
        table = self.ui.tblDiscount
        table.setSortingEnabled(False)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Item Code", "Item Name", "MRP", "Stock"])
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            values = [
                dto.item_code or "",
                dto.item_name or "",
                f"{dto.mrp:.2f}",
                f"{dto.total_stock:g}",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.item_id)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        configure_table_columns(table, stretch_columns=(1,))
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Pagination
    # ------------------------------------------------------------------ #
    def _update_pagination_label(self) -> None:
        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.ui.lblPageInfo.setText(f"Page {self._page} of {total_pages}")
        self.ui.btnPrev.setEnabled(self._page > 1)
        self.ui.btnNext.setEnabled(self._page < total_pages)

    def _on_prev_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._reload_current_level()

    def _on_next_page(self) -> None:
        total_pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._page < total_pages:
            self._page += 1
            self._reload_current_level()

    # ------------------------------------------------------------------ #
    # Selection / navigation
    # ------------------------------------------------------------------ #
    def _selected_row_index(self) -> Optional[int]:
        selected_items = self.ui.tblDiscount.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].row()

    def _selected_mapping_dto(self) -> Optional[SupplierManufacturerDiscountDTO]:
        if self._view_state != STATE_MAPPINGS:
            return None
        row_index = self._selected_row_index()
        if row_index is None or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

    def _on_selection_changed(self) -> None:
        dto = self._selected_mapping_dto()
        has_selection = dto is not None
        is_deleted = bool(dto and dto.is_deleted)
        self.ui.btnEdit.setEnabled(has_selection and not is_deleted)
        self.ui.btnDelete.setEnabled(has_selection and not is_deleted)
        self.ui.btnRestore.setEnabled(has_selection and is_deleted)

    def _on_row_double_clicked(self) -> None:
        row_index = self._selected_row_index()
        if row_index is None or row_index >= len(self._rows):
            return
        if self._view_state == STATE_SUPPLIERS:
            supplier = self._rows[row_index]
            self._enter_mappings_level(supplier)
        elif self._view_state == STATE_MAPPINGS:
            dto = self._rows[row_index]
            if not dto.is_deleted:
                self._enter_items_level(dto.manufacturer_id, dto.manufacturer_name or "")
        # STATE_ITEMS: double-click does nothing (leaf level)

    # ------------------------------------------------------------------ #
    # CRUD actions (mappings level only)
    # ------------------------------------------------------------------ #
    def _on_add_clicked(self) -> None:
        if self._current_supplier is None:
            return
        if self._embedded:
            self.form_requested.emit((None, self._current_supplier.supplier_id))
            return
        dialog = SupplierManufacturerDiscountFormScreen(
            self, discount_id=None, engine=self._engine,
            initial_supplier_id=self._current_supplier.supplier_id,
        )
        if dialog.exec():
            self._reload_current_level()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_mapping_dto()
        if dto is None or dto.is_deleted:
            return
        if self._embedded:
            self.form_requested.emit((dto.id, None))
            return
        dialog = SupplierManufacturerDiscountFormScreen(self, discount_id=dto.id, engine=self._engine)
        if dialog.exec():
            self._reload_current_level()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_mapping_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(
            self, "Delete Discount Mapping",
            f"Delete discount mapping for '{dto.supplier_name}' / '{dto.manufacturer_name}'?\n\n"
            f"This can be restored later.",
        ):
            return
        try:
            self._engine.delete_discount(dto.id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Supplier-Manufacturer Discount", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete discount mapping %s.", dto.id)
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to delete mapping: {exc}")
        else:
            show_success(
                self, "Supplier-Manufacturer Discount",
                f"Discount mapping for '{dto.supplier_name}' / '{dto.manufacturer_name}' deleted.",
            )
            self._reload_current_level()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_mapping_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_discount(dto.id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Supplier-Manufacturer Discount", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore discount mapping %s.", dto.id)
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to restore mapping: {exc}")
        else:
            show_success(
                self, "Supplier-Manufacturer Discount",
                f"Discount mapping for '{restored.supplier_name}' / '{restored.manufacturer_name}' restored.",
            )
            self._reload_current_level()

    def _on_close_clicked(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        self.close()


__all__ = ["SupplierManufacturerDiscountListScreen"]