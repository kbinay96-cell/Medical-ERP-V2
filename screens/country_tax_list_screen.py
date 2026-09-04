"""
screens/country_tax_list_screen.py

Country Tax Settings List Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- per project rule "No SQL. No business
logic."):
    - Load ui/country_tax_list.ui via ui/ui_country_tax_list.py
    - Connect signals to handler methods
    - Call engines/country_tax_engine.py for every data operation
    - Populate the table from what the Engine returns
    - Drive Search / Filter / Soft Delete / Restore / Refresh

Mirrors screens/manufacturer_list_screen.py exactly.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QPushButton, QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.country_tax_engine import CountryTaxDTO, CountryTaxEngine
from screens.country_tax_form_screen import CountryTaxFormScreen
from ui.ui_country_tax_list import Ui_CountryTaxListWidget
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.country_tax_form_helpers import dto_to_table_row, status_filter_value
from utils.ui_standards import configure_table_columns, standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class CountryTaxListScreen(QWidget):
    """Country Tax Settings list/search/filter screen. Opens CountryTaxFormScreen for Add/Edit."""

    close_requested = Signal()
    form_requested = Signal(object)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        engine: Optional[CountryTaxEngine] = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.ui = Ui_CountryTaxListWidget()
        self.ui.setupUi(self)
        self._embedded = embedded
        apply_standard_window_chrome(self, width=1100, height=700, embedded=embedded)
        standardize_action_buttons(self)
        self._engine = engine or CountryTaxEngine()
        self._rows: list[CountryTaxDTO] = []
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self.refresh)
        if self._embedded:
            self._setup_back_button()
        self._connect_signals()
        self._setup_shortcuts()
        self.refresh()

    def _setup_back_button(self) -> None:
        """Text-based back button — note this screen's toolbar layout is
        horizontalLayoutToolbar (camelCase), unlike Company's horizontalLayout_filters."""
        self.btnBack = QPushButton("\u2190 Back", self)
        self.btnBack.setCursor(Qt.PointingHandCursor)
        self.btnBack.setFlat(True)
        self.btnBack.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 4px 8px; }"
            "QPushButton:hover { background: rgba(127,127,127,40); border-radius: 4px; }"
        )
        self.btnBack.clicked.connect(self._on_close_clicked)
        self.ui.horizontalLayoutToolbar.insertWidget(0, self.btnBack)

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.txtSearch.textChanged.connect(self._on_search_text_changed)
        self.ui.cmbStatusFilter.currentTextChanged.connect(self.refresh)
        self.ui.chkShowDeleted.toggled.connect(self.refresh)
        self.ui.btnRefresh.clicked.connect(self.refresh)
        self.ui.tblCountryTax.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblCountryTax.doubleClicked.connect(self._on_edit_clicked)
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
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def refresh(self) -> None:
        search_text = self.ui.txtSearch.text().strip() or None
        status = status_filter_value(self.ui.cmbStatusFilter.currentText())
        include_deleted = self.ui.chkShowDeleted.isChecked()

        try:
            rows, total = self._engine.search_taxes(
                search_text=search_text,
                status=status,
                include_deleted=include_deleted,
                page=1,
                page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load country tax list.")
            show_error(self, "Country Tax", f"Failed to load country tax settings: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.lblRecordCount.setText(f"{total} record(s) found")

    def _populate_table(self, rows: list[CountryTaxDTO]) -> None:
        table = self.ui.tblCountryTax
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            for col_index, value in enumerate(dto_to_table_row(dto)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.country_tax_id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        configure_table_columns(table, stretch_columns=(0, 1))
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[CountryTaxDTO]:
        selected_items = self.ui.tblCountryTax.selectedItems()
        if not selected_items:
            return None
        country_tax_id = selected_items[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.country_tax_id == country_tax_id:
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
        if self._embedded:
            self.form_requested.emit(None)
            return
        dialog = CountryTaxFormScreen(self, country_tax_id=None, engine=self._engine)
        if dialog.exec():
            self.refresh()
    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if self._embedded:
            self.form_requested.emit(dto.country_tax_id)
            return
        dialog = CountryTaxFormScreen(self, country_tax_id=dto.country_tax_id, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(
            self, "Delete Country Tax", f"Delete tax setting for '{dto.country}'?\n\nThis can be restored later."
        ):
            return
        try:
            self._engine.delete_tax(dto.country_tax_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Country Tax", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete country tax %s.", dto.country_tax_id)
            show_error(self, "Country Tax", f"Failed to delete: {exc}")
        else:
            show_success(self, "Country Tax", f"Country Tax for '{dto.country}' deleted.")
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_tax(dto.country_tax_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Country Tax", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore country tax %s.", dto.country_tax_id)
            show_error(self, "Country Tax", f"Failed to restore: {exc}")
        else:
            show_success(self, "Country Tax", f"Country Tax for '{restored.country}' restored.")
            self.refresh()

    def _on_close_clicked(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        self.close()


__all__ = ["CountryTaxListScreen"]
