"""
screens/password_reset_requests_screen.py

Admin screen: review and approve/reject pending forgot-password
requests submitted via the WhatsApp deep-link flow. Programmatic
UI (no separate .ui file) — follows the embedded-dashboard-screen
pattern (embedded param + close_requested signal) used by
Company/Supplier/Manufacturer/Item/CountryTax list screens.
"""

from __future__ import annotations

import logging
import webbrowser
from urllib.parse import quote

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.password_reset_engine import approve_request, get_pending_requests, reject_request
from utils.integration_adapters import confirm, get_current_user_id, show_error, show_success

logger = logging.getLogger(__name__)

TABLE_HEADERS = ["Request ID", "Username", "Code", "Requested At", "Expires At"]


class PasswordResetRequestsScreen(QWidget):
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None, embedded: bool = False) -> None:
        super().__init__(parent)
        self._embedded = embedded
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)

        if self._embedded:
            back_row = QHBoxLayout()
            btn_back = QPushButton("← Back", self)
            btn_back.clicked.connect(self.close_requested.emit)
            back_row.addWidget(btn_back)
            back_row.addStretch()
            layout.addLayout(back_row)

        layout.addWidget(QLabel("Pending Password Reset Requests"))

        self.table = QTableWidget(0, len(TABLE_HEADERS), self)
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_approve = QPushButton("Approve", self)
        self.btn_reject = QPushButton("Reject", self)
        button_row.addWidget(self.btn_refresh)
        button_row.addStretch()
        button_row.addWidget(self.btn_approve)
        button_row.addWidget(self.btn_reject)
        layout.addLayout(button_row)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_approve.clicked.connect(self._on_approve_clicked)
        self.btn_reject.clicked.connect(self._on_reject_clicked)

        self.refresh()

    def refresh(self) -> None:
        try:
            self._rows = get_pending_requests()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load password reset requests.")
            show_error(self, "Password Reset Requests", f"Failed to load requests: {exc}")
            return

        self.table.setRowCount(0)
        for row in self._rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row["requestid"])))
            self.table.setItem(r, 1, QTableWidgetItem(row["username"]))
            self.table.setItem(r, 2, QTableWidgetItem(row["requestcode"]))
            self.table.setItem(r, 3, QTableWidgetItem(str(row["createdat"])))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["expiresat"])))

    def _selected_request_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return self._rows[selected[0].row()]["requestid"]

    def _on_approve_clicked(self) -> None:
        request_id = self._selected_request_id()
        if request_id is None:
            show_error(self, "Password Reset Requests", "Select a request first.")
            return
        if not confirm(self, "Approve Reset", "Confirm you received this code on WhatsApp and want to approve it?"):
            return

        try:
            temp_password, phone = approve_request(request_id, str(get_current_user_id()))
        except (RecordNotFoundError, ValidationError) as exc:
            show_error(self, "Password Reset Requests", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to approve reset request %s.", request_id)
            show_error(self, "Password Reset Requests", f"Failed to approve: {exc}")
            return

        message = (
            f"Your password has been reset. Temporary password: {temp_password}\n"
            "Please log in and change it immediately."
        )

        if phone:
            digits_only = "".join(ch for ch in phone if ch.isdigit())
            webbrowser.open(f"whatsapp://send?phone={digits_only}&text={quote(message)}")
            show_success(
                self, "Password Reset Requests",
                f"Approved. Temporary password: {temp_password}\n"
                "WhatsApp has been opened with this pre-filled — click Send to deliver it.",
            )
        else:
            show_success(
                self, "Password Reset Requests",
                f"Approved. Temporary password: {temp_password}\n"
                "No phone number on file for this user — please relay it manually.",
            )
        self.refresh()

    def _on_reject_clicked(self) -> None:
        request_id = self._selected_request_id()
        if request_id is None:
            show_error(self, "Password Reset Requests", "Select a request first.")
            return

        try:
            reject_request(request_id, str(get_current_user_id()))
        except RecordNotFoundError as exc:
            show_error(self, "Password Reset Requests", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to reject reset request %s.", request_id)
            show_error(self, "Password Reset Requests", f"Failed to reject: {exc}")
            return

        show_success(self, "Password Reset Requests", "Request rejected.")
        self.refresh()


__all__ = ["PasswordResetRequestsScreen"]