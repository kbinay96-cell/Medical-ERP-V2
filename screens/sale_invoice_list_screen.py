# screens/sale_invoice_list_screen.py
from __future__ import annotations

import logging
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.customer_engine import get_active_customers
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_engine import EngineErrorWithInvoice, SaleEngine
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)

COL_NUMBER = 0
COL_CUSTOMER = 1
COL_DATE = 2
COL_SALE_MODE = 3
COL_TOTAL = 4
COL_BALANCE = 5
COL_STATUS = 6
COL_VIEW = 7
COL_CANCEL = 8
COLUMN_COUNT = 9


class SaleInvoiceListScreen(QWidget):
    def __init__(self, parent, engine: SaleEngine, item_engine, item_free_scheme_engine=None, current_user_id: int = 1):
        super().__init__(parent)
        self._engine = engine
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._current_user_id = current_user_id
        self._current_page = 1
        self._page_size = 50

        self.setWindowTitle("Sale List")
        self.setMinimumSize(1100, 560)
        self._build_ui()
        self._connect_signals()
        self._populate_customer_filter()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Invoice number or customer...")
        filters.addWidget(self.search_input)

        filters.addWidget(QLabel("Customer:"))
        self.customer_filter = QComboBox()
        filters.addWidget(self.customer_filter)

        filters.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Posted", "Cancelled"])
        filters.addWidget(self.status_filter)

        filters.addWidget(QLabel("Sale Mode:"))
        self.sale_mode_filter = QComboBox()
        self.sale_mode_filter.addItems(["All", "Retail", "Wholesale"])
        filters.addWidget(self.sale_mode_filter)

        self.search_button = QPushButton("Search")
        self.new_button = QPushButton("New Sale")
        filters.addWidget(self.search_button)
        filters.addWidget(self.new_button)
        root.addLayout(filters)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["Invoice No", "Customer", "Date (BS)", "Mode", "Grand Total", "Balance", "Status", "View", "Cancel"]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_CUSTOMER, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

        pager = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.page_label = QLabel("Page 1")
        pager.addWidget(self.prev_button)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_button)
        pager.addStretch()
        root.addLayout(pager)

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self._on_search)
        self.search_input.returnPressed.connect(self._on_search)
        self.new_button.clicked.connect(self._on_new_sale)
        self.prev_button.clicked.connect(self._on_prev)
        self.next_button.clicked.connect(self._on_next)

    def _populate_customer_filter(self) -> None:
        rows = get_active_customers()
        items = [
            SimpleNamespace(customer_name=r["customer_name"], customer_id=r["customer_id"])
            for r in rows
        ]
        populate_searchable_combo(
            self.customer_filter,
            items=items,
            display_attr="customer_name",
            data_attr="customer_id",
            placeholder="All customers",
        )

    def _on_search(self) -> None:
        self._current_page = 1
        self.refresh()

    def _on_prev(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.refresh()

    def _on_next(self) -> None:
        self._current_page += 1
        self.refresh()

    def refresh(self) -> None:
        status = self.status_filter.currentText()
        status_value = None if status == "All" else status
        sale_mode = self.sale_mode_filter.currentText()
        sale_mode_value = None if sale_mode == "All" else sale_mode

        def _do_search(page_: int):
            return self._engine.search_sale_invoices(
                search_text=self.search_input.text().strip() or None,
                customer_id=self.customer_filter.currentData(),
                status=status_value,
                sale_mode=sale_mode_value,
                page=page_,
                page_size=self._page_size,
            )

        invoices, total = _do_search(self._current_page)
        max_page = max(1, (total + self._page_size - 1) // self._page_size)
        if self._current_page > max_page:
            self._current_page = max_page
            invoices, total = _do_search(self._current_page)

        self.page_label.setText(f"Page {self._current_page} of {max_page} ({total} invoices)")
        self.table.setRowCount(0)
        for invoice in invoices:
            self._append_row(invoice)

    def _append_row(self, invoice) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, COL_NUMBER, QTableWidgetItem(invoice.invoice_number))
        self.table.setItem(row, COL_CUSTOMER, QTableWidgetItem(invoice.customer_name))
        self.table.setItem(row, COL_DATE, QTableWidgetItem(invoice.invoice_date_bs))
        self.table.setItem(row, COL_SALE_MODE, QTableWidgetItem(invoice.sale_mode))
        self.table.setItem(row, COL_TOTAL, QTableWidgetItem(f"{invoice.grand_total:.2f}"))
        self.table.setItem(row, COL_BALANCE, QTableWidgetItem(f"{invoice.balance_amount:.2f}"))
        self.table.setItem(row, COL_STATUS, QTableWidgetItem(invoice.status))

        view_button = QPushButton("View")
        view_button.clicked.connect(
            lambda _, sid=invoice.sale_invoice_id: self._on_view_clicked(sid)
        )
        self.table.setCellWidget(row, COL_VIEW, view_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setEnabled(invoice.status == "Posted")
        cancel_button.clicked.connect(
            lambda _, sid=invoice.sale_invoice_id: self._on_cancel_clicked(sid)
        )
        self.table.setCellWidget(row, COL_CANCEL, cancel_button)

    def _on_new_sale(self) -> None:
        from screens.sale_invoice_form_screen import SaleInvoiceFormScreen

        dialog = SaleInvoiceFormScreen(
            parent=self,
            engine=self._engine,
            item_engine=self._item_engine,
            item_free_scheme_engine=self._item_free_scheme_engine,
            current_user_id=self._current_user_id,
        )
        dialog.exec()
        self.refresh()

    def _on_view_clicked(self, sale_invoice_id: int) -> None:
        try:
            invoice = self._engine.get_sale_invoice(sale_invoice_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
            return
        lines_text = "\n".join(
            f"  {line.batch_no}: qty={line.qty} free={line.free_qty} "
            f"rate={line.rate} amount={line.amount:.2f}"
            for line in invoice.lines
        )
        QMessageBox.information(
            self,
            f"Sale {invoice.invoice_number}",
            f"Customer: {invoice.customer_name}\n"
            f"Date: {invoice.invoice_date_bs}\n"
            f"Mode: {invoice.sale_mode}\n"
            f"Payment: {invoice.payment_type}\n"
            f"Grand Total: {invoice.grand_total:.2f}\n"
            f"Paid: {invoice.amount_paid_now:.2f}\n"
            f"Balance: {invoice.balance_amount:.2f}\n"
            f"Status: {invoice.status}\n\n"
            f"Lines:\n{lines_text or '  (none)'}",
        )

    def _on_cancel_clicked(self, sale_invoice_id: int) -> None:
        reason, ok = QInputDialog.getText(self, "Cancel Sale Invoice", "Reason for cancellation:")
        if not ok or not reason.strip():
            return
        try:
            self._engine.cancel_sale_invoice(sale_invoice_id, self._current_user_id, reason.strip())
        except (RecordNotFoundError, ValidationError) as exc:
            QMessageBox.warning(self, "Cannot Cancel", str(exc))
            return
        except Exception:
            logger.exception("Failed to cancel sale invoice %s", sale_invoice_id)
            QMessageBox.critical(self, "Error", "Could not cancel the sale invoice.")
            return
        self.refresh()
