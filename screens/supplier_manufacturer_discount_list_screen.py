"""
screens/supplier_manufacturer_discount_list_screen.py

Supplier-Manufacturer Discount List Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/supplier_manufacturer_discount_list.ui via
      ui/ui_supplier_manufacturer_discount_list.py
    - Connect signals to handler methods
    - Call engines/supplier_manufacturer_discount_engine.py for every data
      operation
    - Populate the table from what the Engine returns
    - Drive Search / Soft Delete / Restore / Refresh

Mirrors screens/manufacturer_list_screen.py exactly, minus the Status
Filter combo -- this table has no Active/Inactive status of its own (only
is_deleted), so there is nothing for that combo to filter on.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.supplier_manufacturer_discount_engine import (
    SupplierManufacturerDiscountDTO,
    SupplierManufacturerDiscountEngine,
)
from screens.supplier_manufacturer_discount_form_screen import SupplierManufacturerDiscountFormScreen
from ui.ui_supplier_manufacturer_discount_list import Ui_SupplierManufacturerDiscountListWidget
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.supplier_manufacturer_discount_form_helpers import dto_to_table_row

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class SupplierManufacturerDiscountListScreen(QWidget):
    """Supplier-Manufacturer Discount list/search screen. Opens
    SupplierManufacturerDiscountFormScreen for Add/Edit."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        engine: Optional[SupplierManufacturerDiscountEngine] = None,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_SupplierManufacturerDiscountListWidget()
        self.ui.setupUi(self)

        self._engine = engine or SupplierManufacturerDiscountEngine()
        self._rows: list[SupplierManufacturerDiscountDTO] = []

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self.refresh)

        self._connect_signals()
        self._setup_shortcuts()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.txtSearch.textChanged.connect(self._on_search_text_changed)
        self.ui.chkShowDeleted.toggled.connect(self.refresh)
        self.ui.btnRefresh.clicked.connect(self.refresh)
        self.ui.tblDiscount.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblDiscount.doubleClicked.connect(self._on_edit_clicked)
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
    # Search / Refresh
    # ------------------------------------------------------------------ #
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def refresh(self) -> None:
        search_text = self.ui.txtSearch.text().strip() or None
        include_deleted = self.ui.chkShowDeleted.isChecked()

        try:
            rows, total = self._engine.search_discounts(
                search_text=search_text,
                include_deleted=include_deleted,
                page=1,
                page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load supplier-manufacturer discount list.")
            show_error(self, "Supplier-Manufacturer Discount", f"Failed to load mappings: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.lblRecordCount.setText(f"{total} mapping(s) found")

    def _populate_table(self, rows: list[SupplierManufacturerDiscountDTO]) -> None:
        table = self.ui.tblDiscount
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            for col_index, value in enumerate(dto_to_table_row(dto)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[SupplierManufacturerDiscountDTO]:
        selected_items = self.ui.tblDiscount.selectedItems()
        if not selected_items:
            return None
        record_id = selected_items[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.id == record_id:
                return dto
        return None

    def _on_selection_changed(self) -> None:
        dto = self._selected_dto()
        has_selection = dto is not None
        is_deleted = bool(dto and dto.is_deleted)

        self.ui.btnEdit.setEnabled(has_selection and not is_deleted)
        self.ui.btnDelete.setEnabled(has_selection and not is_deleted)
        self.ui.btnRestore.setEnabled(has_selection and is_deleted)

    # ------------------------------------------------------------------ #
    # CRUD actions
    # ------------------------------------------------------------------ #
    def _on_add_clicked(self) -> None:
        dialog = SupplierManufacturerDiscountFormScreen(self, discount_id=None, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = SupplierManufacturerDiscountFormScreen(self, discount_id=dto.id, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
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
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
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
            self.refresh()

    def _on_close_clicked(self) -> None:
        self.close()


__all__ = ["SupplierManufacturerDiscountListScreen"]
