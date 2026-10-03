"""Search and manage Purchase Returns."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.purchase_return_engine import PurchaseReturnEngine
from models.purchase_return_model import PurchaseReturnSearchFilters
from screens.cancellation_reason_dialog import CancellationReasonDialog
from utils import message as msg

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ("All", "Draft", "Posted", "Cancelled")
SETTLEMENT_OPTIONS = ("All", "Adjust Against Payable", "Supplier Advance", "Cash Refund")
PAGE_SIZE = 100


class PurchaseReturnViewDialog(QDialog):
    """Read-only header and item detail for one Purchase Return."""

    def __init__(self, purchase_return, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Purchase Return {purchase_return.return_number}")
        self.resize(900, 560)

        root = QVBoxLayout(self)
        header = QFormLayout()
        for label, value in (
            ("Return No.", purchase_return.return_number),
            ("Supplier", purchase_return.supplier_name or str(purchase_return.supplier_id)),
            ("Invoice Ref.", purchase_return.internal_ref_number or str(purchase_return.purchase_invoice_id)),
            ("Return Date (BS)", purchase_return.return_date_bs),
            ("Status", purchase_return.status),
            ("Settlement", purchase_return.settlement_mode),
            ("Reason", purchase_return.return_reason),
        ):
            field = QLabel(str(value or ""))
            field.setWordWrap(True)
            header.addRow(label, field)
        if purchase_return.cancellation_reason:
            reason = QLabel(purchase_return.cancellation_reason)
            reason.setWordWrap(True)
            header.addRow("Cancellation Reason", reason)
        root.addLayout(header)

        items = QTableWidget(0, 8)
        items.setHorizontalHeaderLabels(
            ["Item ID", "Batch", "Expiry", "Return Qty", "Free Qty", "Rate", "Discount", "Amount"]
        )
        items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        items.verticalHeader().setVisible(False)
        items.setEditTriggers(QAbstractItemView.NoEditTriggers)
        items.setSelectionBehavior(QAbstractItemView.SelectRows)
        for line in purchase_return.lines or []:
            row = items.rowCount()
            items.insertRow(row)
            values = (
                line.item_id,
                line.batch_no,
                f"{line.expiry_month:02d}/{line.expiry_year}",
                f"{line.return_qty:g}",
                f"{line.return_free_qty:g}",
                f"{line.rate:.2f}",
                f"{line.discount_amount:.2f}",
                f"{line.amount:.2f}",
            )
            for column, value in enumerate(values):
                items.setItem(row, column, QTableWidgetItem(str(value)))
        root.addWidget(items, 1)
        root.addWidget(QLabel(
            f"Total Qty: {purchase_return.total_qty:g}    "
            f"Free Qty: {purchase_return.total_free_qty:g}    "
            f"Grand Total: {purchase_return.grand_total:.2f}"
        ))
        if purchase_return.remarks:
            remarks = QTextEdit()
            remarks.setReadOnly(True)
            remarks.setMaximumHeight(70)
            remarks.setPlainText(purchase_return.remarks)
            root.addWidget(QLabel("Remarks"))
            root.addWidget(remarks)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


class PurchaseReturnListScreen(QWidget):
    """Filter, view, cancel posted, and delete draft Purchase Returns."""

    close_requested = Signal()
    form_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: PurchaseReturnEngine,
        supplier_engine,
        current_user_id: int,
        embedded: bool = True,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._supplier_engine = supplier_engine
        self._current_user_id = current_user_id
        self._embedded = embedded
        self._page = 1
        self._rows = []
        self._build_ui()
        self._load_suppliers()
        self._connect_signals()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Purchase Returns")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        self.btnNewReturn = QPushButton("New Return")
        self.btnNewReturn.setObjectName("primaryButton")
        header.addWidget(self.btnNewReturn)
        if self._embedded:
            self.btnBack = QPushButton("Back")
            header.addWidget(self.btnBack)
        root.addLayout(header)

        filters = QHBoxLayout()
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("Return no., supplier, or invoice reference")
        filters.addWidget(self.txtSearch, 2)
        self.cmbSupplier = QComboBox()
        self.cmbSupplier.addItem("All Suppliers", None)
        filters.addWidget(self.cmbSupplier, 1)
        self.cmbStatus = QComboBox()
        self.cmbStatus.addItems(STATUS_OPTIONS)
        filters.addWidget(self.cmbStatus)
        self.cmbSettlement = QComboBox()
        self.cmbSettlement.addItems(SETTLEMENT_OPTIONS)
        filters.addWidget(self.cmbSettlement)
        self.dateFrom = QDateEdit()
        self.dateFrom.setCalendarPopup(True)
        self.dateFrom.setDisplayFormat("dd MMM yyyy")
        self.dateFrom.setDate(self.dateFrom.date().addMonths(-1))
        filters.addWidget(self.dateFrom)
        self.dateTo = QDateEdit()
        self.dateTo.setCalendarPopup(True)
        self.dateTo.setDisplayFormat("dd MMM yyyy")
        self.dateTo.setDate(QDate.currentDate())
        filters.addWidget(self.dateTo)
        self.btnFilter = QPushButton("Filter")
        self.btnRefresh = QPushButton("Refresh")
        filters.addWidget(self.btnFilter)
        filters.addWidget(self.btnRefresh)
        root.addLayout(filters)

        self.tblReturns = QTableWidget(0, 7)
        self.tblReturns.setHorizontalHeaderLabels(
            ["Return No.", "Invoice Ref.", "Supplier", "Date (BS)", "Settlement", "Status", "Grand Total"]
        )
        self.tblReturns.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tblReturns.verticalHeader().setVisible(False)
        self.tblReturns.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblReturns.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblReturns.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.tblReturns, 1)

        actions = QHBoxLayout()
        self.lblPage = QLabel("Page 1")
        actions.addWidget(self.lblPage)
        self.btnPrevious = QPushButton("Prev")
        self.btnNext = QPushButton("Next")
        actions.addWidget(self.btnPrevious)
        actions.addWidget(self.btnNext)
        actions.addStretch(1)
        self.btnView = QPushButton("View")
        self.btnCancel = QPushButton("Cancel Posted")
        self.btnDelete = QPushButton("Delete Draft")
        actions.addWidget(self.btnView)
        actions.addWidget(self.btnCancel)
        actions.addWidget(self.btnDelete)
        root.addLayout(actions)

    def _load_suppliers(self) -> None:
        try:
            suppliers = self._supplier_engine.get_active_suppliers()
        except Exception:
            logger.exception("Failed to load suppliers for Purchase Return filters.")
            msg.show_error("Could not load the supplier filter.")
            return
        for supplier in suppliers:
            self.cmbSupplier.addItem(supplier.supplier_name, supplier.supplier_id)

    def _connect_signals(self) -> None:
        self.btnFilter.clicked.connect(self._apply_filters)
        self.btnRefresh.clicked.connect(self.refresh)
        self.txtSearch.returnPressed.connect(self._apply_filters)
        self.cmbStatus.currentIndexChanged.connect(self._apply_filters)
        self.cmbSupplier.currentIndexChanged.connect(self._apply_filters)
        self.cmbSettlement.currentIndexChanged.connect(self._apply_filters)
        self.btnPrevious.clicked.connect(self._previous_page)
        self.btnNext.clicked.connect(self._next_page)
        self.btnView.clicked.connect(self._view_selected)
        self.btnCancel.clicked.connect(self._cancel_selected)
        self.btnDelete.clicked.connect(self._delete_selected)
        self.tblReturns.itemDoubleClicked.connect(lambda _item: self._view_selected())
        self.tblReturns.itemSelectionChanged.connect(self._update_actions)
        self.btnNewReturn.clicked.connect(self.form_requested.emit)
        if self._embedded:
            self.btnBack.clicked.connect(self.close_requested.emit)

    def _apply_filters(self) -> None:
        self._page = 1
        self.refresh()

    def _filters(self) -> PurchaseReturnSearchFilters:
        status = self.cmbStatus.currentText()
        settlement = self.cmbSettlement.currentText()
        return PurchaseReturnSearchFilters(
            search_text=self.txtSearch.text().strip() or None,
            supplier_id=self.cmbSupplier.currentData(),
            status=None if status == "All" else status,
            settlement_mode=None if settlement == "All" else settlement,
            date_from_ad=date(self.dateFrom.date().year(), self.dateFrom.date().month(), self.dateFrom.date().day()),
            date_to_ad=date(self.dateTo.date().year(), self.dateTo.date().month(), self.dateTo.date().day()),
            include_deleted=False,
            page=self._page,
            page_size=PAGE_SIZE,
        )

    def refresh(self) -> None:
        try:
            self._rows = self._engine.search(self._filters())
        except Exception:
            logger.exception("Failed to search Purchase Returns.")
            msg.show_error("Could not load Purchase Returns.")
            return

        self.tblReturns.setRowCount(0)
        for dto in self._rows:
            row = self.tblReturns.rowCount()
            self.tblReturns.insertRow(row)
            values = (
                dto.return_number,
                dto.internal_ref_number or str(dto.purchase_invoice_id),
                dto.supplier_name or str(dto.supplier_id),
                dto.return_date_bs,
                dto.settlement_mode,
                dto.status,
                f"{dto.grand_total:.2f}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, dto.purchase_return_id)
                self.tblReturns.setItem(row, column, item)
        self.lblPage.setText(f"Page {self._page}")
        self.btnPrevious.setEnabled(self._page > 1)
        self.btnNext.setEnabled(len(self._rows) == PAGE_SIZE)
        self._update_actions()

    def _selected_return(self):
        row = self.tblReturns.currentRow()
        if row < 0:
            return None
        return next(
            (dto for dto in self._rows if dto.purchase_return_id ==
             self.tblReturns.item(row, 0).data(Qt.ItemDataRole.UserRole)),
            None,
        )

    def _update_actions(self) -> None:
        dto = self._selected_return()
        self.btnView.setEnabled(dto is not None)
        self.btnCancel.setEnabled(dto is not None and dto.status == "Posted")
        self.btnDelete.setEnabled(dto is not None and dto.status == "Draft")

    def _previous_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self) -> None:
        if len(self._rows) == PAGE_SIZE:
            self._page += 1
            self.refresh()

    def _view_selected(self) -> None:
        selected = self._selected_return()
        if selected is None:
            msg.show_error("Select a Purchase Return to view.")
            return
        try:
            details = self._engine.get_by_id(selected.purchase_return_id)
            if details is None:
                raise RecordNotFoundError("Purchase Return was not found.")
            details.supplier_name = selected.supplier_name
            details.internal_ref_number = selected.internal_ref_number
            PurchaseReturnViewDialog(details, self).exec()
        except RecordNotFoundError as exc:
            msg.show_error(str(exc))
            self.refresh()
        except Exception:
            logger.exception("Failed to load Purchase Return %s.", selected.purchase_return_id)
            msg.show_error("Could not load Purchase Return details.")

    def _cancel_selected(self) -> None:
        selected = self._selected_return()
        if selected is None:
            msg.show_error("Select a Purchase Return to cancel.")
            return
        if selected.status != "Posted":
            msg.show_error("Only a Posted Purchase Return can be cancelled.")
            return
        dialog = CancellationReasonDialog(self)
        if not dialog.exec():
            return
        reason = dialog.get_reason()
        if not reason:
            return
        try:
            self._engine.cancel_return(selected.purchase_return_id, reason, self._current_user_id)
        except (ValidationError, RecordNotFoundError) as exc:
            msg.show_error(str(exc))
            return
        except Exception:
            logger.exception("Failed to cancel Purchase Return %s.", selected.purchase_return_id)
            msg.show_error("An unexpected error occurred while cancelling the Purchase Return.")
            return
        msg.show_info("Purchase Return cancelled and stock reversal posted.")
        self.refresh()

    def _delete_selected(self) -> None:
        selected = self._selected_return()
        if selected is None:
            msg.show_error("Select a Purchase Return to delete.")
            return
        if selected.status != "Draft":
            msg.show_error("Only a Draft Purchase Return can be deleted.")
            return
        if not msg.confirm("Delete this Draft Purchase Return? This cannot be undone."):
            return
        try:
            self._engine.delete_draft(selected.purchase_return_id, self._current_user_id)
        except (ValidationError, RecordNotFoundError) as exc:
            msg.show_error(str(exc))
            return
        except Exception:
            logger.exception("Failed to delete Purchase Return %s.", selected.purchase_return_id)
            msg.show_error("An unexpected error occurred while deleting the Purchase Return.")
            return
        msg.show_info("Draft Purchase Return deleted.")
        self.refresh()
