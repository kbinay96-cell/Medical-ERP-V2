from __future__ import annotations

from datetime import date, datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.integration_adapters import get_current_user_id


class PeriodLockScreen(QWidget):
    """Period lock controls; period and permission rules remain in injected models."""
    close_requested = Signal()

    def __init__(
        self,
        parent,
        period_model,
        role_permission_model,
        role_name: str | None = None,
        current_user_id: int | None = None,
        engine=None,
        financial_year_model=None,
        coa_model=None,
    ):
        super().__init__(parent)
        self._period_model = period_model
        self._role_permission_model = role_permission_model
        self._role_name = role_name
        self._current_user_id = current_user_id or get_current_user_id()
        self._engine = engine
        self._financial_year_model = financial_year_model
        self._coa_model = coa_model
        self._permissions: dict = {}
        root = QVBoxLayout(self)
        from utils.ui_standards import add_embedded_back_button
        add_embedded_back_button(self, root, self.close_requested.emit)
        header = QHBoxLayout()
        header.addWidget(QLabel("Financial years and accounting periods"), 1)
        self.refresh_button = QPushButton("Refresh")
        header.addWidget(self.refresh_button)
        self.opening_button = QPushButton("Opening balances")
        self.opening_button.setEnabled(
            engine is not None and financial_year_model is not None and coa_model is not None
        )
        if not self.opening_button.isEnabled():
            self.opening_button.setToolTip(
                "Provide engine, FinancialYearModel and ChartOfAccountsModel dependencies."
            )
        header.addWidget(self.opening_button)
        root.addLayout(header)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Period", "Start", "End", "Status"])
        root.addWidget(self.tree, 1)
        actions = QHBoxLayout()
        self.lock_button = QPushButton("Lock selected period")
        self.reopen_button = QPushButton("Reopen selected period")
        actions.addWidget(self.lock_button)
        actions.addWidget(self.reopen_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.refresh_button.clicked.connect(self.refresh)
        self.opening_button.clicked.connect(self._open_opening_balances)
        self.lock_button.clicked.connect(self._on_lock_selected)
        self.reopen_button.clicked.connect(self._on_reopen_selected)
        self.tree.itemSelectionChanged.connect(self._update_actions)
        self.refresh()

    @staticmethod
    def _get(row, key, default=None):
        return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)

    def refresh(self) -> None:
        self.tree.clear()
        try:
            if self._role_name and self._role_permission_model:
                self._permissions = self._role_permission_model.get_permissions_for_role(self._role_name) or {}
            periods = None
            # A listing endpoint is optional; the Part 1 contract only guarantees
            # date lookup, so this view can still show the current period without SQL.
            for method_name in ("get_all_periods", "list_periods"):
                method = getattr(self._period_model, method_name, None)
                if callable(method):
                    periods = method()
                    break
            if periods is None:
                current = self._period_model.get_period_for_date(date.today())
                periods = [current] if current else []
            parents: dict[object, QTreeWidgetItem] = {}
            for period in periods:
                year_id = self._get(period, "financial_year_id", "Current financial year")
                if year_id not in parents:
                    year_label = (
                        self._get(period, "financial_year", None)
                        or self._get(period, "fy_label", None)
                        or f"Financial year {year_id}"
                    )
                    parents[year_id] = QTreeWidgetItem([str(year_label), "", "", ""])
                    parents[year_id].setData(0, Qt.UserRole, None)
                    self.tree.addTopLevelItem(parents[year_id])
                item = QTreeWidgetItem([
                    str(
                        self._get(period, "period_name")
                        or self._get(period, "period_label")
                        or self._get(period, "accounting_period_id")
                        or "Period"
                    ),
                    str(self._get(period, "start_date_ad") or ""),
                    str(self._get(period, "end_date_ad") or ""),
                    str(self._get(period, "status") or ""),
                ])
                item.setData(0, Qt.UserRole, self._get(period, "accounting_period_id"))
                parents[year_id].addChild(item)
            self.tree.expandAll()
            if not periods:
                self.tree.addTopLevelItem(QTreeWidgetItem([
                    "No periods found", "", "",
                    "Provide the documented period-model date lookup/listing data.",
                ]))
        except Exception as exc:
            QMessageBox.critical(self, "Period Lock", f"Could not load periods:\n{exc}")
        self._update_actions()

    def _selected_period(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _update_actions(self) -> None:
        selected = self.tree.currentItem()
        period_id = self._selected_period()
        status = selected.text(3) if selected else ""
        can_lock = bool(
            self._permissions.get("Post")
            or self._permissions.get("Manager")
            or self._permissions.get("Period Lock")
        )
        can_unlock = bool(self._permissions.get("Period Unlock"))
        # Keep controls safe by default when permissions are not injected.
        if not self._role_name:
            can_lock = can_unlock = False
        self.lock_button.setEnabled(period_id is not None and status.casefold() != "locked" and can_lock)
        self.reopen_button.setEnabled(period_id is not None and status.casefold() == "locked" and can_unlock)

    def _on_lock_selected(self) -> None:
        period_id = self._selected_period()
        if period_id is None:
            return
        if not (self._permissions.get("Post") or self._permissions.get("Manager") or self._permissions.get("Period Lock")):
            QMessageBox.warning(self, "Lock Period", "Your role does not have period-lock permission.")
            return
        try:
            if self._engine is not None:
                self._engine.lock_period(int(period_id), self._current_user_id)
            else:
                self._period_model.lock_period(
                    int(period_id),
                    locked_by=self._current_user_id,
                    locked_at_ad=datetime.now(timezone.utc),
                )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Lock Period", str(exc))

    def _on_reopen_selected(self) -> None:
        period_id = self._selected_period()
        if period_id is None:
            return
        if not self._permissions.get("Period Unlock"):
            QMessageBox.warning(self, "Reopen Period", "Your role does not have Period Unlock permission.")
            return
        reason, accepted = QInputDialog.getText(self, "Reopen Period", "Reason (required):")
        reason = reason.strip()
        if not accepted:
            return
        if not reason:
            QMessageBox.warning(self, "Reopen Period", "A reason is required.")
            return
        try:
            if self._engine is not None:
                self._engine.reopen_period(int(period_id), reason, self._current_user_id)
            else:
                self._period_model.reopen_period(
                    int(period_id),
                    reopened_by=self._current_user_id,
                    reopen_reason=reason,
                    reopened_at_ad=datetime.now(timezone.utc),
                )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Reopen Period", str(exc))

    def _open_opening_balances(self) -> None:
        if not (self._engine and self._financial_year_model and self._coa_model):
            return
        try:
            from screens.opening_balance_screen import OpeningBalanceScreen
            OpeningBalanceScreen(
                self, self._engine, self._financial_year_model, self._coa_model
            ).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Opening Balances", str(exc))
