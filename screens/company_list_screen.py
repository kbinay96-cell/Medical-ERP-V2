"""
screens/company_list_screen.py

Company Master list/search/filter screen - Medical ERP V2.
Mirrors screens/supplier_list_screen.py exactly.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableWidgetItem, QWidget

from engines.exceptions import RecordNotFoundError
from engines.company_engine import CompanyDTO, CompanyEngine
from screens.company_form_screen import CompanyFormScreen
from ui.ui_company_list import Ui_CompanyListWidget
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.company_form_helpers import dto_to_table_row, status_filter_value

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300


class CompanyListScreen(QWidget):
    """Company Master list/search/filter screen. Opens CompanyFormScreen for Add/Edit."""

    def __init__(self, parent: Optional[QWidget] = None, engine: Optional[CompanyEngine] = None) -> None:
        super().__init__(parent)
        self.ui = Ui_CompanyListWidget()
        self.ui.setupUi(self)

        self._engine = engine or CompanyEngine()
        self._rows: list[CompanyDTO] = []

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
        self.ui.tblCompany.itemSelectionChanged.connect(self._on_selection_changed)
        self.ui.tblCompany.doubleClicked.connect(self._on_edit_clicked)
        self.ui.btnAdd.clicked.connect(self._on_add_clicked)
        self.ui.btnEdit.clicked.connect(self._on_edit_clicked)
        self.ui.btnDelete.clicked.connect(self._on_delete_clicked)
        self.ui.btnRestore.clicked.connect(self._on_restore_clicked)
        self.ui.btnClose.clicked.connect(self._on_close_clicked)
        self.ui.btnExport.clicked.connect(self._on_export_clicked)
        self.ui.btnPrint.clicked.connect(self._on_print_clicked)

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
            rows, total = self._engine.search_companies(
                search_text=search_text,
                status=status,
                include_deleted=include_deleted,
                page=1,
                page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load company list.")
            show_error(self, "Company Master", f"Failed to load companies: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.lblRecordCount.setText(f"{total} company(s) found")

    def _populate_table(self, rows: list[CompanyDTO]) -> None:
        table = self.ui.tblCompany
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            for col_index, value in enumerate(dto_to_table_row(dto)):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.company_id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        table.setSortingEnabled(True)
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[CompanyDTO]:
        selected_items = self.ui.tblCompany.selectedItems()
        if not selected_items:
            return None
        company_id = selected_items[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.company_id == company_id:
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
        dialog = CompanyFormScreen(self, company_id=None, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = CompanyFormScreen(self, company_id=dto.company_id, engine=self._engine)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(
            self, "Delete Company", f"Delete company '{dto.company_name}'?\n\nThis can be restored later."
        ):
            return
        try:
            self._engine.delete_company(dto.company_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Company Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete company %s.", dto.company_id)
            show_error(self, "Company Master", f"Failed to delete company: {exc}")
        else:
            show_success(self, "Company Master", f"Company '{dto.company_name}' deleted.")
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_company(dto.company_id, current_user_id=get_current_user_id())
        except RecordNotFoundError as exc:
            show_error(self, "Company Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore company %s.", dto.company_id)
            show_error(self, "Company Master", f"Failed to restore company: {exc}")
        else:
            show_success(self, "Company Master", f"Company '{restored.company_name}' restored.")
            self.refresh()

    # ------------------------------------------------------------------ #
    # Export / Print
    # ------------------------------------------------------------------ #
    def _on_export_clicked(self) -> None:
        try:
            import openpyxl  # ASSUMPTION: add 'openpyxl' to requirements.txt if not already present
        except ImportError:
            show_error(self, "Company Master", "openpyxl is not installed. Run: pip install openpyxl")
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "companies.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Companies"
            ws.append(["Company ID", "Company Name", "Contact Person", "Mobile No.", "Phone No.", "Email", "Status"])
            for dto in self._rows:
                ws.append(dto_to_table_row(dto))
            wb.save(path)
            show_success(self, "Company Master", f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to export companies.")
            show_error(self, "Company Master", f"Failed to export: {exc}")

    def _on_print_clicked(self) -> None:
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QTextDocument, QPageLayout

            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageOrientation(QPageLayout.Landscape)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() != QPrintDialog.Accepted:
                return

            headers = ["Company ID", "Company Name", "Contact Person", "Mobile No.", "Phone No.", "Email", "Status"]
            html = "<h3>Company Master</h3><table border='1' cellspacing='0' cellpadding='4' width='100%'>"
            html += "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
            for dto in self._rows:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in dto_to_table_row(dto)) + "</tr>"
            html += "</table>"

            document = QTextDocument()
            document.setHtml(html)
            document.print_(printer)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to print companies.")
            show_error(self, "Company Master", f"Failed to print: {exc}")

    def _on_close_clicked(self) -> None:
        self.close()


__all__ = ["CompanyListScreen"]
