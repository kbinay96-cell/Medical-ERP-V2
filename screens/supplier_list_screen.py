"""
screens/supplier_list_screen.py

Supplier List Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/supplier_list.ui via ui/ui_supplier_list.py
    - Connect signals to handler methods
    - Call engines/supplier_engine.py for every data operation
    - Populate the table from what the Engine returns
    - Drive Search / Filter / Soft Delete / Restore / Refresh

Every value shown or read from a widget is converted through
utils/supplier_form_helpers.py (pure functions, no Qt) rather than
reformatted inline here, so that logic stays unit-testable and is not
duplicated between this screen and supplier_form_screen.py.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.supplier_engine import SupplierDTO, SupplierEngine
from screens.supplier_form_screen import SupplierFormScreen
from ui.ui_supplier_list import Ui_SupplierListWidget
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.supplier_form_helpers import dto_to_table_row, status_filter_value

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class SupplierListScreen(QWidget):
    """Supplier Master list/search/filter screen. Opens SupplierFormScreen for Add/Edit."""

    def __init__(self, parent: Optional[QWidget] = None, engine: Optional[SupplierEngine] = None) -> None:
        super().__init__(parent)
        self.ui = Ui_SupplierListWidget()
        self.ui.setupUi(self)

        self._engine = engine or SupplierEngine()
        self._rows: list[SupplierDTO] = []

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
        self.ui.cmbStatusFilter.currentTextChanged.connect(self.refresh)
        self.ui.chkShowDeleted.toggled.connect(self.refresh)
        self.ui.btnRefresh.clicked.connect(self.refresh)
        self.ui.tblSupplier.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblSupplier.doubleClicked.connect(self._on_edit_clicked)
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
    # Search / Filter / Refresh
    # ------------------------------------------------------------------ #
    def _on_search_text_changed(self, _text: str) -> None:
        # Debounced so every keystroke doesn't trigger a query.
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def refresh(self) -> None:
        search_text = self.ui.txtSearch.text().strip() or None
        status = status_filter_value(self.ui.cmbStatusFilter.currentText())
        include_deleted = self.ui.chkShowDeleted.isChecked()

        try:
            rows, total = self._engine.search_suppliers(
                search_text=search_text,
                status=status,
                include_deleted=include_deleted,
                page=1,
                page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load supplier list.")
            show_error(self, "Supplier Master", f"Failed to load suppliers: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.lblRecordCount.setText(f"{total} supplier(s) found")

    def _populate_table(self, rows: list[SupplierDTO]) -> None:
        table = self.ui.tblSupplier
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            for col_index, value in enumerate(dto_to_table_row(dto)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.supplier_id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[SupplierDTO]:
        selected_ranges = self.ui.tblSupplier.selectedItems()
        if not selected_ranges:
            return None
        supplier_id = selected_ranges[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.supplier_id == supplier_id:
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
        dialog = SupplierFormScreen(self, supplier_id=None, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = SupplierFormScreen(self, supplier_id=dto.supplier_id, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(
            self, "Delete Supplier", f"Delete supplier '{dto.supplier_name}'?\n\nThis can be restored later."
        ):
            return
        try:
            self._engine.delete_supplier(dto.supplier_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Supplier Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete supplier %s.", dto.supplier_id)
            show_error(self, "Supplier Master", f"Failed to delete supplier: {exc}")
        else:
            show_success(self, "Supplier Master", f"Supplier '{dto.supplier_name}' deleted.")
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_supplier(dto.supplier_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Supplier Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore supplier %s.", dto.supplier_id)
            show_error(self, "Supplier Master", f"Failed to restore supplier: {exc}")
        else:
            show_success(self, "Supplier Master", f"Supplier '{restored.supplier_name}' restored.")
            self.refresh()

    def _on_close_clicked(self) -> None:
        self.close()


__all__ = ["SupplierListScreen"]
