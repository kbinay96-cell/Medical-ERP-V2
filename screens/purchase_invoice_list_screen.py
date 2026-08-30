# screens/purchase_invoice_list_screen.py
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from engines.purchase_engine import PurchaseEngine

from engines.purchase_engine import PurchaseEngine
from screens.purchase_invoice_view_dialog import PurchaseInvoiceViewDialog

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ["All", "Posted", "Cancelled"]

COL_INTERNAL_REF = 0
COL_INVOICE_NUMBER = 1
COL_SUPPLIER = 2
COL_INVOICE_DATE = 3
COL_GRAND_TOTAL = 4
COL_STATUS = 5
COL_VIEW = 6
COL_CANCEL = 7
COL_PRINT = 8
COLUMN_COUNT = 9


class PurchaseInvoiceListScreen(QWidget):
    """List/search/filter — mirrors screens/supplier_list_screen.py exactly.
    Filters: Supplier, Status, Date range. Actions: View (read-only detail),
    Cancel (soft-delete with reason), Print (future — not in this phase)."""

    def __init__(self, parent, engine: PurchaseEngine, supplier_engine, item_engine, current_user_id: int):
        super().__init__(parent)
        self._engine = engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._current_page = 1
        self._page_size = 50
        self._current_invoices: list = []
        self._sort_key = None
        self._sort_ascending = True

        self._build_ui()
        self._connect_signals()
        self._populate_supplier_filter()
        self.refresh()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

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
        self.date_from.setCalendarPopup(True)
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        filter_row.addWidget(self.date_to)

        self.search_button = QPushButton("Filter")
        filter_row.addWidget(self.search_button)

        self.new_button = QPushButton("+ New Purchase Invoice")
        filter_row.addStretch()
        filter_row.addWidget(self.new_button)

        root.addLayout(filter_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["Ref No.", "Invoice No.", "Supplier", "Date", "Grand Total", "Status", "", "", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(COL_SUPPLIER, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
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

    def _on_filter_clicked(self) -> None:
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
        status = self.status_filter_combo.currentText()
        status_filter = None if status == "All" else status

        invoices, total_count = self._engine.search_purchase_invoices(
            search_text=self.search_input.text().strip() or None,
            supplier_id=self.supplier_filter_combo.currentData(),
            status=status_filter,
            include_deleted=False,
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
        self._on_view_clicked(ref_item.data(Qt.UserRole))

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
        view_button.clicked.connect(
            lambda _, pid=invoice.purchase_invoice_id: self._on_view_clicked(pid)
        )
        self.table.setCellWidget(row, COL_VIEW, view_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setEnabled(invoice.status == "Posted")
        cancel_button.clicked.connect(
            lambda _, pid=invoice.purchase_invoice_id: self._on_cancel_clicked(pid)
        )
        self.table.setCellWidget(row, COL_CANCEL, cancel_button)

        print_button = QPushButton("Print")
        print_button.setEnabled(False)
        print_button.setToolTip("Coming in a future phase")
        self.table.setCellWidget(row, COL_PRINT, print_button)

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

    def _on_view_clicked(self, purchase_invoice_id: int) -> None:
        try:
            invoice = self._engine.get_purchase_invoice(purchase_invoice_id)
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
        """Soft-delete with reason — does NOT reverse stock_ledger entries;
        that's a separate, explicit Purchase Return flow."""
        reason, ok = QInputDialog.getText(
            self, "Cancel Purchase Invoice", "Reason for cancellation:"
        )
        if not ok or not reason.strip():
            return

        try:
            self._engine.cancel_purchase_invoice(
                purchase_invoice_id, self._current_user_id, reason.strip()
            )
        except (RecordNotFoundError, ValidationError) as exc:
            QMessageBox.warning(self, "Cannot Cancel", str(exc))
            return
        except Exception:
            logger.exception("Failed to cancel purchase invoice %s", purchase_invoice_id)
            QMessageBox.critical(self, "Error", "Could not cancel the purchase invoice.")
            return

        self.refresh()