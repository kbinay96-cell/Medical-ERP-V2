from __future__ import annotations

from datetime import date, datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.integration_adapters import get_current_user_id
from engines import customer_engine
from engines.supplier_engine import SupplierEngine
from models.chart_of_accounts_model import ChartOfAccountsModel


def _get(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


class OpeningBalanceScreen(QDialog):
    """Post one balanced opening journal per financial year."""

    def __init__(self, parent, engine, financial_year_model, coa_model: ChartOfAccountsModel):
        super().__init__(parent)
        self._engine = engine
        self._financial_year_model = financial_year_model
        self._coa_model = coa_model
        self._years: list = []
        self._accounts: list[dict] = []
        self._supplier_engine = SupplierEngine()
        self.setWindowTitle("Opening Balances")
        self.resize(1000, 540)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Financial year:"))
        self.year_combo = QComboBox()
        header.addWidget(self.year_combo, 1)
        header.addWidget(QLabel("Journal date:"))
        self.journal_date = QDateEdit()
        self.journal_date.setCalendarPopup(True)
        self.journal_date.setDisplayFormat("yyyy-MM-dd")
        self.journal_date.setDate(date.today())
        header.addWidget(self.journal_date)
        root.addLayout(header)
        self.status_label = QLabel()
        root.addWidget(self.status_label)
        actions = QHBoxLayout()
        self.add_row_button = QPushButton("Add balance line")
        self.remove_row_button = QPushButton("Remove selected")
        actions.addWidget(self.add_row_button)
        actions.addWidget(self.remove_row_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.table = QTableWidget(0, 4)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Account", "Debit", "Credit", "Sub-ledger type", "Sub-ledger ID",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        self.totals = QLabel("Total debit: 0.00    Total credit: 0.00")
        root.addWidget(self.totals)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.Save)
        buttons.accepted.connect(self._on_save_clicked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.add_row_button.clicked.connect(self._add_row)
        self.remove_row_button.clicked.connect(self._remove_row)
        self.year_combo.currentIndexChanged.connect(self._check_year_posted)
        try:
            self._accounts = self._coa_model.get_hierarchy()
            self._load_financial_years()
            self._add_row()
            self._add_row()
            self._check_year_posted()
        except Exception as exc:
            QMessageBox.critical(self, "Opening Balances", f"Could not initialize:\n{exc}")

    def _load_financial_years(self) -> None:
        model = self._financial_year_model
        years = None
        for method_name in ("list_all", "get_all_financial_years", "list_financial_years"):
            method = getattr(model, method_name, None)
            if callable(method):
                years = method()
                break
        if years is None:
            method = getattr(model, "get_current_open_year", None)
            if callable(method):
                year = method()
                years = [year] if year else []
        if years is None and callable(model):
            years = model()
        self._years = list(years or [])
        for year in self._years:
            year_id = _get(year, "financial_year_id", _get(year, "financialyearid"))
            label = _get(
                year,
                "fy_label",
                _get(year, "financial_year", _get(year, "financialyear", None)),
            )
            if label is None:
                label = f"Financial year {year_id}"
            self.year_combo.addItem(str(label), year_id)
        if not self._years:
            self.status_label.setText(
                "No financial years available. Provide FinancialYearModel.get_current_open_year() "
                "or get_all_financial_years()."
            )

    def _add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        account = QComboBox()
        account.addItem("-- Select account --", None)
        for item in self._accounts:
            account.addItem(
                f"{item.get('account_code')} — {item.get('account_name')}",
                item.get("account_id"),
            )
        debit = QDoubleSpinBox()
        credit = QDoubleSpinBox()
        for spin in (debit, credit):
            spin.setRange(0, 999_999_999_999)
            spin.setDecimals(2)
            spin.valueChanged.connect(self._update_totals_footer)
        subledger = QComboBox()
        subledger.addItems(["", "Customer", "Supplier"])
        subledger.setEnabled(False)
        subledger_id = QComboBox()
        subledger_id.addItem("-- Select customer/supplier --", None)
        subledger_id.setEnabled(False)
        account.currentIndexChanged.connect(
            lambda _ix, r=row: self._on_account_selected(r)
        )
        subledger.currentIndexChanged.connect(lambda _ix, r=row: self._populate_subledger_combo(r))
        self.table.setCellWidget(row, 0, account)
        self.table.setCellWidget(row, 1, debit)
        self.table.setCellWidget(row, 2, credit)
        self.table.setCellWidget(row, 3, subledger)
        self.table.setCellWidget(row, 4, subledger_id)

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_totals_footer()

    def _on_account_selected(self, row: int) -> None:
        account_id = self.table.cellWidget(row, 0).currentData()
        account = next((item for item in self._accounts if item.get("account_id") == account_id), None)
        required = bool(account and account.get("is_control_account"))
        for column in (3, 4):
            widget = self.table.cellWidget(row, column)
            widget.setEnabled(required)
            if not required:
                if column == 3:
                    widget.setCurrentIndex(0)
                else:
                    widget.setCurrentIndex(0)

    def _populate_subledger_combo(self, row: int) -> None:
        sub_type = self.table.cellWidget(row, 3).currentText()
        combo = self.table.cellWidget(row, 4)
        combo.clear()
        combo.addItem("-- Select customer/supplier --", None)
        if sub_type == "Customer":
            for record in customer_engine.get_active_customers():
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

    def _check_year_posted(self, _index=None) -> None:
        financial_year_id = self.year_combo.currentData()
        posted = False
        if financial_year_id is not None:
            year = next(
                (item for item in self._years
                 if _get(item, "financial_year_id", _get(item, "financialyearid")) == financial_year_id),
                {},
            )
            posted = bool(_get(year, "closing_journal_entry_id"))
            try:
                journals = self._engine.get_journals_for_document("Opening Balance", int(financial_year_id))
                posted = posted or bool(journals)
            except Exception as exc:
                self.status_label.setText(f"Could not verify opening balance status: {exc}")
                self.save_button.setEnabled(False)
                return
        self.status_label.setText(
            "Opening balances already posted for this financial year." if posted else ""
        )
        self.save_button.setEnabled(financial_year_id is not None and not posted)

    def _collect_rows(self) -> list[dict]:
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
                raise ValueError(f"Select the required sub-ledger on line {row + 1}.")
            lines.append({
                "account_id": int(account_id),
                "sub_ledger_type": sub_type if account.get("is_control_account") else None,
                "sub_ledger_id": sub_id if account.get("is_control_account") else None,
                "debit_amount": debit,
                "credit_amount": credit,
            })
        if len(lines) < 2:
            raise ValueError("At least two opening-balance lines are required.")
        return lines

    def _on_save_clicked(self) -> None:
        financial_year_id = self.year_combo.currentData()
        if financial_year_id is None:
            QMessageBox.warning(self, "Opening Balances", "Select a financial year.")
            return
        try:
            self._check_year_posted()
            if not self.save_button.isEnabled():
                raise ValueError("An opening balance has already been posted for this year.")
            rows = self._collect_rows()
            self._engine.post_opening_balances(
                int(financial_year_id),
                rows,
                get_current_user_id(),
                self.journal_date.date().toPython(),
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Opening Balances", str(exc))
