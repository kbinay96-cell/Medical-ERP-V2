from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.chart_of_accounts_model import ChartOfAccountsModel
from models.journal_model import JournalSearchFilters
from utils.integration_adapters import get_current_user_id
from screens.journal_voucher_form_screen import JournalVoucherFormScreen


def _value(row, key, default=""):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


class JournalListScreen(QWidget):
    """Search, inspect, reverse and cancel journal entries."""
    close_requested = Signal()

    def __init__(self, parent, engine, coa_model: ChartOfAccountsModel | None = None):
        super().__init__(parent)
        self._engine = engine
        self._coa_model = coa_model or getattr(engine, "_coa_model", None)
        self._visible_ids: list[int] = []
        root = QVBoxLayout(self)
        from utils.ui_standards import add_embedded_back_button
        add_embedded_back_button(self, root, self.close_requested.emit)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Source:"))
        self.source_filter = QComboBox()
        self.source_filter.addItems([
            "All", "Manual", "Sale Invoice", "Purchase Invoice", "Sale Return",
            "Purchase Return", "Receipt", "Payment", "Opening Balance",
        ])
        filters.addWidget(self.source_filter)
        filters.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Posted", "Draft", "Reversed", "Cancelled"])
        filters.addWidget(self.status_filter)
        self.from_date = QDateEdit()
        self.to_date = QDateEdit()
        for edit in (self.from_date, self.to_date):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setDate(date.today())
            edit.setEnabled(False)
        self.use_date_range = QComboBox()
        self.use_date_range.addItems(["All dates", "Use date range"])
        self.use_date_range.currentIndexChanged.connect(self._toggle_dates)
        filters.addWidget(self.use_date_range)
        filters.addWidget(QLabel("From"))
        filters.addWidget(self.from_date)
        filters.addWidget(QLabel("To"))
        filters.addWidget(self.to_date)
        self.account_filter = QComboBox()
        self.account_filter.addItem("All accounts", None)
        if self._coa_model:
            try:
                for account in self._coa_model.get_hierarchy():
                    self.account_filter.addItem(
                        f"{account.get('account_code')} — {account.get('account_name')}",
                        account.get("account_id"),
                    )
            except Exception as exc:
                QMessageBox.warning(self, "Journal List", f"Could not load account filter:\n{exc}")
        filters.addWidget(self.account_filter, 1)
        self.search_button = QPushButton("Search")
        self.new_button = QPushButton("+ New Voucher")
        filters.addWidget(self.search_button)
        filters.addWidget(self.new_button)
        root.addLayout(filters)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Journal", "Date", "Source", "Narration", "Status", "Entry ID"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.view_button = QPushButton("View")
        self.reverse_button = QPushButton("Reverse")
        self.cancel_button = QPushButton("Cancel manual journal")
        self.refresh_button = QPushButton("Refresh")
        for button in (self.view_button, self.reverse_button, self.cancel_button, self.refresh_button):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.search_button.clicked.connect(self.refresh)
        self.use_date_range.currentIndexChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.new_button.clicked.connect(self._new_voucher)
        self.view_button.clicked.connect(self._on_view_clicked)
        self.reverse_button.clicked.connect(self._on_reverse_clicked)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.refresh()

    def refresh(self) -> None:
        try:
            source = self.source_filter.currentText()
            status = self.status_filter.currentText()
            filters = JournalSearchFilters(
                source_document_type=None if source == "All" else source,
                status=None if status == "All" else status,
                date_from_ad=self.from_date.date().toPython() if self.use_date_range.currentIndex() else None,
                date_to_ad=self.to_date.date().toPython() if self.use_date_range.currentIndex() else None,
                page=1,
                page_size=500,
            )
            rows = self._engine.search(filters)
            account_id = self.account_filter.currentData()
            if account_id is not None:
                filtered = []
                for row in rows:
                    journal_id = _value(row, "journal_entry_id")
                    detail = self._engine.get_by_id(int(journal_id))
                    lines = _value(detail, "lines", []) if detail else []
                    if any(_value(line, "account_id") == account_id for line in lines):
                        filtered.append(row)
                rows = filtered
            self.table.setRowCount(0)
            self._visible_ids = []
            for journal in rows:
                journal_id = _value(journal, "journal_entry_id")
                if journal_id is None:
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [
                    _value(journal, "journal_number"),
                    _value(journal, "journal_date_bs") or str(_value(journal, "journal_date_ad")),
                    _value(journal, "source_document_type"),
                    _value(journal, "narration"),
                    _value(journal, "status"),
                    str(journal_id),
                ]
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(str(value or "")))
                self._visible_ids.append(int(journal_id))
            self._update_action_state()
        except Exception as exc:
            QMessageBox.critical(self, "Journal List", f"Could not load journals:\n{exc}")

    def _toggle_dates(self, index: int) -> None:
        self.from_date.setEnabled(bool(index))
        self.to_date.setEnabled(bool(index))

    def _selected_journal(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        try:
            journal_id = int(self.table.item(row, 5).text())
            return self._engine.get_by_id(journal_id)
        except Exception as exc:
            QMessageBox.critical(self, "Journal", str(exc))
            return None

    def _update_action_state(self) -> None:
        journal = self._selected_journal()
        status = _value(journal, "status") if journal else None
        source = _value(journal, "source_document_type") if journal else None
        self.view_button.setEnabled(journal is not None)
        self.reverse_button.setEnabled(status == "Posted")
        self.cancel_button.setVisible(source == "Manual")
        self.cancel_button.setEnabled(source == "Manual" and status in ("Draft", "Posted"))

    def _on_view_clicked(self) -> None:
        journal = self._selected_journal()
        if not journal:
            return
        lines = _value(journal, "lines", []) or []
        detail_lines = []
        for line in lines:
            detail_lines.append(
                f"{_value(line, 'account_code', '')} {_value(line, 'account_name', '')}   "
                f"Dr {_value(line, 'debit_amount', 0):,.2f} / Cr {_value(line, 'credit_amount', 0):,.2f}   "
                f"{_value(line, 'sub_ledger_type', '')} {_value(line, 'sub_ledger_id', '')}   "
                f"{_value(line, 'line_narration', '')}"
            )
        QMessageBox.information(
            self, str(_value(journal, "journal_number", "Journal")),
            f"{_value(journal, 'journal_date_bs', '')}\n{_value(journal, 'narration', '')}\n\n"
            + "\n".join(detail_lines),
        )

    def _reason(self, title: str) -> str | None:
        reason, accepted = QInputDialog.getText(self, title, "Reason (required):")
        reason = reason.strip()
        if not accepted:
            return None
        if not reason:
            QMessageBox.warning(self, title, "A reason is required.")
            return None
        return reason

    def _on_reverse_clicked(self) -> None:
        journal = self._selected_journal()
        if not journal:
            return
        reason = self._reason("Reverse Journal")
        if reason is None:
            return
        try:
            self._engine.reverse_journal(
                int(_value(journal, "journal_entry_id")), reason, get_current_user_id()
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Reverse Journal", str(exc))

    def _on_cancel_clicked(self) -> None:
        journal = self._selected_journal()
        if not journal or _value(journal, "source_document_type") != "Manual":
            return
        if _value(journal, "status") not in ("Draft", "Posted"):
            return
        reason = self._reason("Cancel Manual Journal")
        if reason is None:
            return
        try:
            self._engine.cancel_journal(
                int(_value(journal, "journal_entry_id")), reason, get_current_user_id()
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Cancel Manual Journal", str(exc))

    def _new_voucher(self) -> None:
        dialog = JournalVoucherFormScreen(self, self._engine, self._coa_model)
        if dialog.exec():
            self.refresh()
