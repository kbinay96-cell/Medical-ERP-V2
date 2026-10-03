from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.date_engine import ad_to_bs
from models.chart_of_accounts_model import ChartOfAccountsModel
from utils.integration_adapters import get_current_user_id


class _AccountDialog(QDialog):
    def __init__(self, accounts: list[dict], account: dict | None = None, parent=None):
        super().__init__(parent)
        self.account = account
        self.setWindowTitle("Edit Account" if account else "Add Account")
        form = QFormLayout(self)
        self.code = QLineEdit(str((account or {}).get("account_code") or ""))
        self.name = QLineEdit(str((account or {}).get("account_name") or ""))
        self.group = QComboBox()
        self.group.setEditable(True)
        groups = sorted({str(row.get("account_group") or "") for row in accounts if row.get("account_group")})
        self.group.addItems(groups or ["Assets", "Liabilities", "Equity", "Income", "Expenses"])
        if account:
            self.group.setCurrentText(str(account.get("account_group") or ""))
        self.parent_account = QComboBox()
        self.parent_account.addItem("-- No parent --", None)
        for row in accounts:
            if account and row.get("account_id") == account.get("account_id"):
                continue
            self.parent_account.addItem(
                f"{row.get('account_code', '')} — {row.get('account_name', '')}",
                row.get("account_id"),
            )
        parent_id = (account or {}).get("parent_account_id")
        ix = self.parent_account.findData(parent_id)
        if ix >= 0:
            self.parent_account.setCurrentIndex(ix)
        self.control = QCheckBox()
        self.control.setChecked(bool((account or {}).get("is_control_account")))
        self.normal_balance = QComboBox()
        self.normal_balance.addItems(["Debit", "Credit"])
        current_balance = str((account or {}).get("normal_balance") or "Debit")
        self.normal_balance.setCurrentText(current_balance)
        self.active = QCheckBox()
        self.active.setChecked(bool((account or {}).get("is_active", True)))
        self.remarks = QLineEdit(str((account or {}).get("remarks") or ""))
        form.addRow("Account code", self.code)
        form.addRow("Account name", self.name)
        form.addRow("Group", self.group)
        form.addRow("Parent account", self.parent_account)
        form.addRow("Control account", self.control)
        form.addRow("Normal balance", self.normal_balance)
        form.addRow("Active", self.active)
        form.addRow("Remarks", self.remarks)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict:
        return {
            "account_code": self.code.text().strip(),
            "account_name": self.name.text().strip(),
            "account_group": self.group.currentText().strip(),
            "parent_account_id": self.parent_account.currentData(),
            "is_control_account": self.control.isChecked(),
            "normal_balance": self.normal_balance.currentText(),
            "is_active": self.active.isChecked(),
            "remarks": self.remarks.text().strip() or None,
        }


