"""Create Purchase Returns against posted Purchase Invoices."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engines.date_engine import DateEngineError, ad_to_bs, bs_to_ad
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.purchase_engine import PurchaseEngine
from engines.purchase_return_engine import PurchaseReturnEngine
from utils import message as msg
from widgets.bs_calendar_date_picker import BSCalendarDatePicker

logger = logging.getLogger(__name__)

SETTLEMENT_MODES = ("Adjust Against Payable", "Supplier Advance", "Cash Refund")
PAGE_SIZE = 200


class PurchaseReturnFormScreen(QWidget):
    """Create and post a Purchase Return; quantities are independently capped."""

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: PurchaseReturnEngine,
        purchase_invoice_engine: PurchaseEngine,
        supplier_engine,
        item_engine,
        current_user_id: int,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._purchase_engine = purchase_invoice_engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._invoice_results = []
        self._lines: list[dict] = []
        self._build_ui()
        self._load_suppliers()
        self._connect_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.lblTitle = QLabel("New Purchase Return")
        self.lblTitle.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(self.lblTitle)
        header.addStretch(1)
        self.btnBack = QPushButton("Back")
        header.addWidget(self.btnBack)
        root.addLayout(header)

        source_box = QGroupBox("Posted Purchase Invoice")
        source_form = QFormLayout(source_box)
        self.cmbSupplier = QComboBox()
        self.cmbSupplier.addItem("Select supplier...", None)
        self.txtInvoiceSearch = QLineEdit()
        self.txtInvoiceSearch.setPlaceholderText("Supplier invoice or internal reference")
        search_row = QHBoxLayout()
        search_row.addWidget(self.txtInvoiceSearch, 1)
        self.btnFindInvoices = QPushButton("Find Invoices")
        search_row.addWidget(self.btnFindInvoices)
        search_widget = QWidget()
        search_widget.setLayout(search_row)
        self.cmbInvoice = QComboBox()
        self.cmbInvoice.addItem("Select posted invoice...", None)
        self.btnLoadItems = QPushButton("Load Items")
        invoice_row = QHBoxLayout()
        invoice_row.addWidget(self.cmbInvoice, 1)
        invoice_row.addWidget(self.btnLoadItems)
        invoice_widget = QWidget()
        invoice_widget.setLayout(invoice_row)
        source_form.addRow("Supplier", self.cmbSupplier)
        source_form.addRow("Search", search_widget)
        source_form.addRow("Invoice", invoice_widget)
        self.lblInvoiceInfo = QLabel("Select a posted invoice and load its items.")
        self.lblInvoiceInfo.setWordWrap(True)
        source_form.addRow("Source", self.lblInvoiceInfo)
        root.addWidget(source_box)

        self.tblItems = QTableWidget(0, 10)
        self.tblItems.setHorizontalHeaderLabels([
            "Item", "Batch", "Expiry", "Original Qty", "Returned Qty",
            "Returnable Qty", "Original Free", "Returned Free",
            "Return Qty", "Return Free Qty",
        ])
        self.tblItems.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tblItems.verticalHeader().setVisible(False)
        self.tblItems.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblItems.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.tblItems, 1)

        header_box = QGroupBox("Return Details")
        detail_form = QFormLayout(header_box)
        self.dtReturnDate = BSCalendarDatePicker(self)
        self.dtReturnDate.set_bs_date_string(ad_to_bs(date.today()))
        detail_form.addRow("Return Date (BS)", self.dtReturnDate)
        self.cmbSettlement = QComboBox()
        self.cmbSettlement.addItems(SETTLEMENT_MODES)
        detail_form.addRow("Settlement", self.cmbSettlement)
        self.txtReason = QTextEdit()
        self.txtReason.setMaximumHeight(64)
        self.txtReason.setPlaceholderText("Required: explain why the goods are being returned")
        detail_form.addRow("Return Reason", self.txtReason)
        self.txtRemarks = QLineEdit()
        self.txtRemarks.setPlaceholderText("Optional")
        detail_form.addRow("Remarks", self.txtRemarks)
        root.addWidget(header_box)

        footer = QHBoxLayout()
        self.lblTotals = QLabel("Return Qty: 0    Free Qty: 0")
        footer.addWidget(self.lblTotals)
        footer.addStretch(1)
        self.btnPost = QPushButton("Post Purchase Return")
        self.btnPost.setObjectName("primaryButton")
        self.btnPost.setEnabled(False)
        footer.addWidget(self.btnPost)
        root.addLayout(footer)

    def _connect_signals(self) -> None:
        self.btnBack.clicked.connect(self.close_requested.emit)
        self.btnFindInvoices.clicked.connect(self._load_invoices)
        self.txtInvoiceSearch.returnPressed.connect(self._load_invoices)
        self.btnLoadItems.clicked.connect(self._load_selected_invoice)
        self.btnPost.clicked.connect(self._post_return)

    def _load_suppliers(self) -> None:
        try:
            suppliers = self._supplier_engine.get_active_suppliers()
        except Exception:
            logger.exception("Failed to load suppliers for Purchase Return.")
            msg.show_error("Could not load suppliers.")
            return
        for supplier in suppliers:
            self.cmbSupplier.addItem(supplier.supplier_name, supplier.supplier_id)

    def _load_invoices(self) -> None:
        supplier_id = self.cmbSupplier.currentData()
        if supplier_id is None:
            msg.show_error("Select a supplier first.")
            return
        try:
            results, _total = self._purchase_engine.search_purchase_invoices(
                search_text=self.txtInvoiceSearch.text().strip() or None,
                supplier_id=supplier_id,
                status="Posted",
                page=1,
                page_size=PAGE_SIZE,
                order_dir="DESC",
            )
        except Exception:
            logger.exception("Failed to search posted purchase invoices.")
            msg.show_error("Could not load posted Purchase Invoices.")
            return

        self._invoice_results = results
        self.cmbInvoice.blockSignals(True)
        self.cmbInvoice.clear()
        self.cmbInvoice.addItem("Select posted invoice...", None)
        for invoice in results:
            label = f"{invoice.internal_ref_number} | {invoice.invoice_number}"
            self.cmbInvoice.addItem(label, invoice.purchase_invoice_id)
        self.cmbInvoice.blockSignals(False)
        if not results:
            msg.show_info("No posted Purchase Invoices matched the selected supplier and search.")

    def _load_selected_invoice(self) -> None:
        purchase_invoice_id = self.cmbInvoice.currentData()
        if purchase_invoice_id is None:
            msg.show_error("Select a posted Purchase Invoice.")
            return
        invoice = next(
            (entry for entry in self._invoice_results if entry.purchase_invoice_id == purchase_invoice_id),
            None,
        )
        if invoice is None:
            msg.show_error("The selected invoice is no longer available. Search again.")
            return
        try:
            lines = self._engine.get_returnable_lines(purchase_invoice_id)
        except (RecordNotFoundError, ValidationError) as exc:
            msg.show_error(str(exc))
            return
        except Exception:
            logger.exception("Failed to load returnable lines for invoice %s.", purchase_invoice_id)
            msg.show_error("Could not load returnable invoice items.")
            return

        self._lines = lines
        self.tblItems.setRowCount(0)
        for line in lines:
            row = self.tblItems.rowCount()
            self.tblItems.insertRow(row)
            try:
                item_name = self._item_engine.get_item(line["item_id"]).item_name
            except Exception:
                logger.exception("Could not resolve item name for item %s.", line["item_id"])
                item_name = f"Item {line['item_id']}"
            expiry = f"{int(line.get('expiry_month') or 0):02d}/{line.get('expiry_year') or ''}"
            values = (
                item_name,
                line.get("batch_no", ""),
                expiry,
                line.get("qty", 0),
                line.get("already_returned_qty", 0),
                line.get("remaining_returnable_qty", 0),
                line.get("free_qty", 0),
                line.get("already_returned_free_qty", 0),
            )
            for column, value in enumerate(values):
                self.tblItems.setItem(row, column, QTableWidgetItem(str(value)))
            paid_spin = self._quantity_editor(float(line.get("remaining_returnable_qty", 0) or 0))
            free_spin = self._quantity_editor(float(line.get("remaining_returnable_free_qty", 0) or 0))
            paid_spin.valueChanged.connect(self._update_totals)
            free_spin.valueChanged.connect(self._update_totals)
            self.tblItems.setCellWidget(row, 8, paid_spin)
            self.tblItems.setCellWidget(row, 9, free_spin)
        self.lblInvoiceInfo.setText(
            f"Invoice: {invoice.internal_ref_number} / {invoice.invoice_number}    "
            f"Date: {invoice.invoice_date_bs}    Supplier: "
            f"{self.cmbSupplier.currentText()}"
        )
        self.btnPost.setEnabled(bool(lines))
        self._update_totals()

    @staticmethod
    def _quantity_editor(maximum: float) -> QDoubleSpinBox:
        editor = QDoubleSpinBox()
        editor.setDecimals(2)
        editor.setRange(0, max(0.0, maximum))
        editor.setSingleStep(1)
        editor.setMaximumWidth(110)
        editor.setToolTip(f"Maximum returnable quantity: {maximum:g}")
        return editor

    def _update_totals(self, *_args) -> None:
        paid_qty = sum(
            self.tblItems.cellWidget(row, 8).value()
            for row in range(self.tblItems.rowCount())
            if self.tblItems.cellWidget(row, 8) is not None
        )
        free_qty = sum(
            self.tblItems.cellWidget(row, 9).value()
            for row in range(self.tblItems.rowCount())
            if self.tblItems.cellWidget(row, 9) is not None
        )
        self.lblTotals.setText(f"Return Qty: {paid_qty:g}    Free Qty: {free_qty:g}")

    def _collect_return_lines(self) -> list[dict]:
        payload = []
        for row, line in enumerate(self._lines):
            paid = self.tblItems.cellWidget(row, 8).value()
            free = self.tblItems.cellWidget(row, 9).value()
            if paid > 0 or free > 0:
                payload.append({
                    "purchase_invoice_item_id": line["purchase_invoice_item_id"],
                    "return_qty": paid,
                    "return_free_qty": free,
                })
        return payload

    def _post_return(self) -> None:
        purchase_invoice_id = self.cmbInvoice.currentData()
        supplier_id = self.cmbSupplier.currentData()
        lines = self._collect_return_lines()
        reason = self.txtReason.toPlainText().strip()
        if purchase_invoice_id is None:
            msg.show_error("Select and load a posted Purchase Invoice first.")
            return
        if not reason:
            msg.show_error("Return reason is required.")
            return
        if not lines:
            msg.show_error("Enter a paid or free return quantity for at least one item.")
            return
        try:
            return_date_ad = bs_to_ad(self.dtReturnDate.get_bs_date_string())
            result = self._engine.create_return(
                purchase_invoice_id=purchase_invoice_id,
                supplier_id=supplier_id,
                return_date_ad=return_date_ad,
                return_reason=reason,
                settlement_mode=self.cmbSettlement.currentText(),
                return_lines=lines,
                created_by=self._current_user_id,
                remarks=self.txtRemarks.text().strip() or None,
                status="Posted",
            )
        except DateEngineError as exc:
            msg.show_error(str(exc))
            return
        except (ValidationError, RecordNotFoundError) as exc:
            msg.show_error(str(exc))
            return
        except Exception:
            logger.exception("Failed to post Purchase Return.")
            msg.show_error("An unexpected error occurred while posting the Purchase Return.")
            return
        msg.show_info(f"Purchase Return {result.return_number} posted successfully.")
        self.saved.emit()
