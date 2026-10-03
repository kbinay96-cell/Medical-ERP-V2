# screens/purchase_invoice_list_screen.py
from __future__ import annotations

import logging
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
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

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.date_engine import DateEngineError, ad_to_bs, bs_to_ad
from engines.purchase_engine import PurchaseEngine

from utils.window_chrome import apply_standard_window_chrome
from screens.purchase_invoice_view_dialog import PurchaseInvoiceViewDialog
from widgets.bs_calendar_date_picker import BSCalendarDatePicker
from widgets.purchase_invoice_calendar import PurchaseInvoiceCalendar

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ["All", "Posted", "Cancelled"]

COL_INTERNAL_REF = 0
COL_INVOICE_NUMBER = 1
COL_SUPPLIER = 2
COL_INVOICE_DATE = 3
COL_GRAND_TOTAL = 4
COL_STATUS = 5
COL_VIEW = 6
COL_EDIT = 7
COL_CANCEL = 8
COL_PRINT = 9
COLUMN_COUNT = 10


class PurchaseInvoiceListScreen(QWidget):
    """List/search/filter — mirrors screens/supplier_list_screen.py exactly.
    Filters: Supplier, Status, Date range. Actions: View (read-only detail),
    Cancel (soft-delete with reason), Print (future — not in this phase)."""
    close_requested = Signal()

    def __init__(
        self,
        parent,
        engine: PurchaseEngine,
        supplier_engine,
        item_engine,
        current_user_id: int,
        embedded: bool = False,
    ):
        super().__init__(parent)
        self._embedded = embedded
        apply_standard_window_chrome(
            self, width=1200, height=800, start_maximized=True, embedded=embedded
        )
        self._engine = engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._current_page = 1
        self._page_size = 50
        self._current_invoices: list = []
        self._sort_key = None
        self._sort_ascending = True
        self._date_filter_applied = False

        self._build_ui()
        self._connect_signals()
        self._populate_supplier_filter()
        self.refresh()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        if self._embedded:
            from utils.ui_standards import add_embedded_back_button
            add_embedded_back_button(self, root, self.close_requested.emit)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Invoice number...")
        filter_row.addWidget(self.search_input)

        filter_row.addWidget(QLabel("Supplier:"))
        self.supplier_filter_combo = QComboBox()
        filter_row.addWidget(self.supplier_filter_combo)

        filter_row.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(STATUS_OPTIONS)
        filter_row.addWidget(self.status_filter_combo)

        filter_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setObjectName("purchaseDateFrom")
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd MMM yyyy")
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setCalendarWidget(PurchaseInvoiceCalendar(self.date_from))
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setObjectName("purchaseDateTo")
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd MMM yyyy")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarWidget(PurchaseInvoiceCalendar(self.date_to))
        filter_row.addWidget(self.date_to)

        self.bs_date_from = BSCalendarDatePicker(self)
        self.bs_date_from.setMinimumWidth(130)
        self.bs_date_from.hide()
        filter_row.addWidget(self.bs_date_from)

        self.bs_date_to = BSCalendarDatePicker(self)
        self.bs_date_to.setMinimumWidth(130)
        self.bs_date_to.hide()
        filter_row.addWidget(self.bs_date_to)

        self.bs_date_mode_checkbox = QCheckBox("Use BS dates")
        self.bs_date_mode_checkbox.setToolTip(
            "Switch both date filters between AD and Bikram Sambat calendars."
        )
        filter_row.addWidget(self.bs_date_mode_checkbox)

        self.search_button = QPushButton("Filter")
        filter_row.addWidget(self.search_button)

        self.new_button = QPushButton("+ New Purchase Invoice")
        filter_row.addStretch()
        filter_row.addWidget(self.new_button)

        root.addLayout(filter_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            [
                "Ref No.", "Invoice No.", "Supplier", "Date", "Grand Total",
                "Status", "View", "Edit", "Cancel", "",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_SUPPLIER, QHeaderView.Stretch)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        for column, width in {
            COL_INTERNAL_REF: 92,
            COL_INVOICE_NUMBER: 96,
            COL_INVOICE_DATE: 88,
            COL_GRAND_TOTAL: 100,
            COL_STATUS: 80,
            COL_VIEW: 86,
            COL_EDIT: 86,
            COL_CANCEL: 86,
        }.items():
            self.table.setColumnWidth(column, width)
        self.table.setColumnHidden(COL_PRINT, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table)

        pagination_row = QHBoxLayout()
        self.prev_page_button = QPushButton("◀ Prev")
        pagination_row.addWidget(self.prev_page_button)
        self.page_label = QLabel("Page 1")
        pagination_row.addWidget(self.page_label)
        self.next_page_button = QPushButton("Next ▶")
        pagination_row.addWidget(self.next_page_button)
        pagination_row.addStretch()
        self.page_total_label = QLabel("Page Total: 0.00")
        self.page_total_label.setStyleSheet("font-weight: bold;")
        pagination_row.addWidget(self.page_total_label)
        root.addLayout(pagination_row)

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self._on_filter_clicked)
        self.new_button.clicked.connect(self._on_new_purchase_invoice_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.prev_page_button.clicked.connect(self._on_prev_page_clicked)
        self.next_page_button.clicked.connect(self._on_next_page_clicked)
        self.status_filter_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        self.bs_date_mode_checkbox.toggled.connect(self._on_bs_date_mode_toggled)

    @staticmethod
    def _qdate_to_date(value: QDate) -> date:
        return date(value.year(), value.month(), value.day())

    def _on_bs_date_mode_toggled(self, use_bs: bool) -> None:
        try:
            if use_bs:
                from_bs = ad_to_bs(self._qdate_to_date(self.date_from.date()))
                to_bs = ad_to_bs(self._qdate_to_date(self.date_to.date()))
                self.bs_date_from.set_bs_date_string(from_bs)
                self.bs_date_to.set_bs_date_string(to_bs)
            else:
                from_ad = bs_to_ad(self.bs_date_from.get_bs_date_string())
                to_ad = bs_to_ad(self.bs_date_to.get_bs_date_string())
                self.date_from.setDate(QDate(from_ad.year, from_ad.month, from_ad.day))
                self.date_to.setDate(QDate(to_ad.year, to_ad.month, to_ad.day))
        except DateEngineError as exc:
            self.bs_date_mode_checkbox.blockSignals(True)
            self.bs_date_mode_checkbox.setChecked(not use_bs)
            self.bs_date_mode_checkbox.blockSignals(False)
            QMessageBox.warning(
                self,
                "Calendar conversion unavailable",
                str(exc),
            )
            return

        self.date_from.setVisible(not use_bs)
        self.date_to.setVisible(not use_bs)
        self.bs_date_from.setVisible(use_bs)
        self.bs_date_to.setVisible(use_bs)

    def _on_filter_clicked(self) -> None:
        try:
            from_date, to_date = self._get_filter_dates_ad()
        except DateEngineError as exc:
            QMessageBox.warning(self, "Calendar conversion unavailable", str(exc))
            return

        if from_date > to_date:
            QMessageBox.warning(
                self,
                "Invalid date range",
                "The From date must be on or before the To date.",
            )
            return
        self._current_page = 1
        self._date_filter_applied = True
        self.refresh()

    def _get_filter_dates_ad(self) -> tuple[date, date]:
        if self.bs_date_mode_checkbox.isChecked():
            return (
                bs_to_ad(self.bs_date_from.get_bs_date_string()),
                bs_to_ad(self.bs_date_to.get_bs_date_string()),
            )
        return (
            self._qdate_to_date(self.date_from.date()),
            self._qdate_to_date(self.date_to.date()),
        )

    def _on_status_filter_changed(self, _index: int) -> None:
        self._current_page = 1
        self.refresh()

    def _populate_supplier_filter(self) -> None:
        from utils.searchable_combo_helper import populate_searchable_combo

        suppliers, _ = self._supplier_engine.search_suppliers(page=1, page_size=1000)
        self.supplier_filter_combo.addItem("All Suppliers", None)
        populate_searchable_combo(
            self.supplier_filter_combo,
            items=suppliers,
            display_attr="supplier_name",
            data_attr="supplier_id",
            keep_existing_items=True,
        )

    def refresh(self) -> None:
        status = self.status_filter_combo.currentData()
        if status is None:
            status = self.status_filter_combo.currentText()
        status_filter = None if status == "All" else status

        date_from_ad = None
        date_to_ad = None
        if self._date_filter_applied:
            try:
                from_date, to_date = self._get_filter_dates_ad()
            except DateEngineError as exc:
                QMessageBox.warning(self, "Calendar conversion unavailable", str(exc))
                return
            date_from_ad = from_date.isoformat()
            date_to_ad = to_date.isoformat()

        invoices, total_count = self._engine.search_purchase_invoices(
            search_text=self.search_input.text().strip() or None,
            supplier_id=self.supplier_filter_combo.currentData(),
            status=status_filter,
            date_from_ad=date_from_ad,
            date_to_ad=date_to_ad,
            include_deleted=status_filter == "Cancelled",
            page=self._current_page,
            page_size=self._page_size,
            order_by=self._sort_key,
            order_dir="ASC" if self._sort_ascending else "DESC",
        )

        self._current_invoices = invoices

        self.table.setRowCount(0)
        for invoice in invoices:
            self._add_row(invoice)

        total_pages = max(1, (total_count + self._page_size - 1) // self._page_size)
        self.page_label.setText(f"Page {self._current_page} of {total_pages}")
        self.prev_page_button.setEnabled(self._current_page > 1)
        self.next_page_button.setEnabled(self._current_page < total_pages)

        page_total = sum(invoice.grand_total for invoice in invoices)
        self.page_total_label.setText(f"Page Total: {page_total:.2f}")

    # -- data ---------------------------------------------------------------

    def _on_header_clicked(self, column: int) -> None:
        """Server-side sort — the Model's ORDER BY handles all pages, not
        just what's currently loaded. Click the same column again to
        reverse the order."""
        sort_keys = {
            COL_INTERNAL_REF: "internal_ref_number",
            COL_INVOICE_NUMBER: "invoice_number",
            COL_SUPPLIER: "supplier_name",
            COL_INVOICE_DATE: "invoice_date_bs",
            COL_GRAND_TOTAL: "grand_total",
            COL_STATUS: "status",
        }
        order_by = sort_keys.get(column)
        if order_by is None:
            return

        if self._sort_key == order_by:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_key = order_by
            self._sort_ascending = True

        order = Qt.AscendingOrder if self._sort_ascending else Qt.DescendingOrder
        self.table.horizontalHeader().setSortIndicator(column, order)
        self._current_page = 1
        self.refresh()

    def _on_prev_page_clicked(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.refresh()

    def _on_next_page_clicked(self) -> None:
        self._current_page += 1
        self.refresh()

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        ref_item = self.table.item(row, COL_INTERNAL_REF)
        if ref_item is None:
            return
        status_item = self.table.item(row, COL_STATUS)
        self._on_view_clicked(
            ref_item.data(Qt.UserRole),
            include_deleted=bool(status_item and status_item.text() == "Cancelled"),
        )

    def _add_row(self, invoice) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        ref_item = QTableWidgetItem(invoice.internal_ref_number)
        ref_item.setData(Qt.UserRole, invoice.purchase_invoice_id)
        self.table.setItem(row, COL_INTERNAL_REF, ref_item)

        self.table.setItem(row, COL_INVOICE_NUMBER, QTableWidgetItem(invoice.invoice_number))

        supplier_name = self._supplier_engine.get_supplier(invoice.supplier_id).supplier_name
        self.table.setItem(row, COL_SUPPLIER, QTableWidgetItem(supplier_name))
        self.table.setItem(row, COL_INVOICE_DATE, QTableWidgetItem(invoice.invoice_date_bs))
        self.table.setItem(row, COL_GRAND_TOTAL, QTableWidgetItem(f"{invoice.grand_total:.2f}"))
        self.table.setItem(row, COL_STATUS, QTableWidgetItem(invoice.status))

        view_button = QPushButton("View")
        view_button.setToolTip("View / print this invoice (read-only).")
        view_button.clicked.connect(
            lambda _, pid=invoice.purchase_invoice_id, cancelled=invoice.status == "Cancelled":
            self._on_view_clicked(pid, include_deleted=cancelled)
        )
        self.table.setCellWidget(row, COL_VIEW, view_button)

        edit_button = QPushButton("Edit")
        is_po_linked = getattr(invoice, "purchase_order_id", None) is not None
        if invoice.status == "Cancelled":
            edit_button.setEnabled(False)
            edit_button.setToolTip("Cancelled invoices cannot be edited.")
        elif is_po_linked:
            edit_button.setEnabled(False)
            edit_button.setToolTip(
                "This invoice is linked to a Purchase Order and cannot be edited. "
                "Use Purchase Return for corrections instead."
            )
        edit_button.clicked.connect(
            lambda _, pid=invoice.purchase_invoice_id: self._on_edit_clicked(pid)
        )
        self.table.setCellWidget(row, COL_EDIT, edit_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setEnabled(invoice.status != "Cancelled")
        cancel_button.clicked.connect(
            lambda _, pid=invoice.purchase_invoice_id: self._on_cancel_clicked(pid)
        )
        self.table.setCellWidget(row, COL_CANCEL, cancel_button)

    # -- actions ------------------------------------------------------------

    def _on_new_purchase_invoice_clicked(self) -> None:
        from screens.purchase_invoice_form_screen import PurchaseInvoiceFormScreen
        dialog = PurchaseInvoiceFormScreen(
            parent=self,
            engine=self._engine,
            purchase_order_engine=self._engine._purchase_order_engine,
            supplier_engine=self._supplier_engine,
            item_engine=self._item_engine,
            current_user_id=self._current_user_id,
        )
        dialog.exec()
        self.refresh()

    def _on_edit_clicked(self, purchase_invoice_id: int) -> None:
        from screens.purchase_invoice_form_screen import PurchaseInvoiceFormScreen
        dialog = PurchaseInvoiceFormScreen(
            parent=self,
            engine=self._engine,
            purchase_order_engine=self._engine._purchase_order_engine,
            supplier_engine=self._supplier_engine,
            item_engine=self._item_engine,
            current_user_id=self._current_user_id,
            existing_invoice_id=purchase_invoice_id,
        )
        dialog.exec()
        self.refresh()

    def _on_view_clicked(self, purchase_invoice_id: int, include_deleted: bool = False) -> None:
        try:
            invoice = self._engine.get_purchase_invoice(
                purchase_invoice_id,
                include_deleted=include_deleted,
            )
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Not Found", str(exc))
            return

        supplier_name = self._supplier_engine.get_supplier(invoice.supplier_id).supplier_name
        dialog = PurchaseInvoiceViewDialog(
            parent=self,
            invoice=invoice,
            supplier_name=supplier_name,
            item_engine=self._item_engine,
            supplier_engine=self._supplier_engine,
        )
        dialog.exec()

    def _on_cancel_clicked(self, purchase_invoice_id: int) -> None:
        reason, accepted = QInputDialog.getText(
            self,
            "Cancel Purchase Invoice",
            "Cancellation reason:",
        )
        if not accepted:
            return
        if not reason.strip():
            QMessageBox.warning(self, "Reason Required", "Please enter a cancellation reason.")
            return

        if QMessageBox.question(
            self,
            "Confirm Cancellation",
            "Cancel this purchase invoice? Its stock remains in the ledger; use Purchase Return "
            "to reverse received goods.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        try:
            self._engine.cancel_purchase_invoice(
                purchase_invoice_id,
                current_user_id=self._current_user_id,
                reason=reason,
            )
        except (RecordNotFoundError, ValidationError) as exc:
            QMessageBox.warning(self, "Cannot Cancel", str(exc))
            return
        except Exception:
            logger.exception("Failed to cancel purchase invoice %s", purchase_invoice_id)
            QMessageBox.critical(self, "Error", "Could not cancel the purchase invoice.")
            return

        self.refresh()

    