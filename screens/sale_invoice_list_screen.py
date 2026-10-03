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

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.permission_enforcer import PermissionDeniedError
from engines.sale_engine import SaleEngine, SaleInvoiceDTO
from screens.cancellation_reason_dialog import CancellationReasonDialog
from screens.sale_invoice_form_screen import SaleInvoiceFormScreen
from screens.sale_invoice_view_dialog import SaleInvoiceViewDialog

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
COLUMN_COUNT = 7


class SaleInvoiceListScreen(QWidget):
    """List/search -- mirrors screens/purchase_invoice_list_screen.py."""

    form_requested = Signal()    # embedded: "+ New Sale Invoice" clicked
    edit_requested = Signal(int) # embedded: "Edit" clicked on a row, carries sale_invoice_id
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
        self.setObjectName("saleInvoiceListScreen")
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
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        if self._embedded:
            self.back_button = QPushButton("Back")
            self.back_button.setObjectName("saleSecondaryButton")
            self.back_button.clicked.connect(self.close_requested.emit)
            header.addWidget(self.back_button)
        title = QLabel("Sale Invoices")
        title.setObjectName("saleListTitle")
        header.addWidget(title)
        self.result_count_label = QLabel("0 invoices")
        self.result_count_label.setObjectName("saleListCount")
        header.addStretch(1)
        header.addWidget(self.result_count_label)
        self.new_button = QPushButton("+ New Invoice")
        self.new_button.setObjectName("salePrimaryButton")
        self.new_button.setMinimumWidth(150)
        self.new_button.setMaximumWidth(180)
        header.addWidget(self.new_button)
        root.addLayout(header)

        filter_group = QGroupBox("Search & filters")
        filter_group.setObjectName("saleSectionCard")
        filter_grid = QGridLayout(filter_group)
        filter_grid.setContentsMargins(8, 13, 8, 7)
        filter_grid.setHorizontalSpacing(8)
        filter_grid.setVerticalSpacing(3)

        def add_filter_field(label: str, widget, row: int, column: int, span: int = 1) -> None:
            caption = QLabel(label)
            caption.setObjectName("saleFieldCaption")
            filter_grid.addWidget(caption, row, column, 1, span)
            filter_grid.addWidget(widget, row + 1, column, 1, span)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Invoice number or customer...")
        self.search_input.setClearButtonEnabled(True)
        add_filter_field("Search", self.search_input, 0, 0, 2)
        self.area_filter_combo = QComboBox()
        add_filter_field("Area", self.area_filter_combo, 0, 2)
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(STATUS_OPTIONS)
        add_filter_field("Status", self.status_filter_combo, 0, 3)
        self.sale_mode_filter_combo = QComboBox()
        self.sale_mode_filter_combo.addItems(SALE_MODE_OPTIONS)
        add_filter_field("Sale mode", self.sale_mode_filter_combo, 0, 4)

        self.date_filter_checkbox = QCheckBox("Date range")
        self.date_filter_checkbox.setToolTip("Restrict results to the selected invoice date range.")
        filter_grid.addWidget(self.date_filter_checkbox, 2, 0, 1, 1, Qt.AlignVCenter)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd MMM yyyy")
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setEnabled(False)
        add_filter_field("From", self.date_from, 2, 1)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd MMM yyyy")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        add_filter_field("To", self.date_to, 2, 2)
        self.search_button = QPushButton("Filter")
        self.search_button.setObjectName("saleSecondaryButton")
        self.search_button.setMinimumWidth(120)
        filter_grid.addWidget(self.search_button, 3, 3, 1, 2, Qt.AlignRight | Qt.AlignBottom)
        for column in range(5):
            filter_grid.setColumnStretch(column, 1)
        filter_grid.setColumnStretch(0, 2)
        root.addWidget(filter_group)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setObjectName("saleInvoiceListTable")
        self.table.setHorizontalHeaderLabels(
            ["Invoice No.", "Customer", "Area", "Date", "Mode", "Grand Total", "Status"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_CUSTOMER, QHeaderView.Stretch)
        header.setMinimumSectionSize(80)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setColumnWidth(COL_INVOICE_NO, 110)
        self.table.setColumnWidth(COL_AREA, 100)
        self.table.setColumnWidth(COL_DATE, 82)
        self.table.setColumnWidth(COL_MODE, 78)
        self.table.setColumnWidth(COL_GRAND_TOTAL, 96)
        self.table.setColumnWidth(COL_STATUS, 82)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        root.addWidget(self.table)

        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(5)
        self.view_button = QPushButton("View")
        self.view_button.setObjectName("saleSecondaryButton")
        self.view_button.setToolTip("View the selected invoice.")
        self.view_button.setEnabled(False)
        pagination_row.addWidget(self.view_button)
        self.edit_button = QPushButton("Edit")
        self.edit_button.setObjectName("saleSecondaryButton")
        self.edit_button.setToolTip("Edit the selected invoice.")
        self.edit_button.setEnabled(False)
        pagination_row.addWidget(self.edit_button)
        self.cancel_invoice_button = QPushButton("Cancel")
        self.cancel_invoice_button.setObjectName("saleSecondaryButton")
        self.cancel_invoice_button.setToolTip("Cancel the selected Posted invoice.")
        self.cancel_invoice_button.setEnabled(False)
        pagination_row.addWidget(self.cancel_invoice_button)
        pagination_row.addSpacing(10)
        self.prev_page_button = QPushButton("\u25c0 Prev")
        self.prev_page_button.setObjectName("saleSecondaryButton")
        pagination_row.addWidget(self.prev_page_button)
        self.page_label = QLabel("Page 1")
        pagination_row.addWidget(self.page_label)
        self.next_page_button = QPushButton("Next \u25b6")
        self.next_page_button.setObjectName("saleSecondaryButton")
        pagination_row.addWidget(self.next_page_button)
        self.page_total_label = QLabel("Page Total: 0.00")
        self.page_total_label.setObjectName("saleListPageTotal")
        pagination_row.addStretch()
        pagination_row.addWidget(self.page_total_label)
        root.addLayout(pagination_row)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(lambda _: self._debounce_timer.start(SEARCH_DEBOUNCE_MS))
        self.area_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.status_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.sale_mode_filter_combo.currentIndexChanged.connect(self._reload_first_page)
        self.date_from.dateChanged.connect(self._reload_first_page)
        self.date_to.dateChanged.connect(self._reload_first_page)
        self.date_filter_checkbox.toggled.connect(self.date_from.setEnabled)
        self.date_filter_checkbox.toggled.connect(self.date_to.setEnabled)
        self.date_filter_checkbox.toggled.connect(self._reload_first_page)
        self.search_button.clicked.connect(self._reload_first_page)
        self.new_button.clicked.connect(self._on_new_clicked)
        self.prev_page_button.clicked.connect(self._on_prev_page)
        self.next_page_button.clicked.connect(self._on_next_page)
        self.table.itemSelectionChanged.connect(self._update_selection_actions)
        self.view_button.clicked.connect(self._on_view_selected)
        self.edit_button.clicked.connect(self._on_edit_selected)
        self.cancel_invoice_button.clicked.connect(self._on_cancel_selected)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)

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

        area_id = self.area_filter_combo.currentData()
        date_from_ad = (
            self.date_from.date().toString(Qt.ISODate)
            if self.date_filter_checkbox.isChecked()
            else None
        )
        date_to_ad = (
            self.date_to.date().toString(Qt.ISODate)
            if self.date_filter_checkbox.isChecked()
            else None
        )
        self._rows, total_count = self._engine.search_sale_invoices(
            search_text=search_text,
            area_id=area_id,
            status=status,
            sale_mode=sale_mode,
            date_from_ad=date_from_ad,
            date_to_ad=date_to_ad,
            include_deleted=status in (None, "Cancelled"),
            page=self._current_page,
            page_size=PAGE_SIZE,
        )
        self._populate_table()
        self._update_selection_actions()
        self.result_count_label.setText(
            f"{total_count:,} invoice{'s' if total_count != 1 else ''}"
        )

        total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        self.page_label.setText(f"Page {self._current_page} of {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

        page_total = sum(dto.grand_total for dto in self._rows)
        self.page_total_label.setText(f"Page Total: {page_total:,.2f}")

    def _populate_table(self) -> None:
        self.table.clearSpans()
        self.table.setRowCount(0)
        if not self._rows:
            self.table.insertRow(0)
            empty_item = QTableWidgetItem("No sale invoices match these filters")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsSelectable)
            self.table.setItem(0, COL_INVOICE_NO, empty_item)
            self.table.setSpan(0, 0, 1, COLUMN_COUNT)
            self.table.setRowHeight(0, 64)
            self._update_selection_actions()
            return

        for dto in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            invoice_item = QTableWidgetItem(dto.invoice_number)
            invoice_item.setData(Qt.UserRole, dto.sale_invoice_id)
            invoice_item.setFont(self.font())
            invoice_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, COL_INVOICE_NO, invoice_item)
            self.table.setItem(row, COL_CUSTOMER, QTableWidgetItem(dto.customer_name or ""))
            self.table.setItem(row, COL_AREA, QTableWidgetItem(dto.area_name or ""))
            date_item = QTableWidgetItem(dto.invoice_date_bs or "")
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, COL_DATE, date_item)
            mode_item = QTableWidgetItem(dto.sale_mode)
            mode_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, COL_MODE, mode_item)
            total_item = QTableWidgetItem(f"{dto.grand_total:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, COL_GRAND_TOTAL, total_item)
            status_item = QTableWidgetItem(dto.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, COL_STATUS, status_item)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self._update_selection_actions()

    def _selected_invoice(self) -> Optional[SaleInvoiceDTO]:
        if not self.table.selectionModel().hasSelection():
            return None
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _update_selection_actions(self) -> None:
        dto = self._selected_invoice()
        self.view_button.setEnabled(dto is not None)
        self.edit_button.setEnabled(dto is not None and dto.status != "Cancelled")
        self.cancel_invoice_button.setEnabled(dto is not None and dto.status == "Posted")

    def _on_view_selected(self) -> None:
        dto = self._selected_invoice()
        if dto is not None:
            self._on_view_clicked(dto.sale_invoice_id)

    def _on_edit_selected(self) -> None:
        dto = self._selected_invoice()
        if dto is not None and dto.status != "Cancelled":
            self._on_edit_clicked(dto.sale_invoice_id)

    def _on_cancel_selected(self) -> None:
        dto = self._selected_invoice()
        if dto is not None and dto.status == "Posted":
            self._on_cancel_clicked(dto.sale_invoice_id)

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

    def _on_edit_clicked(self, sale_invoice_id: int) -> None:
        if self._embedded:
            self.edit_requested.emit(sale_invoice_id)
            return
        dialog = SaleInvoiceFormScreen(
            self, self._engine, self._customer_engine, self._item_engine,
            self._item_free_scheme_engine, self._current_user_id,
            existing_invoice_id=sale_invoice_id,
        )
        if dialog.exec():
            self._reload_first_page()

    def _on_row_double_clicked(self, item) -> None:
        row = item.row()
        if 0 <= row < len(self._rows):
            self._on_view_clicked(self._rows[row].sale_invoice_id)

    def _on_view_clicked(self, sale_invoice_id: int) -> None:
        try:
            dto = self._engine.get_sale_invoice(sale_invoice_id)
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
            return
        dialog = SaleInvoiceViewDialog(
            self, dto, self._item_engine, self._customer_engine,
            self._engine.is_free_scheme_enabled(),
        )
        dialog.exec()

    def _on_cancel_clicked(self, sale_invoice_id: int) -> None:
        dialog = CancellationReasonDialog(
            self,
            "Enter why this Sale Invoice is being cancelled. Its stock will be restored.",
        )
        if not dialog.exec():
            return
        reason = dialog.get_reason()
        if not reason:
            return

        try:
            self._engine.cancel_sale_invoice(
                sale_invoice_id=sale_invoice_id,
                current_user_id=self._current_user_id,
                reason=reason,
            )
        except (PermissionDeniedError, RecordNotFoundError, ValidationError) as exc:
            message = "; ".join(exc.errors) if isinstance(exc, ValidationError) else str(exc)
            QMessageBox.warning(self, "Unable to Cancel Sale Invoice", message)
            return

        QMessageBox.information(self, "Sale Invoice Cancelled", "The invoice was cancelled and its stock was restored.")
        self._reload_first_page()

    

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