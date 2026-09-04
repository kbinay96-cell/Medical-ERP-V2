"""
screens/receipt_audit_log_dialog.py

Receipt Audit Log Dialog (read-only) - Medical ERP V2

Responsibility (and ONLY this):
    Show the full edit history of a single Receipt by calling
    ReceiptEngine.get_audit_log(receipt_id) and rendering it as a
    read-only table: Changed Field | Old Value | New Value | Changed By
    | Changed At (BS).

No SQL. No business logic. No mutation of any kind happens from this
dialog -- it is a pure viewer.

Verified against the real repo during Receipt Part 3 wiring:
get_audit_log(receipt_id) -> list[dict] with changed_field, old_value,
new_value, changed_by, changed_at_bs (plus extra changed_at_ad/receipt_id/
receipt_audit_log_id keys, which this dialog simply ignores) -- this
matched the original assumption exactly, no logic change needed. The
only correction is the exceptions import path below (engines.exceptions,
not utils.exceptions, which doesn't exist in the real repo).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.message import show_error
from engines.exceptions import ValidationError

if TYPE_CHECKING:
    from engines.receipt_engine import ReceiptEngine

logger = logging.getLogger(__name__)

_COLUMN_HEADERS = ["Changed Field", "Old Value", "New Value", "Changed By", "Changed At (BS)"]


class ReceiptAuditLogDialog(QDialog):
    """Read-only viewer for a Receipt's audit_log entries.

    Args:
        parent: Parent widget (typically ReceiptListScreen).
        engine: The shared ReceiptEngine instance.
        receipt_id: The Receipt whose history is being viewed.
    """

    def __init__(self, parent: Optional[QWidget], engine: "ReceiptEngine", receipt_id: int) -> None:
        super().__init__(parent)
        self._engine = engine
        self._receipt_id = receipt_id

        self.setObjectName("dlgReceiptAuditLog")
        self.setWindowTitle(f"Receipt Audit Log - #{receipt_id}")
        self.setModal(True)
        self.resize(760, 420)

        self._build_ui()
        self._load_audit_log()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.lblTitle = QLabel(f"Edit History for Receipt #{self._receipt_id}")
        self.lblTitle.setObjectName("lblAuditLogTitle")
        self.lblTitle.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(self.lblTitle)

        self.tblAuditLog = QTableWidget(0, len(_COLUMN_HEADERS), self)
        self.tblAuditLog.setObjectName("tblAuditLog")
        self.tblAuditLog.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.tblAuditLog.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblAuditLog.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tblAuditLog.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tblAuditLog.setAlternatingRowColors(True)
        self.tblAuditLog.verticalHeader().setVisible(False)
        header = self.tblAuditLog.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tblAuditLog, stretch=1)

        self.lblEmptyState = QLabel("No changes have been recorded for this receipt yet.")
        self.lblEmptyState.setObjectName("lblAuditLogEmpty")
        self.lblEmptyState.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblEmptyState.setVisible(False)
        layout.addWidget(self.lblEmptyState)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.btnClose = QPushButton("Close", self)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnClose.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btnClose.clicked.connect(self.accept)
        footer.addWidget(self.btnClose)
        layout.addLayout(footer)

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def _load_audit_log(self) -> None:
        try:
            entries = self._engine.get_audit_log(self._receipt_id)
        except ValidationError as exc:
            show_error(str(exc))
            self.reject()
            return
        except Exception:  # noqa: BLE001 - surface as a friendly message, never a traceback
            logger.exception("Unexpected error loading audit log for receipt_id=%s", self._receipt_id)
            show_error("Could not load the audit log for this receipt. Please try again.")
            self.reject()
            return

        if not entries:
            self.tblAuditLog.setVisible(False)
            self.lblEmptyState.setVisible(True)
            return

        self.tblAuditLog.setVisible(True)
        self.lblEmptyState.setVisible(False)
        self.tblAuditLog.setRowCount(len(entries))

        for row_index, entry in enumerate(entries):
            self._set_cell(row_index, 0, entry.get("changed_field", ""))
            self._set_cell(row_index, 1, entry.get("old_value", ""))
            self._set_cell(row_index, 2, entry.get("new_value", ""))
            self._set_cell(row_index, 3, entry.get("changed_by", ""))
            self._set_cell(row_index, 4, entry.get("changed_at_bs", ""))

    def _set_cell(self, row: int, column: int, value: object) -> None:
        text = "" if value is None else str(value)
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tblAuditLog.setItem(row, column, item)