class ChartOfAccountsScreen(QWidget):
    """Chart of accounts tree; persistence and hierarchy reads use the COA model."""
    close_requested = Signal()

    def __init__(
        self,
        parent=None,
        coa_model: ChartOfAccountsModel | None = None,
        engine=None,
        financial_year_model=None,
    ):
        super().__init__(parent)
        self._coa_model = coa_model or ChartOfAccountsModel()
        self._engine = engine
        self._financial_year_model = financial_year_model
        root = QVBoxLayout(self)
        from utils.ui_standards import add_embedded_back_button
        add_embedded_back_button(self, root, self.close_requested.emit)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Chart of Accounts"), 1)
        self.add_button = QPushButton("Add account")
        self.edit_button = QPushButton("Edit selected")
        self.refresh_button = QPushButton("Refresh")
        self.opening_button = QPushButton("Opening balances")
        self.opening_button.setEnabled(engine is not None and financial_year_model is not None)
        if not self.opening_button.isEnabled():
            self.opening_button.setToolTip(
                "Provide engine and FinancialYearModel dependencies to post opening balances."
            )
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.opening_button)
        root.addLayout(toolbar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Account", "Group", "Normal balance", "Status"])
        self.tree.setColumnWidth(0, 360)
        root.addWidget(self.tree, 1)
        self.add_button.clicked.connect(self._on_add_account_clicked)
        self.edit_button.clicked.connect(self._on_edit_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self.opening_button.clicked.connect(self._open_opening_balances)
        self.tree.itemDoubleClicked.connect(lambda *_: self._on_edit_selected())
        self.refresh()

    def _build_tree(self, accounts: list[dict]) -> None:
        self.tree.clear()
        by_id = {row.get("account_id"): row for row in accounts}
        nodes: dict[object, QTreeWidgetItem] = {}
        roots: dict[str, QTreeWidgetItem] = {}

        def add_account(row: dict) -> QTreeWidgetItem:
            aid = row.get("account_id")
            if aid in nodes:
                return nodes[aid]
            parent_id = row.get("parent_account_id")
            if parent_id in by_id and parent_id != aid:
                parent_item = add_account(by_id[parent_id])
            else:
                group = str(row.get("account_group") or "Other")
                if group not in roots:
                    roots[group] = QTreeWidgetItem([group, group, "", ""])
                    roots[group].setData(0, Qt.UserRole, None)
                    self.tree.addTopLevelItem(roots[group])
                parent_item = roots[group]
            item = QTreeWidgetItem([
                f"{row.get('account_code') or ''} — {row.get('account_name') or ''}",
                str(row.get("account_group") or ""),
                str(row.get("normal_balance") or ""),
                "Active" if row.get("is_active", True) else "Inactive",
            ])
            item.setData(0, Qt.UserRole, aid)
            item.setToolTip(0, str(row.get("remarks") or ""))
            parent_item.addChild(item)
            nodes[aid] = item
            return item

        for account in accounts:
            add_account(account)
        self.tree.expandAll()

    def refresh(self) -> None:
        try:
            self._build_tree(self._coa_model.get_hierarchy())
        except Exception as exc:
            QMessageBox.critical(self, "Chart of Accounts", f"Could not load accounts:\n{exc}")

    def _on_add_account_clicked(self) -> None:
        try:
            accounts = self._coa_model.get_hierarchy()
            dialog = _AccountDialog(accounts, parent=self)
            if dialog.exec() != QDialog.Accepted:
                return
            payload = dialog.payload()
            if not payload["account_code"] or not payload["account_name"] or not payload["account_group"]:
                raise ValueError("Account code, name and group are required.")
            now = datetime.now(timezone.utc)
            payload.update({
                "created_by": get_current_user_id(),
                "created_at_ad": now,
                "created_at_bs": ad_to_bs(now.date()),
            })
            self._coa_model.insert(payload)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Add Account", str(exc))

    def _on_edit_selected(self) -> None:
        selected = self.tree.currentItem()
        account_id = selected.data(0, Qt.UserRole) if selected else None
        if account_id is None:
            QMessageBox.information(self, "Edit Account", "Select a ledger account first.")
            return
        try:
            account = self._coa_model.get_by_id(int(account_id))
            if not account:
                raise ValueError("The selected account no longer exists.")
            dialog = _AccountDialog(self._coa_model.get_hierarchy(), account, self)
            dialog.control.setEnabled(False)
            if dialog.exec() != QDialog.Accepted:
                return
            changed = dialog.payload()
            if not changed["account_code"] or not changed["account_name"] or not changed["account_group"]:
                raise ValueError("Account code, name and group are required.")
            changed.pop("is_control_account", None)
            now = datetime.now(timezone.utc)
            self._coa_model.update(
                int(account_id), changed, get_current_user_id(), now, ad_to_bs(now.date())
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Edit Account", str(exc))

    def _open_opening_balances(self) -> None:
        if self._engine is None or self._financial_year_model is None:
            return
        try:
            from screens.opening_balance_screen import OpeningBalanceScreen
            OpeningBalanceScreen(
                self, self._engine, self._financial_year_model, self._coa_model
            ).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Opening Balances", str(exc))
