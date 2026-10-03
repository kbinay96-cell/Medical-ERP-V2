from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.chart_of_accounts_model import ChartOfAccountsModel
from utils.integration_adapters import get_current_user_id


def _signed_ledger_amount(row: dict) -> float:
    if row.get("ledger_amount") is not None:
        return float(row["ledger_amount"])
    if row.get("amount") is not None:
        return float(row["amount"])
    return float(row.get("debit_amount") or 0) - float(row.get("credit_amount") or 0)


class _ReconcileDialog(QDialog):
    def __init__(self, ledger_amount: float, parent=None):
        super().__init__(parent)
        self.ledger_amount = ledger_amount
        self.setWindowTitle("Reconcile Bank Entry")
        form = QFormLayout(self)
        self.reference = QLineEdit()
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setDate(date.today())
        self.statement_amount = QDoubleSpinBox()
        self.statement_amount.setRange(-999_999_999_999, 999_999_999_999)
        self.statement_amount.setDecimals(2)
        self.difference = QLabel("0.00")
        form.addRow("Bank statement reference", self.reference)
        form.addRow("Reconciled date", self.date)
        form.addRow("Statement amount", self.statement_amount)
        form.addRow("Ledger amount", QLabel(f"{ledger_amount:,.2f}"))
        form.addRow("Difference", self.difference)
        self.statement_amount.valueChanged.connect(self._update_difference)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _update_difference(self, statement_amount: float) -> None:
        self.difference.setText(f"{statement_amount - self.ledger_amount:,.2f}")

    def payload(self):
        return (
            self.reference.text().strip(),
            self.date.date().toPython(),
            self.statement_amount.value() - self.ledger_amount,
        )


class BankReconciliationScreen(QWidget):
    """Review unreconciled bank journal lines and mark reconciled through the model."""
    close_requested = Signal()

    def __init__(self, parent, bank_recon_model, coa_model: ChartOfAccountsModel):
        super().__init__(parent)
        self._bank_recon_model = bank_recon_model
        self._coa_model = coa_model
        self._rows: list[dict] = []
        root = QVBoxLayout(self)
        from utils.ui_standards import add_embedded_back_button
        add_embedded_back_button(self, root, self.close_requested.emit)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Bank account:"))
        self.account_combo = QComboBox()
        filters.addWidget(self.account_combo, 1)
        self.load_button = QPushButton("Load unreconciled")
        filters.addWidget(self.load_button)
        self.reconcile_button = QPushButton("Reconcile selected")
        filters.addWidget(self.reconcile_button)
        root.addLayout(filters)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Journal", "Date", "Narration", "Ledger amount", "Recon ID", "Journal line ID",
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setColumnHidden(4, True)
        self.table.setColumnHidden(5, True)
        root.addWidget(self.table, 1)
        self.load_button.clicked.connect(self._on_account_selected)
        self.account_combo.currentIndexChanged.connect(self._on_account_selected)
        self.reconcile_button.clicked.connect(self._on_reconcile_clicked)
        try:
            for account in self._coa_model.get_hierarchy():
                code = str(account.get("account_code") or "")
                if code.startswith("12"):
                    self.account_combo.addItem(
                        f"{code} — {account.get('account_name')}", account.get("account_id")
                    )
        except Exception as exc:
            QMessageBox.critical(self, "Bank Reconciliation", f"Could not load bank accounts:\n{exc}")

    def _on_account_selected(self, _account_id=None) -> None:
        account_id = self.account_combo.currentData()
        self._rows = []
        self.table.setRowCount(0)
        if account_id is None:
            return
        try:
            self._rows = self._bank_recon_model.get_unreconciled(int(account_id)) or []
            for entry in self._rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [
                    entry.get("journal_number") or "",
                    entry.get("journal_date_ad") or "",
                    entry.get("narration") or entry.get("line_narration") or "",
                    f"{_signed_ledger_amount(entry):,.2f}",
                    str(entry.get("bank_reconciliation_id") or ""),
                    str(entry.get("journal_entry_line_id") or ""),
                ]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(str(value)))
        except Exception as exc:
            QMessageBox.critical(self, "Bank Reconciliation", f"Could not load entries:\n{exc}")

    def _on_reconcile_clicked(self, bank_reconciliation_id: int | None = None) -> None:
        row_index = self.table.currentRow()
        if row_index < 0:
            QMessageBox.information(self, "Reconcile", "Select an unreconciled entry.")
            return
        try:
            entry = self._rows[row_index]
            recon_id = bank_reconciliation_id or int(entry["bank_reconciliation_id"])
            ledger_amount = _signed_ledger_amount(entry)
            dialog = _ReconcileDialog(ledger_amount, self)
            if dialog.exec() != QDialog.Accepted:
                return
            reference, reconciled_date, difference = dialog.payload()
            if not reference:
                raise ValueError("Bank statement reference is required.")
            self._bank_recon_model.mark_reconciled(
                bank_reconciliation_id=recon_id,
                bank_statement_reference=reference,
                reconciled_date_ad=reconciled_date,
                reconciled_by=get_current_user_id(),
                difference_amount=difference,
            )
            self._on_account_selected()
        except Exception as exc:
            QMessageBox.critical(self, "Reconcile Bank Entry", str(exc))
