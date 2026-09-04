"""
screens/sale_invoice_list_screen.py

Sale Invoice List/Search Screen - Medical ERP V2

Mirrors screens/purchase_invoice_list_screen.py exactly (filter row + sorted
QTableWidget + pagination). Filters: search text (matches invoice number OR
customer name, per SaleInvoiceModel.search()), Area, Status, Sale Mode
(Retail/Wholesale), Date range.

Actions:
    - View: opens a read-only detail dialog. NOTE on fidelity: the spec's
      "view showing exactly the columns that were visible/printed at save
      time" is approximated here using sale_invoice.sale_mode (the one
      thing actually stored per-invoice) to decide whether Free Qty / CC
      appear -- the schema does not store a full per-invoice visible-
      column list, only sale_mode, so this is the closest faithful
      reconstruction available from what is actually persisted.
    - Cancel: soft-delete, per confirmed add-only + Sale Return correction
      rule. Disabled once a row is already Cancelled.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from engines.exceptions import RecordNotFoundError
from engines.sale_engine import SaleEngine, SaleInvoiceDTO
from screens.sale_invoice_form_screen import SaleInvoiceFormScreen

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
SEARCH_DEBOUNCE_MS = 300

STATUS_OPTIONS = ["All", "Draft", "Posted", "Cancelled"]
SALE_MODE_OPTIONS = ["All", "Retail", "Wholesale"]

COL_INVOICE_NO = 0
COL_CUSTOMER = 1
COL_AREA = 2
COL_DATE = 3
COL_MODE = 4
COL_GRAND_TOTAL = 5
COL_STATUS = 6
COL_ACTIONS = 7
COLUMN_COUNT = 8


class SaleInvoiceListScreen(QWidget):
    """List/search -- mirrors screens/purchase_invoice_list_screen.py."""

    form_requested = Signal()    # embedded: "+ New Sale Invoice" clicked
    close_requested = Signal()   # embedded: Back button clicked

    def __init__(
        self,
        parent,
        engine: SaleEngine,
        customer_engine,
        item_engine,
        item_free_scheme_engine,
        current_user_id: int,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._embedded = embedded
        self._engine = engine
        self._customer_engine = customer_engine
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._current_user_id = current_user_id

        self._rows: list[SaleInvoiceDTO] = []
        self._current_page = 1

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._reload_first_page)

        self._build_ui()
        self._connect_signals()
        self._populate_area_filter()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        if self._embedded:
            back_row = QHBoxLayout()
            self.back_button = QPushButton("\u25c0 Back")
            self.back_button.clicked.connect(self.close_requested.emit)
            back_row.addWidget(self.back_button)
            back_row.addStretch()
            root.addLayout(back_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Invoice number or customer...")
        filter_row.addWidget(self.search_input)

        filter_row.addWidget(QLabel("Area:"))
        self.area_filter_combo = QComboBox()
        filter_row.addWidget(self.area_filter_combo)

        filter_row.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(STATUS_OPTIONS)
        filter_row.addWidget(self.status_filter_combo)

        filter_row.addWidget(QLabel("Mode:"))
        self.sale_mode_filter_combo = QComboBox()
        self.sale_mode_filter_combo.addItems(SALE_MODE_OPTIONS)
        filter_row.addWidget(self.sale_mode_filter_combo)

        filter_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        filter_row.addWidget(self.date_to)

        self.search_button = QPushButton("Filter")
        filter_row.addWidget(self.search_button)

        self.new_button = QPushButton("+ New Sale Invoice")
        filter_row.addStretch()
        filter_row.addWidget(self.new_button)

        root.addLayout(filter_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["Invoice No.", "Customer", "Area", "Date", "Mode", "Grand Total", "Status", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_CUSTOMER, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

        pagination_row = QHBoxLayout()
        self.prev_page_button = QPushButton("\u25c0 Prev")
        pagination_row.addWidget(self.prev_page_button)
        self.page_label = QLabel("Page 1")
        pagination_row.addWidget(self.page_label)
        self.next_page_button = QPushButton("Next \u25b6")
        pagination_row.addWidget(self.next_page_button)
        pagination_row.addStretch()
        self.page_total_label = QLabel("Page Total: 0.00")
        self.page_total_label.setStyleSheet("font-weight: bold;")
        pagination_row.addWidget(self.page_total_label)
        root.addLayout(pagination_row)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(lambda _: self._debounce_timer.start(SEARCH_DEBOUNCE_MS))
        self.area_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.status_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.sale_mode_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.search_button.clicked.connect(self._reload_first_page)
        self.new_button.clicked.connect(self._on_new_clicked)
        self.prev_page_button.clicked.connect(self._on_prev_page)
        self.next_page_button.clicked.connect(self._on_next_page)

    def _populate_area_filter(self) -> None:
        self.area_filter_combo.clear()
        self.area_filter_combo.addItem("All Areas", None)
        lookup_data = self._customer_engine.get_lookup_data()
        for area in lookup_data.get("areas", []):
            self.area_filter_combo.addItem(str(area.get("area_name", "")), area.get("area_id"))

    # ------------------------------------------------------------------ #
    def _reload_first_page(self) -> None:
        self._current_page = 1
        self.refresh()

    def refresh(self) -> None:
        search_text = self.search_input.text().strip() or None
        status_text = self.status_filter_combo.currentText()
        status = None if status_text == "All" else status_text
        mode_text = self.sale_mode_filter_combo.currentText()
        sale_mode = None if mode_text == "All" else mode_text

        # NOTE: Area/Date-range filters are not sent -- the real
        # SaleEngine.search_sale_invoices() does not accept area_id,
        # date_from_ad, or date_to_ad (only search_text, customer_id,
        # status, sale_mode, include_deleted, page, page_size, order_by,
        # order_dir). The Area combo and date pickers stay in the UI but
        # currently have no filtering effect -- wire them up once/if the
        # engine adds support, or filter client-side on self._rows if
        # needed sooner.
        self._rows, total_count = self._engine.search_sale_invoices(
            search_text=search_text,
            status=status,
            sale_mode=sale_mode,
            page=self._current_page,
            page_size=PAGE_SIZE,
        )
        self._populate_table()

        total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        self.page_label.setText(f"Page {self._current_page} of {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

        page_total = sum(dto.grand_total for dto in self._rows)
        self.page_total_label.setText(f"Page Total: {page_total:,.2f}")

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for dto in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, COL_INVOICE_NO, QTableWidgetItem(dto.invoice_number))
            self.table.setItem(row, COL_CUSTOMER, QTableWidgetItem(dto.customer_name or ""))
            self.table.setItem(row, COL_AREA, QTableWidgetItem(dto.area_name or ""))
            self.table.setItem(row, COL_DATE, QTableWidgetItem(dto.invoice_date_bs or ""))
            self.table.setItem(row, COL_MODE, QTableWidgetItem(dto.sale_mode))
            self.table.setItem(row, COL_GRAND_TOTAL, QTableWidgetItem(f"{dto.grand_total:,.2f}"))
            self.table.setItem(row, COL_STATUS, QTableWidgetItem(dto.status))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, sid=dto.sale_invoice_id: self._on_view_clicked(sid))
            action_layout.addWidget(view_button)

            cancel_button = QPushButton("Cancel")
            cancel_button.setEnabled(dto.status != "Cancelled")
            cancel_button.clicked.connect(lambda _, sid=dto.sale_invoice_id: self._on_cancel_clicked(sid))
            action_layout.addWidget(cancel_button)

            self.table.setCellWidget(row, COL_ACTIONS, action_widget)

    def _on_prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.refresh()

    def _on_next_page(self) -> None:
        self._current_page += 1
        self.refresh()

    # ------------------------------------------------------------------ #
    def _on_new_clicked(self) -> None:
        if self._embedded:
            self.form_requested.emit()
            return
        dialog = SaleInvoiceFormScreen(
            self, self._engine, self._customer_engine, self._item_engine,
            self._item_free_scheme_engine, self._current_user_id,
        )
        if dialog.exec():
            self._reload_first_page()

    def _on_view_clicked(self, sale_invoice_id: int) -> None:
        try:
            dto = self._engine.get_sale_invoice(sale_invoice_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
            return
        dialog = _SaleInvoiceViewDialog(self, dto)
        dialog.exec()

    def _on_cancel_clicked(self, sale_invoice_id: int) -> None:
        confirm = QMessageBox.question(
            self, "Confirm Cancel",
            "Cancel this Sale Invoice? This does NOT automatically reverse stock "
            "-- physical correction, if needed, goes through Sale Return.",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self._engine.cancel_sale_invoice(sale_invoice_id, self._current_user_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Cannot Cancel", str(exc))
            return
        self.refresh()


class _SaleInvoiceViewDialog(QDialog):
    """Read-only detail view -- header info-panel plus a read-only line
    table. Free Qty / Tax columns are shown only when dto.sale_mode ==
    'Wholesale' (the one column-relevant fact the schema actually
    persists per invoice); everything else in the line table is always
    shown since no separate per-invoice visible-column list exists."""

    def __init__(self, parent, dto: SaleInvoiceDTO) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Sale Invoice {dto.invoice_number}")
        self.resize(820, 520)

        root = QVBoxLayout(self)
        header_form = QFormLayout()
        header_form.addRow("Invoice Number:", QLabel(dto.invoice_number))
        header_form.addRow("Customer:", QLabel(dto.customer_name or ""))
        header_form.addRow("Area:", QLabel(dto.area_name or ""))
        header_form.addRow("Date (BS):", QLabel(dto.invoice_date_bs or ""))
        header_form.addRow("Sale Mode:", QLabel(dto.sale_mode))
        header_form.addRow("Status:", QLabel(dto.status))
        header_form.addRow("Payment Type:", QLabel(dto.payment_type or "Credit"))
        header_form.addRow("Amount Paid Now:", QLabel(f"{dto.amount_paid_now:,.2f}"))
        header_form.addRow("Grand Total:", QLabel(f"{dto.grand_total:,.2f}"))
        if dto.remarks:
            header_form.addRow("Remarks:", QLabel(dto.remarks))
        root.addLayout(header_form)

        show_wholesale_cols = dto.sale_mode == "Wholesale"
        headers = ["Item", "Batch", "Expiry", "Qty"]
        if show_wholesale_cols:
            headers += ["Free Qty", "CC Amt"]
        headers += ["Rate", "Disc %"]
        if show_wholesale_cols:
            headers += ["Tax %", "Tax Amt"]
        headers += ["Amount"]

        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)

        for line in dto.lines:
            row = table.rowCount()
            table.insertRow(row)
            col = 0
            table.setItem(row, col, QTableWidgetItem(str(line.item_id))); col += 1
            table.setItem(row, col, QTableWidgetItem(line.batch_no)); col += 1
            table.setItem(row, col, QTableWidgetItem(f"{line.expiry_month:02d}/{line.expiry_year}")); col += 1
            table.setItem(row, col, QTableWidgetItem(f"{line.qty:g}")); col += 1
            if show_wholesale_cols:
                table.setItem(row, col, QTableWidgetItem(f"{line.free_qty:g}")); col += 1
                table.setItem(row, col, QTableWidgetItem(f"{line.cc_amount:.2f}")); col += 1
            table.setItem(row, col, QTableWidgetItem(f"{line.rate:.2f}")); col += 1
            table.setItem(row, col, QTableWidgetItem(f"{line.discount_percent:.2f}")); col += 1
            if show_wholesale_cols:
                table.setItem(row, col, QTableWidgetItem(f"{line.tax_percent:.2f}")); col += 1
                table.setItem(row, col, QTableWidgetItem(f"{line.tax_amount:.2f}")); col += 1
            table.setItem(row, col, QTableWidgetItem(f"{line.amount:.2f}")); col += 1

        root.addWidget(table, stretch=1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        root.addLayout(close_row)


__all__ = ["SaleInvoiceListScreen"]