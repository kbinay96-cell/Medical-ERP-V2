"""
screens/user_list_screen.py

User Master list/search/filter screen - Medical ERP V2.
Mirrors screens/company_list_screen.py exactly.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QHeaderView, QWidget

from engines.exceptions import RecordNotFoundError
from engines.user_engine import UserDTO, UserEngine
from screens.user_form_screen import UserFormScreen
from screens.reset_password_screen import ResetPasswordScreen
from models import company_model, role_model
from ui.ui_user_list import Ui_UserListView
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success
from utils.ui_standards import configure_table_columns, install_detail_splitter, standardize_action_buttons
from utils.window_chrome import apply_standard_window_chrome
from widgets.master_detail_panel import MasterDetailPanel

logger = logging.getLogger(__name__)

SEARCH_DEBOUNCE_MS = 300

TABLE_HEADERS = ["User ID", "Username", "Full Name", "Email", "Phone", "Role", "Company", "Status"]


def _dto_to_table_row(dto: UserDTO) -> list[str]:
    return [
        str(dto.user_id),
        dto.username,
        dto.fullname,
        dto.email or "",
        dto.phone or "",
        str(dto.role_name or dto.role_id),
        str(dto.company_id or ""),
        dto.status,
    ]


def _status_filter_value(label: str) -> Optional[str]:
    if not label or label.strip().lower() == "all":
        return None
    return label.strip()


class UserListScreen(QWidget):
    """User Master list/search/filter screen. Opens UserFormScreen for Add/Edit."""

    def __init__(self, parent: Optional[QWidget] = None, engine: Optional[UserEngine] = None, current_user_id: Optional[int] = None) -> None:
        super().__init__(parent)
        self.ui = Ui_UserListView()
        self.ui.setupUi(self)
        apply_standard_window_chrome(self, width=1360, height=760)
        standardize_action_buttons(self)

        self._engine = engine or UserEngine()
        self._current_user_id = current_user_id
        self._rows: list[UserDTO] = []

        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self.refresh)

        self._table_model = QStandardItemModel(0, len(TABLE_HEADERS), self)
        self._table_model.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.ui.table_users.setModel(self._table_model)
        self.ui.table_users.setSelectionBehavior(self.ui.table_users.SelectionBehavior.SelectRows)
        self.ui.table_users.setSelectionMode(self.ui.table_users.SelectionMode.SingleSelection)
        self.ui.table_users.setEditTriggers(self.ui.table_users.EditTrigger.NoEditTriggers)
        self.ui.table_users.setAlternatingRowColors(True)
        self._configure_column_widths()
        self._detail = MasterDetailPanel(
            placeholder_title="Select a user",
            placeholder_icon="user.svg",
            field_captions=(
                "Username:", "Email:", "Phone:", "Role:", "Company:", "Status:",
                "Must change pwd:", "Failed attempts:", "Created:",
            ),
        )
        install_detail_splitter(self.ui.verticalLayout_root, self.ui.table_users, self._detail)
        self._load_filter_options()

        self._connect_signals()
        self._setup_shortcuts()
        self.refresh()

    def _configure_column_widths(self) -> None:
        """User ID / Username / Role / Status stay compact; Full Name and Email
        take up the remaining space. Fixes the previous default where every
        column (including Status) stretched unevenly."""
        header = self.ui.table_users.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(7, 110)
        header.setStretchLastSection(False)

    def _load_filter_options(self) -> None:
        self.ui.filter_role.clear()
        self.ui.filter_role.addItem("All Roles", None)
        for role in role_model.list_roles():
            self.ui.filter_role.addItem(role["rolename"], role["roleid"])

        self.ui.filter_company.clear()
        self.ui.filter_company.addItem("All Companies", None)
        for company in company_model.list_companies(status_filter="all"):
            self.ui.filter_company.addItem(company["companyname"], company["companyid"])

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.ui.search_input.textChanged.connect(self._on_search_text_changed)
        self.ui.filter_status.currentTextChanged.connect(self.refresh)
        self.ui.filter_role.currentIndexChanged.connect(self.refresh)
        self.ui.filter_company.currentIndexChanged.connect(self.refresh)
        self.ui.btn_refresh.clicked.connect(self.refresh)
        self.ui.table_users.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.ui.table_users.doubleClicked.connect(self._on_edit_clicked)
        self.ui.btn_new.clicked.connect(self._on_add_clicked)
        self.ui.btn_edit.clicked.connect(self._on_edit_clicked)
        self.ui.btn_delete.clicked.connect(self._on_delete_clicked)
        self.ui.btn_restore.clicked.connect(self._on_restore_clicked)
        self.ui.btn_toggle_active.clicked.connect(self._on_toggle_active_clicked)
        self.ui.btn_reset_password.clicked.connect(self._on_reset_password_clicked)
        self.ui.btn_export.clicked.connect(self._on_export_clicked)
        self.ui.btn_print.clicked.connect(self._on_print_clicked)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_add_clicked)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.ui.search_input.setFocus)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._on_delete_clicked)

    # ------------------------------------------------------------------ #
    # Search / Filter / Refresh
    # ------------------------------------------------------------------ #
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_debounce_timer.start(SEARCH_DEBOUNCE_MS)

    def refresh(self) -> None:
        search_text = self.ui.search_input.text().strip() or None
        status = _status_filter_value(self.ui.filter_status.currentText())
        role_id = self.ui.filter_role.currentData()
        company_id = self.ui.filter_company.currentData()
        include_deleted = status == "Deleted"

        try:
            rows, total = self._engine.search_users(
                search_text=search_text, status=status,
                role_id=role_id, company_id=company_id, include_deleted=include_deleted,
                page=1, page_size=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load user list.")
            show_error(self, "User Master", f"Failed to load users: {exc}")
            return

        self._rows = rows
        self._populate_table(rows)
        self.ui.status_bar.showMessage(f"{total} user(s) found")

    def _populate_table(self, rows: list[UserDTO]) -> None:
        self._table_model.setRowCount(0)
        for dto in rows:
            row_items = []
            for col_index, value in enumerate(_dto_to_table_row(dto)):
                item = QStandardItem(value)
                item.setEditable(False)
                if col_index in (0, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_index == 0:
                    item.setData(dto.user_id, Qt.UserRole)
                if not dto.is_active:
                    item.setForeground(Qt.gray)
                row_items.append(item)
            self._table_model.appendRow(row_items)
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection state -> button enablement
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[UserDTO]:
        selected_indexes = self.ui.table_users.selectionModel().selectedRows(0)
        if not selected_indexes:
            return None
        user_id = self._table_model.item(selected_indexes[0].row(), 0).data(Qt.UserRole)
        for dto in self._rows:
            if dto.user_id == user_id:
                return dto
        return None

    def _on_selection_changed(self) -> None:
        dto = self._selected_dto()
        has_selection = dto is not None
        is_deleted = bool(dto and dto.is_deleted)

        self.ui.btn_edit.setEnabled(has_selection and not is_deleted)
        self.ui.btn_delete.setEnabled(has_selection and not is_deleted)
        self.ui.btn_restore.setEnabled(has_selection and is_deleted)
        self.ui.btn_toggle_active.setEnabled(has_selection and not is_deleted)
        self.ui.btn_reset_password.setEnabled(has_selection and not is_deleted)

        if dto is None:
            self._detail.show_placeholder()
            return
        self._show_detail(dto)

    def _show_detail(self, dto: UserDTO) -> None:
        self._detail.set_photo(getattr(dto, "photo_path", None))
        self._detail.set_heading(dto.fullname or dto.username, f"ID {dto.user_id}")
        self._detail.set_field("Username:", dto.username or "-")
        self._detail.set_field("Email:", dto.email or "-")
        self._detail.set_field("Phone:", dto.phone or "-")
        self._detail.set_field("Role:", str(dto.role_name or dto.role_id or "-"))
        self._detail.set_field("Company:", str(dto.company_id or "-"))
        self._detail.set_field("Status:", dto.status or "-")
        self._detail.set_field("Must change pwd:", "Yes" if dto.must_change_password else "No")
        self._detail.set_field("Failed attempts:", str(dto.failed_attempts))
        created = dto.created_date
        created_text = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else (str(created) if created else "-")
        self._detail.set_field("Created:", f"{dto.created_by or '-'}\n{created_text}")

    # ------------------------------------------------------------------ #
    # CRUD actions
    # ------------------------------------------------------------------ #
    def _on_add_clicked(self) -> None:
        dialog = UserFormScreen(self, user_id=None, engine=self._engine, current_user_id=self._current_user_id)
        if dialog.exec():
            self.refresh()

    def _on_edit_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = UserFormScreen(self, user_id=dto.user_id, engine=self._engine, current_user_id=self._current_user_id)
        if dialog.exec():
            self.refresh()

    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        if not confirm(self, "Delete User", f"Delete user '{dto.username}'?\n\nThis can be restored later."):
            return
        try:
            self._engine.delete_user(dto.user_id, current_user_id=self._current_user_id)
        except RecordNotFoundError as exc:
            show_error(self, "User Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete user %s.", dto.user_id)
            show_error(self, "User Master", f"Failed to delete user: {exc}")
        else:
            show_success(self, "User Master", f"User '{dto.username}' deleted.")
            self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            restored = self._engine.restore_user(dto.user_id, current_user_id=self._current_user_id)
        except RecordNotFoundError as exc:
            show_error(self, "User Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore user %s.", dto.user_id)
            show_error(self, "User Master", f"Failed to restore user: {exc}")
        else:
            show_success(self, "User Master", f"User '{restored.username}' restored.")
            self.refresh()

    def _on_toggle_active_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        try:
            updated = self._engine.set_active_status(
                dto.user_id, is_active=not dto.is_active, current_user_id=self._current_user_id
            )
        except RecordNotFoundError as exc:
            show_error(self, "User Master", str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to toggle status for user %s.", dto.user_id)
            show_error(self, "User Master", f"Failed to change status: {exc}")
        else:
            show_success(self, "User Master", f"User '{updated.username}' status set to {updated.status}.")
            self.refresh()

    def _on_reset_password_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        dialog = ResetPasswordScreen(self, user_id=dto.user_id, username=dto.username, engine=self._engine, current_user_id=self._current_user_id)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # Export / Print
    # ------------------------------------------------------------------ #
    def _on_export_clicked(self) -> None:
        try:
            import openpyxl  # ASSUMPTION: add 'openpyxl' to requirements.txt if not already present
        except ImportError:
            show_error(self, "User Master", "openpyxl is not installed. Run: pip install openpyxl")
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "users.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Users"
            ws.append(TABLE_HEADERS)
            for dto in self._rows:
                ws.append(_dto_to_table_row(dto))
            wb.save(path)
            show_success(self, "User Master", f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to export users.")
            show_error(self, "User Master", f"Failed to export: {exc}")

    def _on_print_clicked(self) -> None:
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
            from PySide6.QtGui import QTextDocument, QPageLayout

            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageOrientation(QPageLayout.Landscape)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() != QPrintDialog.Accepted:
                return

            html = "<h3>User Master</h3><table border='1' cellspacing='0' cellpadding='4' width='100%'>"
            html += "<tr>" + "".join(f"<th>{h}</th>" for h in TABLE_HEADERS) + "</tr>"
            for dto in self._rows:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in _dto_to_table_row(dto)) + "</tr>"
            html += "</table>"

            document = QTextDocument()
            document.setHtml(html)
            document.print_(printer)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to print users.")
            show_error(self, "User Master", f"Failed to print: {exc}")


__all__ = ["UserListScreen"]
