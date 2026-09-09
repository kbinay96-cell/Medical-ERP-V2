"""
screens/audit_log_screen.py

Admin screen: browse the four audit/history tables (Security
Events, Login History, Failed Logins, User Activity) with
username + date-range filters. Programmatic UI, no .ui file --
follows the embedded-dashboard-screen pattern (embedded param +
close_requested signal) established by PasswordResetRequestsScreen.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDateEdit, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from models import audit_log_model

logger = logging.getLogger(__name__)


class _AuditTableTab(QWidget):
    """columns: list of (display_label, dict_key) tuples."""

    def __init__(self, fetch_fn, columns: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self._fetch_fn = fetch_fn
        self._columns = columns

        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Username:"))
        self.input_username = QLineEdit(self)
        self.input_username.setPlaceholderText("filter by username")
        filter_row.addWidget(self.input_username)

        filter_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit(self)
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit(self)
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_row.addWidget(self.date_to)

        self.btn_refresh = QPushButton("Refresh", self)
        filter_row.addWidget(self.btn_refresh)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        labels = [label for label, _ in columns]
        self.table = QTableWidget(0, len(labels), self)
        self.table.setHorizontalHeaderLabels(labels)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        username = self.input_username.text().strip() or None
        start_date = datetime.combine(self.date_from.date().toPython(), datetime.min.time())
        end_date = datetime.combine(self.date_to.date().toPython(), datetime.max.time())

        try:
            rows = self._fetch_fn(username=username, start_date=start_date, end_date=end_date)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load audit data.")
            rows = []

        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for col_index, (_, key) in enumerate(self._columns):
                value = row.get(key, "")
                self.table.setItem(r, col_index, QTableWidgetItem(str(value) if value is not None else ""))


class AuditLogScreen(QWidget):
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None, embedded: bool = False) -> None:
        super().__init__(parent)
        self._embedded = embedded

        layout = QVBoxLayout(self)

        if self._embedded:
            back_row = QHBoxLayout()
            btn_back = QPushButton("← Back", self)
            btn_back.clicked.connect(self.close_requested.emit)
            back_row.addWidget(btn_back)
            back_row.addStretch()
            layout.addLayout(back_row)

        layout.addWidget(QLabel("Audit Log"))

        tabs = QTabWidget(self)
        layout.addWidget(tabs)

        tabs.addTab(
            _AuditTableTab(
                audit_log_model.get_audit_log,
                [("Date", "createdat"), ("Username", "username"), ("Action", "action"), ("Details", "details")],
                self,
            ),
            "Security Events",
        )
        tabs.addTab(
            _AuditTableTab(
                audit_log_model.get_login_history,
                [("Login Time", "logintime"), ("Username", "username"), ("Logout Time", "logouttime"),
                 ("Machine", "machinename"), ("Session", "sessionid")],
                self,
            ),
            "Login History",
        )
        tabs.addTab(
            _AuditTableTab(
                audit_log_model.get_failed_login_history,
                [("Date", "attemptdate"), ("Username", "username"), ("Machine", "machinename"), ("Reason", "failurereason")],
                self,
            ),
            "Failed Logins",
        )
        tabs.addTab(
            _AuditTableTab(
                audit_log_model.get_user_audit_log,
                [("Date", "actionat"), ("Action", "action"), ("Performed By", "performedby"), ("Remarks", "remarks")],
                self,
            ),
            "User Activity",
        )


__all__ = ["AuditLogScreen"]