from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from engines.company_engine import CompanyEngine
from engines.session_manager import get_current_session

logger = logging.getLogger(__name__)

COL_SN = 0
COL_ITEM = 1
COL_BATCH_NO = 2
COL_EXPIRY = 3
COL_MRP = 4
COL_QTY = 5
COL_FREE_QTY = 6
COL_RATE = 7
COL_AMOUNT = 8
COL_DISCOUNT_PCT = 9
COLUMN_COUNT = 10

COLUMN_HEADERS = [
    "SN.",
    "Particulars",
    "Batch_No",
    "Expiry",
    "MRP",
    "Qty.",
    "Free",
    "Rate",
    "Amount",
    "Dis%",
]


class PurchaseInvoiceViewDialog(QDialog):
    """Read-only Purchase Invoice detail dialog, styled after the physical
    Monika Medico bill layout. Company letterhead comes from the currently
    logged-in company (this app's own company), NOT the supplier -- the
    "Supplier Details" box shows the supplier's info instead of the
    reference bill's "Customer Details" box, since this is Purchase."""

    def __init__(self, parent, invoice, supplier_name, item_engine, supplier_engine):
        super().__init__(parent)
        self._invoice = invoice
        self._item_engine = item_engine
        self._supplier_engine = supplier_engine
        self._supplier_name = supplier_name

        self.setWindowTitle(f"Purchase Invoice — {invoice.internal_ref_number}")
        self.resize(1050, 750)

        root = QVBoxLayout(self)

        root.addWidget(self._build_details_section(invoice))
        root.addWidget(self._build_table(invoice), stretch=1)
        root.addWidget(self._build_summary_section(invoice))

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        root.addLayout(button_row)

    # -- supplier + invoice details boxes --------------------------------

    def _build_details_section(self, invoice) -> QFrame:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(20)

        supplier_box = QFrame()
        supplier_box.setFrameShape(QFrame.StyledPanel)
        supplier_layout = QGridLayout(supplier_box)
        supplier_layout.setContentsMargins(10, 8, 10, 8)
        supplier_layout.setHorizontalSpacing(12)
        supplier_layout.setVerticalSpacing(6)
        supplier_layout.addWidget(QLabel("<b>Supplier Details</b>"), 0, 0, 1, 2)
        supplier_layout.addWidget(QLabel("Name:"), 1, 0)
        supplier_layout.addWidget(QLabel(self._supplier_name), 1, 1)

        supplier = None
        try:
            supplier = self._supplier_engine.get_supplier(invoice.supplier_id)
        except Exception:
            logger.exception("Could not load supplier details for invoice view.")

        if supplier and supplier.address:
            supplier_layout.addWidget(QLabel("Address:"), 2, 0)
            supplier_layout.addWidget(QLabel(supplier.address), 2, 1)
        if supplier and supplier.phone_no:
            supplier_layout.addWidget(QLabel("Phone No:"), 3, 0)
            supplier_layout.addWidget(QLabel(supplier.phone_no), 3, 1)
        if supplier and supplier.pan_vat_no:
            supplier_layout.addWidget(QLabel("Pan No:"), 4, 0)
            supplier_layout.addWidget(QLabel(supplier.pan_vat_no), 4, 1)

        layout.addWidget(supplier_box, stretch=1)

        invoice_box = QFrame()
        invoice_box.setFrameShape(QFrame.StyledPanel)
        invoice_layout = QGridLayout(invoice_box)
        invoice_layout.setContentsMargins(10, 8, 10, 8)
        invoice_layout.setHorizontalSpacing(12)
        invoice_layout.setVerticalSpacing(6)
        invoice_layout.addWidget(QLabel("<b>Invoice Details</b>"), 0, 0, 1, 2)
        invoice_layout.addWidget(QLabel("Invoice No:"), 1, 0)
        invoice_layout.addWidget(QLabel(invoice.invoice_number), 1, 1)
        invoice_layout.addWidget(QLabel("Internal Ref:"), 2, 0)
        invoice_layout.addWidget(QLabel(invoice.internal_ref_number), 2, 1)
        invoice_layout.addWidget(QLabel("Invoice Miti:"), 3, 0)
        invoice_layout.addWidget(QLabel(invoice.invoice_date_bs), 3, 1)
        invoice_layout.addWidget(QLabel("Invoice Date:"), 4, 0)
        invoice_layout.addWidget(QLabel(invoice.invoice_date_ad or ""), 4, 1)
        invoice_layout.addWidget(QLabel("Status:"), 5, 0)
        invoice_layout.addWidget(QLabel(invoice.status), 5, 1)

        layout.addWidget(invoice_box, stretch=1)

        return frame

    # -- table --------------------------------------------------------------

    def _build_table(self, invoice) -> QTableWidget:
        table = QTableWidget(len(invoice.lines), COLUMN_COUNT, self)
        table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)

        for row, line in enumerate(invoice.lines):
            item_name = self._resolve_item_name(line.item_id)
            expiry_display = f"{line.expiry_month:02d}/{line.expiry_year}"
            amount = (line.qty or 0) * (line.purchase_rate or 0)

            table.setItem(row, COL_SN, QTableWidgetItem(str(row + 1)))
            table.setItem(row, COL_ITEM, QTableWidgetItem(item_name))
            table.setItem(row, COL_BATCH_NO, QTableWidgetItem(line.batch_no or ""))
            table.setItem(row, COL_EXPIRY, QTableWidgetItem(expiry_display))
            table.setItem(row, COL_MRP, QTableWidgetItem(f"{line.mrp:.2f}"))
            table.setItem(row, COL_QTY, QTableWidgetItem(f"{line.qty:.2f}"))
            table.setItem(row, COL_FREE_QTY, QTableWidgetItem(f"{line.free_qty:.2f}"))
            table.setItem(row, COL_RATE, QTableWidgetItem(f"{line.purchase_rate:.2f}"))
            table.setItem(row, COL_AMOUNT, QTableWidgetItem(f"{amount:.2f}"))
            table.setItem(row, COL_DISCOUNT_PCT, QTableWidgetItem(f"{line.discount_percent:.2f}"))

        return table

    # -- summary --------------------------------------------------------------

    def _build_summary_section(self, invoice) -> QFrame:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setHorizontalSpacing(30)
        layout.setVerticalSpacing(6)

        basic_amount = sum((line.qty or 0) * (line.purchase_rate or 0) for line in invoice.lines)
        product_discount = sum(line.discount_amount or 0 for line in invoice.lines)
        cc_on_free_goods = sum(line.cc_amount or 0 for line in invoice.lines)

        current_balance = 0.0
        try:
            current_balance = self._supplier_engine.get_current_balance(invoice.supplier_id)
        except Exception:
            logger.exception("Could not resolve current balance for invoice view.")

        layout.addWidget(self._field_label("Basic Amount:", f"{basic_amount:.2f}"), 0, 0)
        layout.addWidget(self._field_label("Product Discount:", f"{product_discount:.2f}"), 0, 1)
        layout.addWidget(self._field_label("CC On Free Goods:", f"{cc_on_free_goods:.2f}"), 1, 0)
        layout.addWidget(
            self._field_label("Round Off:", f"{invoice.round_off_amount:.2f}"), 1, 1
        )

        net_label = self._field_label("Net Total:", f"{invoice.grand_total:.2f}")
        net_font = QFont()
        net_font.setPointSize(11)
        net_font.setBold(True)
        net_label.setFont(net_font)
        layout.addWidget(net_label, 2, 0)

        layout.addWidget(
            self._field_label("Current Balance:", f"{current_balance:.2f}"), 2, 1
        )

        words_label = QLabel(f"<b>In Words:</b> {self._amount_in_words(invoice.grand_total)}")
        words_label.setWordWrap(True)
        layout.addWidget(words_label, 3, 0, 1, 2)

        return frame

    # -- helpers ----------------------------------------------------------

    def _resolve_item_name(self, item_id: int) -> str:
        try:
            return self._item_engine.get_item(item_id).item_name
        except Exception:
            return f"(item #{item_id} not found)"

    @staticmethod
    def _field_label(caption: str, value) -> QLabel:
        return QLabel(f"<b>{caption}</b> {value}")

    @staticmethod
    def _amount_in_words(amount: float) -> str:
        """Simple English amount-in-words converter (Rupees only, no
        paisa/decimal support needed for this bill format)."""
        ones = [
            "", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen",
            "Nineteen",
        ]
        tens = [
            "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty",
            "Seventy", "Eighty", "Ninety",
        ]

        def two_digits(n: int) -> str:
            if n < 20:
                return ones[n]
            return (tens[n // 10] + (f" {ones[n % 10]}" if n % 10 else "")).strip()

        def three_digits(n: int) -> str:
            if n >= 100:
                return f"{ones[n // 100]} Hundred" + (
                    f" {two_digits(n % 100)}" if n % 100 else ""
                )
            return two_digits(n)

        n = int(round(amount))
        if n == 0:
            return "Zero Only"

        crore, n = divmod(n, 10_000_000)
        lakh, n = divmod(n, 100_000)
        thousand, n = divmod(n, 1_000)
        hundred = n

        parts = []
        if crore:
            parts.append(f"{three_digits(crore)} Crore")
        if lakh:
            parts.append(f"{two_digits(lakh)} Lakh")
        if thousand:
            parts.append(f"{two_digits(thousand)} Thousand")
        if hundred:
            parts.append(three_digits(hundred))

        return " ".join(parts) + " Only"