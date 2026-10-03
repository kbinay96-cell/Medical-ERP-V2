from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.chart_of_accounts_model import ChartOfAccountsModel
from engines import customer_engine
from engines.supplier_engine import SupplierEngine


class AccountLedgerScreen(QWidget):
    """General ledger view with client-side running balance presentation."""
    close_requested = Signal()

    def __init__(self, parent, engine, coa_model: ChartOfAccountsModel):
        super().__init__(parent)
        self._engine = engine
        self._coa_model = coa_model
        self._accounts: dict[int, dict] = {}
        self._supplier_engine = SupplierEngine()
        root = QVBoxLayout(self)
        from utils.ui_standards import add_embedded_back_button
        add_embedded_back_button(self, root, self.close_requested.emit)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        filters.addWidget(self.account_combo, 2)
        filters.addWidget(QLabel("Sub-ledger:"))
        self.sub_ledger_type = QComboBox()
        self.sub_ledger_type.addItems(["", "Customer", "Supplier"])
        self.sub_ledger_type.setEnabled(False)
        self.sub_ledger_id = QComboBox()
        self.sub_ledger_id.addItem("All sub-ledgers", None)
        self.sub_ledger_id.setEnabled(False)
        filters.addWidget(self.sub_ledger_type)
        filters.addWidget(self.sub_ledger_id)
        self.use_dates = QCheckBox("Date range")
        self.date_from = QDateEdit()
        self.date_to = QDateEdit()
        for edit in (self.date_from, self.date_to):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setDate(date.today())
            edit.setEnabled(False)
        filters.addWidget(self.use_dates)
        filters.addWidget(self.date_from)
        filters.addWidget(self.date_to)
        self.load_button = QPushButton("Load Ledger")
        filters.addWidget(self.load_button)
        root.addLayout(filters)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Journal No.", "Narration", "Debit", "Credit", "Balance"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        self.account_combo.currentIndexChanged.connect(self._on_account_selected)
        self.sub_ledger_type.currentIndexChanged.connect(self._populate_subledgers)
        self.use_dates.toggled.connect(self._toggle_dates)
        self.load_button.clicked.connect(self._on_search_clicked)
        try:
            for account in self._coa_model.get_hierarchy():
                account_id = int(account["account_id"])
                self._accounts[account_id] = account
                self.account_combo.addItem(
                    f"{account.get('account_code')} — {account.get('account_name')}", account_id
                )
        except Exception as exc:
            QMessageBox.critical(self, "Account Ledger", f"Could not load accounts:\n{exc}")

    def _toggle_dates(self, enabled: bool) -> None:
        self.date_from.setEnabled(enabled)
        self.date_to.setEnabled(enabled)

    def _on_account_selected(self, _account_id: int) -> None:
        account_id = self.account_combo.currentData()
        account = self._accounts.get(account_id)
        enabled = bool(account and account.get("is_control_account"))
        self.sub_ledger_type.setEnabled(enabled)
        self.sub_ledger_id.setEnabled(enabled)
        if not enabled:
            self.sub_ledger_type.setCurrentIndex(0)
            self.sub_ledger_id.clear()
            self.sub_ledger_id.addItem("All sub-ledgers", None)

    def _populate_subledgers(self, _index=None) -> None:
        self.sub_ledger_id.clear()
        self.sub_ledger_id.addItem("All sub-ledgers", None)
        sub_type = self.sub_ledger_type.currentText()
        if sub_type == "Customer":
            for record in customer_engine.get_active_customers():
                self.sub_ledger_id.addItem(
                    str(record.get("customer_name") or record.get("customer_code") or record.get("customer_id")),
                    record.get("customer_id"),
                )
        elif sub_type == "Supplier":
            for record in self._supplier_engine.get_active_suppliers():
                self.sub_ledger_id.addItem(
                    str(getattr(record, "supplier_name", "") or getattr(record, "supplier_code", "")),
                    getattr(record, "supplier_id", None),
                )

    def _on_search_clicked(self) -> None:
        account_id = self.account_combo.currentData()
        if account_id is None:
            QMessageBox.warning(self, "Account Ledger", "Select an account.")
            return
        account = self._accounts[int(account_id)]
        try:
            rows = self._engine.get_account_ledger(
                int(account_id),
                sub_ledger_type=self.sub_ledger_type.currentText() or None,
                sub_ledger_id=self.sub_ledger_id.currentData(),
                date_from_ad=self.date_from.date().toPython() if self.use_dates.isChecked() else None,
                date_to_ad=self.date_to.date().toPython() if self.use_dates.isChecked() else None,
            )
            self._render_running_balance(rows, str(account.get("normal_balance") or "Debit"))
        except Exception as exc:
            QMessageBox.critical(self, "Account Ledger", f"Could not load ledger:\n{exc}")

    def _render_running_balance(self, ledger_rows: list[dict], normal_balance: str) -> None:
        self.table.setRowCount(0)
        balance = 0.0
        debit_normal = normal_balance.casefold() == "debit"
        for entry in ledger_rows:
            debit = float(entry.get("debit_amount") or 0)
            credit = float(entry.get("credit_amount") or 0)
            balance += debit - credit if debit_normal else credit - debit
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                entry.get("journal_date_ad") or "",
                entry.get("journal_number") or "",
                entry.get("line_narration") or entry.get("narration") or "",
                f"{debit:,.2f}",
                f"{credit:,.2f}",
                f"{balance:,.2f}",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
