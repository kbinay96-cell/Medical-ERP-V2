from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from engines.date_engine import bs_to_ad
from engines import customer_engine
from models.chart_of_accounts_model import ChartOfAccountsModel
from engines.supplier_engine import SupplierEngine
from utils.integration_adapters import get_current_user_id
from widgets.bs_calendar_date_picker import BSCalendarDatePicker


class JournalVoucherFormScreen(QDialog):
    """Manual journal entry dialog; posting/validation stay in AccountingEngine."""

    def __init__(self, parent, engine, coa_model: ChartOfAccountsModel):
        super().__init__(parent)
        self._engine = engine
        self._coa_model = coa_model
        self._accounts: list[dict] = []
        self._supplier_engine = SupplierEngine()
        self.setWindowTitle("New Journal Voucher")
        self.resize(1050, 560)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Journal date (BS):"))
        self.date_picker = BSCalendarDatePicker(self)
        header.addWidget(self.date_picker)
        header.addWidget(QLabel("Narration:"))
        self.narration = QLineEdit()
        self.narration.setPlaceholderText("Required journal description")
        header.addWidget(self.narration, 1)
        root.addLayout(header)
        actions = QHBoxLayout()
        self.add_row_button = QPushButton("Add line")
        self.remove_row_button = QPushButton("Remove selected line")
        actions.addWidget(self.add_row_button)
        actions.addWidget(self.remove_row_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Account", "Debit", "Credit", "Sub-ledger type", "Sub-ledger ID", "Line narration"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        self.totals = QLabel("Total debit: 0.00    Total credit: 0.00")
        root.addWidget(self.totals)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save_clicked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.add_row_button.clicked.connect(self._add_line_row)
        self.remove_row_button.clicked.connect(self._remove_line_row)
        try:
            self._accounts = self._coa_model.get_hierarchy()
            self._add_line_row()
            self._add_line_row()
        except Exception as exc:
            QMessageBox.critical(self, "Journal Voucher", f"Could not load accounts:\n{exc}")

    def _add_line_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        account = QComboBox()
        account.setEditable(True)
        account.addItem("-- Select account --", None)
        for item in self._accounts:
            account.addItem(
                f"{item.get('account_code', '')} — {item.get('account_name', '')}",
                item.get("account_id"),
            )
        debit = QDoubleSpinBox()
        credit = QDoubleSpinBox()
        for amount in (debit, credit):
            amount.setRange(0, 999_999_999_999)
            amount.setDecimals(2)
            amount.valueChanged.connect(self._update_totals_footer)
        sub_type = QComboBox()
        sub_type.addItems(["", "Customer", "Supplier"])
        sub_id = QComboBox()
        sub_id.addItem("-- Select customer/supplier --", None)
        sub_type.setEnabled(False)
        sub_id.setEnabled(False)
        narration = QLineEdit()
        self.table.setCellWidget(row, 0, account)
        self.table.setCellWidget(row, 1, debit)
        self.table.setCellWidget(row, 2, credit)
        self.table.setCellWidget(row, 3, sub_type)
        self.table.setCellWidget(row, 4, sub_id)
        self.table.setCellWidget(row, 5, narration)
        account.currentIndexChanged.connect(lambda _ix, r=row: self._on_account_selected(r))
        sub_type.currentIndexChanged.connect(
            lambda _ix, r=row: self._populate_subledger_combo(r)
        )

    def _remove_line_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_totals_footer()

    def _on_account_selected(self, row_index: int) -> None:
        combo = self.table.cellWidget(row_index, 0)
        account_id = combo.currentData() if combo else None
        account = next((item for item in self._accounts if item.get("account_id") == account_id), None)
        is_control = bool(account and account.get("is_control_account"))
        self.table.cellWidget(row_index, 3).setEnabled(is_control)
        self.table.cellWidget(row_index, 4).setEnabled(is_control)
        if not is_control:
            self.table.cellWidget(row_index, 3).setCurrentIndex(0)
            self.table.cellWidget(row_index, 4).setCurrentIndex(0)

    def _populate_subledger_combo(self, row_index: int) -> None:
        sub_type = self.table.cellWidget(row_index, 3).currentText()
        combo = self.table.cellWidget(row_index, 4)
        combo.clear()
        combo.addItem("-- Select customer/supplier --", None)
        if sub_type == "Customer":
            records = customer_engine.get_active_customers()
            for record in records:
                combo.addItem(
                    str(record.get("customer_name") or record.get("customer_code") or record.get("customer_id")),
                    record.get("customer_id"),
                )
        elif sub_type == "Supplier":
            for record in self._supplier_engine.get_active_suppliers():
                combo.addItem(
                    str(getattr(record, "supplier_name", "") or getattr(record, "supplier_code", "")),
                    getattr(record, "supplier_id", None),
                )

    def _update_totals_footer(self) -> None:
        debit = sum(self.table.cellWidget(row, 1).value() for row in range(self.table.rowCount()))
        credit = sum(self.table.cellWidget(row, 2).value() for row in range(self.table.rowCount()))
        self.totals.setText(f"Total debit: {debit:,.2f}    Total credit: {credit:,.2f}")

    def _collect_lines(self) -> list[dict]:
        lines = []
        for row in range(self.table.rowCount()):
            account_id = self.table.cellWidget(row, 0).currentData()
            debit = self.table.cellWidget(row, 1).value()
            credit = self.table.cellWidget(row, 2).value()
            if account_id is None and not debit and not credit:
                continue
            if account_id is None:
                raise ValueError(f"Select an account on line {row + 1}.")
            if debit > 0 and credit > 0:
                raise ValueError(f"Line {row + 1} cannot have both debit and credit.")
            if debit <= 0 and credit <= 0:
                raise ValueError(f"Enter a debit or credit on line {row + 1}.")
            account = next((item for item in self._accounts if item.get("account_id") == account_id), {})
            sub_type = self.table.cellWidget(row, 3).currentText() or None
            sub_id = self.table.cellWidget(row, 4).currentData()
            if account.get("is_control_account") and (not sub_type or not sub_id):
                raise ValueError(f"Select the required customer/supplier sub-ledger on line {row + 1}.")
            lines.append({
                "account_id": int(account_id),
                "debit_amount": debit,
                "credit_amount": credit,
                "sub_ledger_type": sub_type if account.get("is_control_account") else None,
                "sub_ledger_id": sub_id if account.get("is_control_account") else None,
                "branch_id": None,
                "department_id": None,
                "cost_center_id": None,
                "line_narration": self.table.cellWidget(row, 5).text().strip() or None,
                "line_order": len(lines) + 1,
            })
        if len(lines) < 2:
            raise ValueError("A journal voucher needs at least two populated lines.")
        return lines

    def _on_save_clicked(self) -> None:
        try:
            narration = self.narration.text().strip()
            if not narration:
                raise ValueError("Narration is required.")
            journal_date_ad = bs_to_ad(self.date_picker.get_bs_date_string())
            lines = self._collect_lines()
            poster = getattr(self._engine, "post_manual_journal", None)
            if not callable(poster):
                raise RuntimeError(
                    "AccountingEngine.post_manual_journal(journal_date_ad, narration, line_rows, created_by) "
                    "is missing; the documented public manual-journal wrapper must be added."
                )
            poster(journal_date_ad, narration, lines, get_current_user_id())
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Journal Voucher", str(exc))
