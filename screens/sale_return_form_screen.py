"""
screens/sale_return_form_screen.py

Sale Return Form Screen — create a new Sale Return against a posted Sale Invoice,
or view (read-only) an existing one.

Rewritten against CONFIRMED real signatures (verified via Cline against the actual repo):
    - engines.sale_return_engine.SaleReturnEngine.create_return(
          sale_invoice_id, customer_id, return_date_ad, return_reason, refund_mode,
          return_lines: list[dict] (each: {"sale_invoice_item_id", "return_qty", "remarks"?}),
          created_by, remarks=None, status="Posted"
      ) -> SaleReturnDTO   [raises RecordNotFoundError, ValidationError]
    - engines.sale_return_engine.SaleReturnEngine.get_by_id(sale_return_id) -> Optional[SaleReturnDTO]
    - engines.sale_return_engine.SaleReturnEngine.get_returnable_lines(sale_invoice_id) -> list[dict]
          (each dict confirmed to include "remaining_returnable_qty"; other keys assumed by
          convention — item_name, batch_no, sale_invoice_item_id, rate, discount_percent,
          cc_percent — STILL NEEDS CONFIRMATION, see SALE_RETURN_WIRING_NOTES.md Step 2)
    - engines.sale_return_engine.SaleReturnEngine.cancel_return(
          sale_return_id, cancellation_reason, updated_by) -> SaleReturnDTO
    - engines.sale_engine.SaleEngine.search_sale_invoices(search_text=..., ...) ->
          tuple[list[SaleInvoiceDTO], int]   (there is NO get_by_invoice_number on SaleEngine)
    - engines.exceptions: ValidationError, RecordNotFoundError
    - utils.message: show_error(message, title=...), show_info(message, title=...)
    - widgets.bs_calendar_date_picker.BSCalendarDatePicker
    - screens.cancellation_reason_dialog.CancellationReasonDialog.get_reason() -> Optional[str]
    - engines.customer_engine.get_active_customers() -> list[dict] (customer_id/customer_code/customer_name)

KNOWN GAP (flagged, not silently assumed): the real SaleReturnEngine has no update/edit method
for an existing Draft — only create_return / get_by_id / search / get_returnable_lines /
cancel_return / delete_draft. So this screen supports exactly two modes:
    1. CREATE  — pick an invoice, enter return lines, Save as Draft or Post directly.
    2. VIEW    — read-only display of an existing return, with a Cancel action if Posted.
There is no "edit an existing Draft" mode until Cline confirms whether an update method
exists elsewhere. See SALE_RETURN_WIRING_NOTES.md Step 2 for the exact follow-up question.

Naming convention: btnX / txtX / lblX / tblX / cmbX / dtX / grpX per project standard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from engines.customer_engine import get_active_customers, get_active_customers_by_area, get_lookup_data
from engines.date_engine import ad_to_bs, bs_to_ad
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_engine import SaleEngine
from engines.sale_return_engine import SaleReturnEngine
from screens.cancellation_reason_dialog import CancellationReasonDialog
from utils import message as msg
from widgets.bs_calendar_date_picker import BSCalendarDatePicker

logger = logging.getLogger(__name__)

REFUND_MODES = ["Cash Refund", "Adjust Against Invoice", "Advance"]
POSTED_INVOICE_STATUS = "Posted"  # SaleInvoiceDTO.status value expected on a postable invoice

RETURN_QTY_COLUMN = 6


@dataclass
class _ReturnableLine:
    """In-memory row model built from get_returnable_lines()."""

    sale_invoice_item_id: int
    item_name: str
    batch_no: str
    original_qty: float
    remaining_returnable_qty: float
    rate: float
    discount_percent: float
    cc_percent: float

    def estimated_line_total(self, return_qty: float) -> float:
        gross = return_qty * self.rate
        discount = gross * (self.discount_percent / 100.0)
        taxable = gross - discount
        cc = taxable * (self.cc_percent / 100.0)
        return round(taxable + cc, 2)


class SaleReturnFormScreen(QWidget):
    """
    Create a new Sale Return, or view an existing one read-only.

    Embedded pattern (matches ReceiptFormScreen):
        saved            -> emitted after a successful create / cancel
        close_requested  -> emitted when the user wants to go back to the list
    """

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        sale_return_engine: SaleReturnEngine,
        sale_engine: SaleEngine,
        current_user_id: int,
        sale_return_id: Optional[int] = None,
        embedded: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sale_return_engine = sale_return_engine
        self._sale_engine = sale_engine
        self._current_user_id = current_user_id
        self._sale_return_id = sale_return_id
        self._embedded = embedded
        self._view_mode = sale_return_id is not None

        self._sale_invoice_id: Optional[int] = None
        self._customer_id: Optional[int] = None
        self._status: str = "Draft"
        self._lines: list[_ReturnableLine] = []
        self._customer_names: dict[int, str] = {}

        self._build_ui()
        self._populate_area_combo()
        self._populate_customer_combo()
        self._wire_events()

        if self._view_mode:
            self._load_existing_return(self._sale_return_id)
        else:
            self._set_editable(True)

    # ------------------------------------------------------------------
    def _field_label(self, text: str) -> QLabel:
        """Fixed-width label so every field's gap-to-widget is consistent across rows."""
        label = QLabel(text)
        label.setFixedWidth(100)
        return label

    def _make_searchable(self, combo: QComboBox) -> None:
        """Editable combo with type-ahead, match-anywhere, case-insensitive filtering."""
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        completer = QCompleter(combo.model(), combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(completer)

    def _populate_area_combo(self) -> None:
        """Areas come from customer_engine.get_lookup_data()["areas"] (confirmed real source)."""
        self.cmbArea.blockSignals(True)
        self.cmbArea.clear()
        self.cmbArea.addItem("All Areas", None)
        try:
            areas = get_lookup_data().get("areas", [])
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load areas")
            areas = []
        for area in areas:
            self.cmbArea.addItem(area.get("area_name", str(area.get("area_id"))), area.get("area_id"))
        self.cmbArea.blockSignals(False)

    def _on_area_changed(self) -> None:
        self._populate_customer_combo(area_id=self.cmbArea.currentData())

    def _populate_customer_combo(self, area_id: Optional[int] = None) -> None:
        """Confirmed real functions: get_active_customers() (no args) vs.
        get_active_customers_by_area(area_id) when an area is selected."""
        try:
            customers = (
                get_active_customers_by_area(area_id) if area_id is not None else get_active_customers()
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load active customers")
            customers = []

        self._customer_names = {c["customer_id"]: c["customer_name"] for c in customers}

        current_id = self.cmbCustomer.currentData()
        self.cmbCustomer.blockSignals(True)
        self.cmbCustomer.clear()
        self.cmbCustomer.addItem("Select Customer...", None)
        for customer_id, customer_name in self._customer_names.items():
            self.cmbCustomer.addItem(customer_name, customer_id)
        restore_index = self.cmbCustomer.findData(current_id)
        self.cmbCustomer.setCurrentIndex(restore_index if restore_index >= 0 else 0)
        self.cmbCustomer.blockSignals(False)
        self._refresh_invoice_options()

    def _refresh_invoice_options(self) -> None:
        """
        Repopulates cmbInvoiceNumber with posted invoices for the selected customer,
        filtered by the From/To date range (client-side — search_sale_invoices has no
        confirmed date-range parameter, so this filters the returned page in Python using
        each invoice's `invoice_date_ad` attribute; ASSUMED attribute name — verify against
        the real SaleInvoiceDTO, see SALE_RETURN_WIRING_NOTES.md).
        """
        customer_id = self.cmbCustomer.currentData()
        current_text = self.cmbInvoiceNumber.currentText()
        self.cmbInvoiceNumber.blockSignals(True)
        self.cmbInvoiceNumber.clear()

        if customer_id is None:
            self.cmbInvoiceNumber.blockSignals(False)
            return

        try:
            results, _total = self._sale_engine.search_sale_invoices(
                customer_id=customer_id, status=POSTED_INVOICE_STATUS, page_size=200
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load invoices for customer %s", customer_id)
            self.cmbInvoiceNumber.blockSignals(False)
            return

        from_bs = self.dtFromDate.get_bs_date_string()
        to_bs = self.dtToDate.get_bs_date_string()
        from_date = bs_to_ad(from_bs) if from_bs else None
        to_date = bs_to_ad(to_bs) if to_bs else None

        for invoice in results:
            invoice_date = getattr(invoice, "invoice_date_ad", None)
            if from_date and invoice_date and invoice_date < from_date:
                continue
            if to_date and invoice_date and invoice_date > to_date:
                continue
            invoice_number = getattr(invoice, "invoice_number", str(invoice.sale_invoice_id))
            self.cmbInvoiceNumber.addItem(invoice_number, invoice.sale_invoice_id)

        self.cmbInvoiceNumber.setCurrentText(current_text)
        self.cmbInvoiceNumber.blockSignals(False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.lblTitle = QLabel("View Sale Return" if self._view_mode else "New Sale Return")
        f = self.lblTitle.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        self.lblTitle.setFont(f)
        header.addWidget(self.lblTitle)
        header.addStretch(1)
        self.lblStatus = QLabel(self._status)
        header.addWidget(self.lblStatus)
        root.addLayout(header)

        grpInvoice = QGroupBox("Customer & Invoice")
        invLayout = QVBoxLayout(grpInvoice)

        custRow = QHBoxLayout()
        custRow.addWidget(self._field_label("Area:"))
        self.cmbArea = QComboBox()
        self.cmbArea.setFixedWidth(140)
        custRow.addWidget(self.cmbArea)
        custRow.addSpacing(20)
        custRow.addWidget(self._field_label("Customer:"))
        self.cmbCustomer = QComboBox()
        self.cmbCustomer.setMinimumWidth(280)
        self.cmbCustomer.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._make_searchable(self.cmbCustomer)
        custRow.addWidget(self.cmbCustomer)
        custRow.addSpacing(20)
        custRow.addWidget(QLabel("From:"))
        self.dtFromDate = BSCalendarDatePicker(self)
        self.dtFromDate.setMinimumWidth(130)
        custRow.addWidget(self.dtFromDate)
        custRow.addSpacing(12)
        custRow.addWidget(QLabel("To:"))
        self.dtToDate = BSCalendarDatePicker(self)
        self.dtToDate.setMinimumWidth(130)
        custRow.addWidget(self.dtToDate)
        custRow.addStretch(1)
        invLayout.addLayout(custRow)

        invoiceRow = QHBoxLayout()
        invoiceRow.addWidget(self._field_label("Invoice No.:"))
        self.cmbInvoiceNumber = QComboBox()
        self.cmbInvoiceNumber.setFixedWidth(180)
        self._make_searchable(self.cmbInvoiceNumber)
        invoiceRow.addWidget(self.cmbInvoiceNumber)
        self.btnLoadInvoice = QPushButton("Load Items")
        invoiceRow.addWidget(self.btnLoadInvoice)
        invoiceRow.addSpacing(20)
        invoiceRow.addWidget(self._field_label("Return Date:"))
        self.dtReturnDate = BSCalendarDatePicker(self)
        self.dtReturnDate.set_bs_date_string(ad_to_bs(date.today()))
        invoiceRow.addWidget(self.dtReturnDate)
        invoiceRow.addSpacing(20)
        invoiceRow.addWidget(self._field_label("Refund Mode:"))
        self.cmbRefundMode = QComboBox()
        self.cmbRefundMode.setFixedWidth(160)
        self.cmbRefundMode.addItems(REFUND_MODES)
        invoiceRow.addWidget(self.cmbRefundMode)
        invoiceRow.addStretch(1)
        invLayout.addLayout(invoiceRow)

        root.addWidget(grpInvoice)

        self.tblReturnItems = QTableWidget(0, 8)
        self.tblReturnItems.setHorizontalHeaderLabels(
            [
                "Item",
                "Batch",
                "Sold Qty",
                "Rate",
                "Discount %",
                "Remaining Returnable",
                "Return Qty",
                "Est. Line Total",
            ]
        )
        self.tblReturnItems.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tblReturnItems.verticalHeader().setVisible(False)
        self.tblReturnItems.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblReturnItems.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.tblReturnItems, stretch=1)

        totalRow = QHBoxLayout()
        totalRow.addStretch(1)
        totalRow.addWidget(QLabel("Estimated Grand Total:"))
        self.lblGrandTotal = QLabel("0.00")
        f2 = self.lblGrandTotal.font()
        f2.setBold(True)
        f2.setPointSize(f2.pointSize() + 2)
        self.lblGrandTotal.setFont(f2)
        totalRow.addWidget(self.lblGrandTotal)
        root.addLayout(totalRow)

        actions = QHBoxLayout()
        actions.addWidget(QLabel("Return Reason: *"))
        self.txtReturnReason = QLineEdit()
        self.txtReturnReason.setPlaceholderText("Mandatory")
        self.txtReturnReason.setMaximumWidth(500)
        actions.addWidget(self.txtReturnReason)
        actions.addStretch(1)
        self.btnSaveDraft = QPushButton("Save Draft")
        self.btnPost = QPushButton("Post Return")
        self.btnPost.setObjectName("primaryButton")
        self.btnCancelReturn = QPushButton("Cancel Return")
        self.btnCancelReturn.setObjectName("dangerButton")
        self.btnClose = QPushButton("Close")
        actions.addWidget(self.btnSaveDraft)
        actions.addWidget(self.btnPost)
        actions.addWidget(self.btnCancelReturn)
        actions.addWidget(self.btnClose)
        root.addLayout(actions)

        self.btnCancelReturn.setVisible(False)
        if self._view_mode:
            self.btnSaveDraft.setVisible(False)
            self.btnPost.setVisible(False)

    def _wire_events(self) -> None:
        self.cmbArea.currentIndexChanged.connect(self._on_area_changed)
        self.cmbCustomer.currentIndexChanged.connect(self._refresh_invoice_options)
        self.dtFromDate.date_changed.connect(self._refresh_invoice_options)
        self.dtToDate.date_changed.connect(self._refresh_invoice_options)
        self.btnLoadInvoice.clicked.connect(self._on_load_invoice)
        self.btnSaveDraft.clicked.connect(lambda: self._on_create(status="Draft"))
        self.btnPost.clicked.connect(lambda: self._on_create(status="Posted"))
        self.btnCancelReturn.clicked.connect(self._on_cancel_return)
        self.btnClose.clicked.connect(self.close_requested.emit)

    # ------------------------------------------------------------------
    # Invoice lookup (create mode only)
    # ------------------------------------------------------------------
    def _on_load_invoice(self) -> None:
        invoice_number = self.cmbInvoiceNumber.currentText().strip()
        if not invoice_number:
            msg.show_error("Please select or enter an invoice number to load.")
            return
        try:
            results, _total = self._sale_engine.search_sale_invoices(search_text=invoice_number)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to search invoice %s", invoice_number)
            msg.show_error("Could not look up that invoice. Please try again.")
            return

        if not results:
            msg.show_error(f"No invoice found matching '{invoice_number}'.")
            return

        invoice = results[0]
        if getattr(invoice, "status", None) != POSTED_INVOICE_STATUS:
            msg.show_error("Only a posted invoice can be returned against.")
            return

        self._sale_invoice_id = invoice.sale_invoice_id
        self._customer_id = invoice.customer_id
        customer_index = self.cmbCustomer.findData(self._customer_id)
        if customer_index >= 0:
            self.cmbCustomer.blockSignals(True)
            self.cmbCustomer.setCurrentIndex(customer_index)
            self.cmbCustomer.blockSignals(False)

        try:
            rows = self._sale_return_engine.get_returnable_lines(self._sale_invoice_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load returnable lines for invoice %s", self._sale_invoice_id)
            msg.show_error("Could not load items for this invoice.")
            return

        self._lines = [
            _ReturnableLine(
                sale_invoice_item_id=row["sale_invoice_item_id"],
                item_name=row.get("item_name", ""),
                batch_no=row.get("batch_no", ""),
                original_qty=float(row.get("original_qty", row.get("qty", 0))),
                remaining_returnable_qty=float(row["remaining_returnable_qty"]),
                rate=float(row.get("rate", 0)),
                discount_percent=float(row.get("discount_percent", 0)),
                cc_percent=float(row.get("cc_percent", 0)),
            )
            for row in rows
            if float(row["remaining_returnable_qty"]) > 0
        ]
        self._populate_table()

    def _populate_table(self) -> None:
        self.tblReturnItems.setRowCount(0)
        for line in self._lines:
            row = self.tblReturnItems.rowCount()
            self.tblReturnItems.insertRow(row)
            self.tblReturnItems.setItem(row, 0, QTableWidgetItem(line.item_name))
            self.tblReturnItems.setItem(row, 1, QTableWidgetItem(line.batch_no))
            self.tblReturnItems.setItem(row, 2, QTableWidgetItem(f"{line.original_qty:g}"))
            self.tblReturnItems.setItem(row, 3, QTableWidgetItem(f"{line.rate:.2f}"))
            self.tblReturnItems.setItem(row, 4, QTableWidgetItem(f"{line.discount_percent:.2f}"))
            self.tblReturnItems.setItem(row, 5, QTableWidgetItem(f"{line.remaining_returnable_qty:g}"))

            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setMinimum(0.0)
            spin.setMaximum(line.remaining_returnable_qty)
            spin.setValue(0.0)
            spin.valueChanged.connect(self._recalculate_totals)
            self.tblReturnItems.setCellWidget(row, RETURN_QTY_COLUMN, spin)

            self.tblReturnItems.setItem(row, 7, QTableWidgetItem("0.00"))
        self._recalculate_totals()

    def _recalculate_totals(self) -> None:
        grand_total = 0.0
        for row, line in enumerate(self._lines):
            spin = self.tblReturnItems.cellWidget(row, RETURN_QTY_COLUMN)
            return_qty = spin.value() if isinstance(spin, QDoubleSpinBox) else 0.0
            line_total = line.estimated_line_total(return_qty)
            self.tblReturnItems.setItem(row, 7, QTableWidgetItem(f"{line_total:.2f}"))
            grand_total += line_total
        self.lblGrandTotal.setText(f"{grand_total:.2f}")

    # ------------------------------------------------------------------
    # View mode (existing return, read-only)
    # ------------------------------------------------------------------
    def _load_existing_return(self, sale_return_id: int) -> None:
        try:
            dto = self._sale_return_engine.get_by_id(sale_return_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load sale return %s", sale_return_id)
            msg.show_error("Could not load this sale return.")
            self.close_requested.emit()
            return

        if dto is None:
            msg.show_error("This sale return no longer exists.")
            self.close_requested.emit()
            return

        self._status = dto.status
        self.lblTitle.setText(f"Sale Return #{dto.sale_return_id}")
        self.lblStatus.setText(dto.status)
        customer_index = self.cmbCustomer.findData(dto.customer_id)
        if customer_index >= 0:
            self.cmbCustomer.setCurrentIndex(customer_index)
        self.cmbInvoiceNumber.clear()
        self.cmbInvoiceNumber.addItem(str(dto.sale_invoice_id), dto.sale_invoice_id)
        self.cmbRefundMode.setCurrentText(dto.refund_mode)
        self.txtReturnReason.setText(getattr(dto, "return_reason", "") or "")
        self.lblGrandTotal.setText(f"{float(dto.grand_total):.2f}")

        items = getattr(dto, "items", []) or []
        self._lines = [
            _ReturnableLine(
                sale_invoice_item_id=item.sale_invoice_item_id,
                item_name=getattr(item, "item_name", ""),
                batch_no=getattr(item, "batch_no", ""),
                original_qty=float(getattr(item, "return_qty", 0)),
                remaining_returnable_qty=float(getattr(item, "return_qty", 0)),
                rate=float(getattr(item, "rate", 0)),
                discount_percent=float(getattr(item, "discount_percent", 0)),
                cc_percent=float(getattr(item, "cc_percent", 0)),
            )
            for item in items
        ]
        self._populate_table()
        for row, item in enumerate(items):
            spin = self.tblReturnItems.cellWidget(row, RETURN_QTY_COLUMN)
            if isinstance(spin, QDoubleSpinBox):
                spin.setValue(float(getattr(item, "return_qty", 0)))
        self._recalculate_totals()

        self._set_editable(False)
        self.btnCancelReturn.setVisible(self._status == "Posted")

    def _set_editable(self, editable: bool) -> None:
        self.cmbArea.setEnabled(editable)
        self.cmbCustomer.setEnabled(editable)
        self.dtFromDate.setEnabled(editable)
        self.dtToDate.setEnabled(editable)
        self.cmbInvoiceNumber.setEnabled(editable)
        self.btnLoadInvoice.setEnabled(editable)
        self.dtReturnDate.setEnabled(editable)
        self.cmbRefundMode.setEnabled(editable)
        self.txtReturnReason.setReadOnly(not editable)
        for row in range(self.tblReturnItems.rowCount()):
            spin = self.tblReturnItems.cellWidget(row, RETURN_QTY_COLUMN)
            if isinstance(spin, QDoubleSpinBox):
                spin.setEnabled(editable)

    # ------------------------------------------------------------------
    # Create (Draft or Posted)
    # ------------------------------------------------------------------
    def _on_create(self, status: str) -> None:
        if self._sale_invoice_id is None:
            msg.show_error("Please load a posted invoice first.")
            return

        return_reason = self.txtReturnReason.text().strip()
        if not return_reason:
            msg.show_error("Return reason is mandatory.")
            return

        return_lines = []
        for row, line in enumerate(self._lines):
            spin = self.tblReturnItems.cellWidget(row, RETURN_QTY_COLUMN)
            return_qty = spin.value() if isinstance(spin, QDoubleSpinBox) else 0.0
            if return_qty <= 0:
                continue
            return_lines.append(
                {"sale_invoice_item_id": line.sale_invoice_item_id, "return_qty": return_qty}
            )

        if not return_lines:
            msg.show_error("Please enter a return quantity for at least one item.")
            return

        try:
            self._sale_return_engine.create_return(
                sale_invoice_id=self._sale_invoice_id,
                customer_id=self._customer_id,
                return_date_ad=bs_to_ad(self.dtReturnDate.get_bs_date_string()),
                return_reason=return_reason,
                refund_mode=self.cmbRefundMode.currentText(),
                return_lines=return_lines,
                created_by=self._current_user_id,
                status=status,
            )
        except ValidationError as exc:
            msg.show_error(str(exc))
            return
        except RecordNotFoundError as exc:
            msg.show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create sale return")
            msg.show_error("An unexpected error occurred while saving the sale return.")
            return

        msg.show_info("Sale return posted successfully." if status == "Posted" else "Sale return saved as draft.")
        self.saved.emit()

    def _on_cancel_return(self) -> None:
        if self._sale_return_id is None:
            return
        dialog = CancellationReasonDialog(self)
        reason = dialog.get_reason()
        if not reason:
            return
        try:
            self._sale_return_engine.cancel_return(self._sale_return_id, reason, self._current_user_id)
            msg.show_info("Sale return cancelled and stock reversed.")
        except ValidationError as exc:
            msg.show_error(str(exc))
            return
        except RecordNotFoundError as exc:
            msg.show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to cancel sale return %s", self._sale_return_id)
            msg.show_error("An unexpected error occurred while cancelling the sale return.")
            return

        self.saved.emit()