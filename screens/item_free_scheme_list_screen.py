"""
screens/item_free_scheme_list_screen.py

Item Free Scheme List/Search Screen - Medical ERP V2

Mirrors screens/supplier_manufacturer_discount_list_screen.py's pattern, but
taking only its SIMPLE single-level subset (this table has no scope/level
drill-down the way Supplier -> Mapping -> Item does) -- same reasoning
already documented there for tables with only is_active/is_deleted (no
separate Status Filter combo).
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from engines.exceptions import RecordNotFoundError
from engines.sale_item_free_scheme_engine import SaleItemFreeSchemeDTO, SaleItemFreeSchemeEngine
from screens.item_free_scheme_form_screen import ItemFreeSchemeFormScreen

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300

COL_ITEM_CODE = 0
COL_ITEM_NAME = 1
COL_SCHEME = 2
COL_ACTIVE = 3
COL_REMARKS = 4
COLUMN_COUNT = 5


class ItemFreeSchemeListScreen(QWidget):
    """List/search for the Item Free Scheme master."""

    def __init__(self, parent, engine: SaleItemFreeSchemeEngine, item_engine, current_user_id: int) -> None:
        super().__init__(parent)
        self._engine = engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._rows: list[SaleItemFreeSchemeDTO] = []

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self.refresh)

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Item name...")
        filter_row.addWidget(self.search_input)

        self.show_deleted_checkbox = QCheckBox("Show Deleted")
        filter_row.addWidget(self.show_deleted_checkbox)

        filter_row.addStretch()

        self.new_button = QPushButton("+ New Free Scheme")
        filter_row.addWidget(self.new_button)
        root.addLayout(filter_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["Item Code", "Item Name", "Scheme (Buy+Free)", "Active", "Remarks"]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_ITEM_NAME, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_REMARKS, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

        action_row = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.restore_button = QPushButton("Restore")
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(self.restore_button)
        action_row.addStretch()
        root.addLayout(action_row)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(lambda _: self._debounce_timer.start(SEARCH_DEBOUNCE_MS))
        self.show_deleted_checkbox.toggled.connect(self.refresh)
        self.new_button.clicked.connect(self._on_new_clicked)
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.restore_button.clicked.connect(self._on_restore_clicked)
        self.table.doubleClicked.connect(lambda _: self._on_edit_clicked())

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        search_text = self.search_input.text().strip() or None
        include_deleted = self.show_deleted_checkbox.isChecked()
        self._rows = self._engine.list_schemes(search_text=search_text, include_deleted=include_deleted)
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for dto in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, COL_ITEM_CODE, QTableWidgetItem(dto.item_code or ""))
            self.table.setItem(row, COL_ITEM_NAME, QTableWidgetItem(dto.item_name or ""))
            self.table.setItem(
                row, COL_SCHEME, QTableWidgetItem(f"{dto.scheme_qty:g}+{dto.scheme_free:g}")
            )
            status_text = "Deleted" if dto.is_deleted else ("Active" if dto.is_active else "Inactive")
            self.table.setItem(row, COL_ACTIVE, QTableWidgetItem(status_text))
            self.table.setItem(row, COL_REMARKS, QTableWidgetItem(dto.remarks or ""))
            self.table.item(row, COL_ITEM_CODE).setData(Qt.UserRole, dto.sale_item_free_scheme_id)

    def _selected_dto(self) -> Optional[SaleItemFreeSchemeDTO]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    # ------------------------------------------------------------------ #
    def _on_new_clicked(self) -> None:
        dialog = ItemFreeSchemeFormScreen(self, None, self._engine, self._item_engine, self._current_user_id)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None:
            QMessageBox.information(self, "No Selection", "Select a row to edit first.")
            return
        dialog = ItemFreeSchemeFormScreen(
            self, dto.sale_item_free_scheme_id, self._engine, self._item_engine, self._current_user_id
        )
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None:
            QMessageBox.information(self, "No Selection", "Select a row to delete first.")
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete the Free Scheme for '{dto.item_name}'?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self._engine.soft_delete_scheme(dto.sale_item_free_scheme_id, self._current_user_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Cannot Delete", str(exc))
            return
        self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None:
            QMessageBox.information(self, "No Selection", "Select a deleted row to restore first.")
            return
        if not dto.is_deleted:
            QMessageBox.information(self, "Not Deleted", "This row is not deleted.")
            return
        try:
            self._engine.restore_scheme(dto.sale_item_free_scheme_id, self._current_user_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Cannot Restore", str(exc))
            return
        self.refresh()


__all__ = ["ItemFreeSchemeListScreen"]