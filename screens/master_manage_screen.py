"""
screens/master_manage_screen.py

Generic Lookup Master Management Dialog - Medical ERP V2

Fills the gap Item Master Part 1/2 left open: there was a generic
SimpleMasterEngine/Model/Validator for Category, Sub Category, Item Group,
Manufacturer, Unit, Generic, and Tax Master -- but no screen to actually
add/edit/remove rows in any of them. Rather than writing seven near-
identical management screens, ONE generic dialog drives all seven (same
"No Duplicate Logic" reasoning already used for the Model/Engine/Validator
layers), configured by the same `MasterTableConfig` + `SimpleMasterEngine`
pair the rest of the module already uses.

Responsibilities (and ONLY these, per "No SQL. No business logic."):
    - List / search / status-filter / show-deleted toggle
    - Add / Edit inline form (Code, Name, Remarks, Status)
    - Soft Delete / Restore
    - For scoped tables (Sub Category, scoped by Category), a required
      parent-scope selector drives both the list filter and the save payload

Everything else -- uniqueness, mandatory fields, defaults -- is decided by
the injected SimpleMasterEngine/Validator, exactly like every other screen
in this codebase.

SESSION MANAGER: `current_user_id` is a required constructor parameter,
same contract as every other screen here -- this dialog does not look it
up itself.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from engines.simple_master_engine import MasterDTO, SimpleMasterEngine
from utils.combo_helpers import make_searchable

logger = logging.getLogger(__name__)


class MasterManageDialog(QDialog):
    """
    Generic Add/Edit/Delete/Restore dialog for one simple lookup master.

    `engine` must be a SimpleMasterEngine instance for the table being
    managed (e.g. `category_engine()`, `manufacturer_engine()`, ...).

    `scope_engine` + `scope_label` are only needed for a scoped table like
    Sub Category (scoped by Category): pass the PARENT's SimpleMasterEngine
    (e.g. `category_engine()`) and a label ("Category"). The dialog then
    shows a mandatory parent-selector combo, uses it to filter the list,
    and includes it in every save/uniqueness check via `scope_id`.
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: SimpleMasterEngine,
        entity_label: str,
        current_user_id: int,
        scope_engine: Optional[SimpleMasterEngine] = None,
        scope_label: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        if current_user_id is None:
            raise ValueError(
                "MasterManageDialog requires current_user_id explicitly -- it "
                "does not look this up itself."
            )
        self._engine = engine
        self._entity_label = entity_label
        self._current_user_id = current_user_id
        self._scope_engine = scope_engine
        self._scope_label = scope_label
        self._is_scoped = scope_engine is not None

        self._rows: list[MasterDTO] = []
        self._selected_id: Optional[int] = None

        self.setWindowTitle(f"Manage {entity_label}")
        self.resize(640, 480)
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

        if self._is_scoped:
            self._populate_scope_combo()
        self.refresh()

    # ------------------------------------------------------------------ #
    # UI construction (no .ui file -- this dialog is new, built directly)
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # -- Filter row -----------------------------------------------------
        filter_row = QHBoxLayout()
        if self._is_scoped:
            filter_row.addWidget(QLabel(f"{self._scope_label}:"))
            self.cmbScope = QComboBox()
            filter_row.addWidget(self.cmbScope, 2)
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText(f"Search {self._entity_label}...")
        filter_row.addWidget(self.txtSearch, 3)
        self.chkShowDeleted = QCheckBox("Show Deleted")
        filter_row.addWidget(self.chkShowDeleted)
        root.addLayout(filter_row)

        # -- Table ------------------------------------------------------------
        self.tblMaster = QTableWidget(0, 4)
        self.tblMaster.setHorizontalHeaderLabels(["Code", "Name", "Status", "Remarks"])
        self.tblMaster.setSelectionBehavior(QTableWidget.SelectRows)
        self.tblMaster.setSelectionMode(QTableWidget.SingleSelection)
        self.tblMaster.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tblMaster.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.tblMaster, 1)

        # -- Inline Add/Edit form -----------------------------------------
        form_row1 = QHBoxLayout()
        form_row1.addWidget(QLabel("Code:"))
        self.txtCode = QLineEdit()
        form_row1.addWidget(self.txtCode, 1)
        form_row1.addWidget(QLabel("Name:"))
        self.txtName = QLineEdit()
        form_row1.addWidget(self.txtName, 2)
        form_row1.addWidget(QLabel("Status:"))
        self.cmbStatus = QComboBox()
        self.cmbStatus.addItems(["Active", "Inactive"])
        form_row1.addWidget(self.cmbStatus)
        root.addLayout(form_row1)

        form_row2 = QHBoxLayout()
        form_row2.addWidget(QLabel("Remarks:"))
        self.txtRemarks = QPlainTextEdit()
        self.txtRemarks.setMaximumHeight(50)
        form_row2.addWidget(self.txtRemarks)
        root.addLayout(form_row2)

        self.lblValidationMessage = QLabel("")
        self.lblValidationMessage.setStyleSheet("color: #b00020;")
        root.addWidget(self.lblValidationMessage)

        # -- Buttons ------------------------------------------------------
        btn_row = QHBoxLayout()
        self.btnSave = QPushButton("Save")
        self.btnUpdate = QPushButton("Update")
        self.btnClear = QPushButton("Clear")
        self.btnDelete = QPushButton("Delete")
        self.btnRestore = QPushButton("Restore")
        self.btnClose = QPushButton("Close")
        for b in (self.btnSave, self.btnUpdate, self.btnClear, self.btnDelete, self.btnRestore, self.btnClose):
            btn_row.addWidget(b)
        root.addLayout(btn_row)

        self._set_form_mode(editing=False)

    def _connect_signals(self) -> None:
        self.txtSearch.textChanged.connect(self.refresh)
        self.chkShowDeleted.toggled.connect(self.refresh)
        if self._is_scoped:
            self.cmbScope.currentIndexChanged.connect(self.refresh)
        self.tblMaster.itemSelectionChanged.connect(self._on_selection_changed)
        self.btnSave.clicked.connect(self._on_save_clicked)
        self.btnUpdate.clicked.connect(self._on_save_clicked)
        self.btnClear.clicked.connect(self._on_clear_clicked)
        self.btnDelete.clicked.connect(self._on_delete_clicked)
        self.btnRestore.clicked.connect(self._on_restore_clicked)
        self.btnClose.clicked.connect(self.accept)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save_clicked)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.accept)

    # ------------------------------------------------------------------ #
    # Scope (parent) combo -- Sub Category's Category selector, etc.
    # ------------------------------------------------------------------ #
    def _populate_scope_combo(self) -> None:
        self.cmbScope.clear()
        for dto in self._scope_engine.list_active():
            self.cmbScope.addItem(dto.name, dto.id)
        make_searchable(self.cmbScope)

    def _current_scope_id(self) -> Optional[int]:
        if not self._is_scoped:
            return None
        return self.cmbScope.currentData()

    # ------------------------------------------------------------------ #
    # List / refresh
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        if self._is_scoped and self._current_scope_id() is None:
            self._rows = []
            self._populate_table([])
            return
        search_text = self.txtSearch.text().strip() or None
        include_deleted = self.chkShowDeleted.isChecked()
        rows = self._engine.search(search_text=search_text, include_deleted=include_deleted)
        if self._is_scoped:
            scope_id = self._current_scope_id()
            rows = [r for r in rows if r.extra.get(self._scope_extra_key()) == scope_id]
        self._rows = rows
        self._populate_table(rows)

    def _scope_extra_key(self) -> str:
        # Sub Category's extra_columns includes "category_id" -- this is the
        # only scoped table today, so this is a small, explicit mapping
        # rather than a guess based on scope_label.
        return "category_id"

    def _populate_table(self, rows: list[MasterDTO]) -> None:
        table = self.tblMaster
        table.setRowCount(0)
        for row_index, dto in enumerate(rows):
            table.insertRow(row_index)
            values = [dto.code or "", dto.name or "", "Deleted" if dto.is_deleted else dto.status, dto.remarks or ""]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, dto.id)
                if dto.is_deleted:
                    item.setForeground(Qt.gray)
                table.setItem(row_index, col_index, item)
        self._on_selection_changed()

    # ------------------------------------------------------------------ #
    # Selection -> form + button state
    # ------------------------------------------------------------------ #
    def _selected_dto(self) -> Optional[MasterDTO]:
        selected = self.tblMaster.selectedItems()
        if not selected:
            return None
        record_id = selected[0].data(Qt.UserRole)
        for dto in self._rows:
            if dto.id == record_id:
                return dto
        return None

    def _on_selection_changed(self) -> None:
        dto = self._selected_dto()
        if dto is None:
            self.btnDelete.setEnabled(False)
            self.btnRestore.setEnabled(False)
            return
        self._selected_id = dto.id
        self.txtCode.setText(dto.code or "")
        self.txtName.setText(dto.name or "")
        self.cmbStatus.setCurrentText(dto.status or "Active")
        self.txtRemarks.setPlainText(dto.remarks or "")
        self._set_form_mode(editing=not dto.is_deleted)
        self.btnDelete.setEnabled(not dto.is_deleted)
        self.btnRestore.setEnabled(dto.is_deleted)

    def _set_form_mode(self, editing: bool) -> None:
        """editing=True -> Update is the active save action; False -> Save (Add)."""
        self.btnSave.setEnabled(not editing)
        self.btnUpdate.setEnabled(editing)

    # ------------------------------------------------------------------ #
    # Add / Edit
    # ------------------------------------------------------------------ #
    def _on_clear_clicked(self) -> None:
        self._selected_id = None
        self.tblMaster.clearSelection()
        self.txtCode.clear()
        self.txtName.clear()
        self.cmbStatus.setCurrentText("Active")
        self.txtRemarks.clear()
        self.lblValidationMessage.setText("")
        self._set_form_mode(editing=False)
        self.txtName.setFocus()

    def _on_save_clicked(self) -> None:
        self.lblValidationMessage.setText("")

        if self._is_scoped and self._current_scope_id() is None:
            self.lblValidationMessage.setText(f"Select a {self._scope_label} first.")
            return

        payload = {
            "code": self.txtCode.text().strip(),
            "name": self.txtName.text().strip(),
            "status": self.cmbStatus.currentText(),
            "remarks": self.txtRemarks.toPlainText().strip(),
        }
        scope_id = self._current_scope_id()
        if self._is_scoped:
            payload[self._scope_extra_key()] = scope_id

        try:
            if self._selected_id is not None:
                self._engine.update(self._selected_id, payload, self._current_user_id, scope_id=scope_id)
            else:
                self._engine.create(payload, self._current_user_id, scope_id=scope_id)
        except ValidationError as exc:
            self.lblValidationMessage.setText("\n".join(exc.errors))
            return
        except DuplicateRecordError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except RecordNotFoundError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error saving %s.", self._entity_label)
            self.lblValidationMessage.setText(f"Unexpected error: {exc}")
            return

        self._on_clear_clicked()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Delete / Restore
    # ------------------------------------------------------------------ #
    def _on_delete_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or dto.is_deleted:
            return
        confirmed = QMessageBox.question(
            self, f"Delete {self._entity_label}",
            f"Delete '{dto.name}'?\n\nThis can be restored later.",
        ) == QMessageBox.Yes
        if not confirmed:
            return
        try:
            self._engine.delete(dto.id, self._current_user_id)
        except RecordNotFoundError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete %s %s.", self._entity_label, dto.id)
            self.lblValidationMessage.setText(f"Failed to delete: {exc}")
            return
        self._on_clear_clicked()
        self.refresh()

    def _on_restore_clicked(self) -> None:
        dto = self._selected_dto()
        if dto is None or not dto.is_deleted:
            return
        try:
            self._engine.restore(dto.id, self._current_user_id)
        except RecordNotFoundError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to restore %s %s.", self._entity_label, dto.id)
            self.lblValidationMessage.setText(f"Failed to restore: {exc}")
            return
        self._on_clear_clicked()
        self.refresh()


__all__ = ["MasterManageDialog"]
