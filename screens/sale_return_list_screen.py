"""
screens/sale_return_list_screen.py

Sale Return List Screen — search, browse, and act on Sale Return records.

Rewritten against CONFIRMED real signatures:
    - engines.sale_return_engine.SaleReturnEngine.search(filters: SaleReturnSearchFilters) -> list[SaleReturnDTO]
    - engines.sale_return_engine.SaleReturnEngine.delete_draft(sale_return_id, deleted_by) -> None
          [raises RecordNotFoundError, ValidationError]
    - engines.sale_return_engine.SaleReturnEngine.cancel_return(sale_return_id, cancellation_reason, updated_by) -> SaleReturnDTO
    - engines.customer_engine.get_active_customers() -> list[dict]
    - engines.exceptions: ValidationError, RecordNotFoundError
    - utils.message: show_error, show_info, confirm

STILL UNCONFIRMED (see SALE_RETURN_WIRING_NOTES.md Step 2): the exact field names of the
`SaleReturnSearchFilters` dataclass in models/sale_return_model.py. Used here by convention
(search_text, customer_id, status, date_from_ad, date_to_ad, include_deleted, page, page_size)
matching the pattern used by ReceiptSearchFilters — confirm before merging.

There is NO edit/update method for an existing Draft in the real engine — so this screen has
no "Edit" action. Only: New, View (read-only), Cancel (Posted only), Delete Draft (Draft only).

Naming convention: btnX / txtX / lblX / tblX / cmbX per project standard.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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

from engines.customer_engine import get_active_customers
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_return_engine import SaleReturnEngine
from models.sale_return_model import SaleReturnSearchFilters
from screens.cancellation_reason_dialog import CancellationReasonDialog
from utils import message as msg

logger = logging.getLogger(__name__)

STATUS_FILTER_OPTIONS = ["All", "Draft", "Posted", "Cancelled"]

COL_ID = 0
COL_INVOICE = 1
COL_CUSTOMER = 2
COL_RETURN_DATE = 3
COL_REFUND_MODE = 4
COL_STATUS = 5
COL_GRAND_TOTAL = 6


class SaleReturnListScreen(QWidget):
    """
    Sale Return list/search screen.

    Embedded pattern (matches ReceiptListScreen):
        close_requested    -> go back to Dashboard home
        form_requested(obj) -> open the form to CREATE a new return (obj is always None here)
        view_requested(int) -> open the form read-only for a specific sale_return_id
    """

    close_requested = Signal()
    form_requested = Signal(object)
    view_requested = Signal(int)

    def __init__(
        self,
        sale_return_engine: SaleReturnEngine,
        current_user_id: int,
        embedded: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sale_return_engine = sale_return_engine
        self._current_user_id = current_user_id
        self._embedded = embedded
        self._customers: list[dict] = []

        self._build_ui()
        self._wire_events()
        self._load_customers()
        self._refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        lblTitle = QLabel("Sale Returns")
        f = lblTitle.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        lblTitle.setFont(f)
        header.addWidget(lblTitle)
        header.addStretch(1)
        self.btnNewReturn = QPushButton("New Return")
        self.btnNewReturn.setObjectName("primaryButton")
        header.addWidget(self.btnNewReturn)
        if self._embedded:
            self.btnClose = QPushButton("Back")
            header.addWidget(self.btnClose)
        root.addLayout(header)

        filters = QHBoxLayout()
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("Search by invoice number or return ID...")
        filters.addWidget(self.txtSearch, stretch=2)

        self.cmbCustomer = QComboBox()
        self.cmbCustomer.addItem("All Customers", None)
        filters.addWidget(self.cmbCustomer, stretch=1)

        self.cmbStatus = QComboBox()
        self.cmbStatus.addItems(STATUS_FILTER_OPTIONS)
        filters.addWidget(self.cmbStatus, stretch=1)

        self.btnSearch = QPushButton("Search")
        filters.addWidget(self.btnSearch)
        self.btnRefresh = QPushButton("Refresh")
        filters.addWidget(self.btnRefresh)
        root.addLayout(filters)

        self.tblReturns = QTableWidget(0, 7)
        self.tblReturns.setHorizontalHeaderLabels(
            ["ID", "Invoice ID", "Customer", "Return Date", "Refund Mode", "Status", "Grand Total"]
        )
        self.tblReturns.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tblReturns.verticalHeader().setVisible(False)
        self.tblReturns.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblReturns.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblReturns.setSelectionMode(QAbstractItemView.SingleSelection)
        root.addWidget(self.tblReturns, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btnView = QPushButton("View")
        self.btnCancelReturn = QPushButton("Cancel Return")
        self.btnCancelReturn.setObjectName("dangerButton")
        self.btnDelete = QPushButton("Delete Draft")
        self.btnDelete.setObjectName("dangerButton")
        actions.addWidget(self.btnView)
        actions.addWidget(self.btnCancelReturn)
        actions.addWidget(self.btnDelete)
        root.addLayout(actions)

    def _wire_events(self) -> None:
        self.btnNewReturn.clicked.connect(lambda: self.form_requested.emit(None))
        if self._embedded:
            self.btnClose.clicked.connect(self.close_requested.emit)
        self.btnSearch.clicked.connect(self._refresh)
        self.btnRefresh.clicked.connect(self._refresh)
        self.txtSearch.returnPressed.connect(self._refresh)
        self.btnView.clicked.connect(self._on_view)
        self.btnCancelReturn.clicked.connect(self._on_cancel)
        self.btnDelete.clicked.connect(self._on_delete)
        self.tblReturns.itemDoubleClicked.connect(lambda _item: self._on_view())

    # ------------------------------------------------------------------
    def _load_customers(self) -> None:
        try:
            self._customers = get_active_customers()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load active customers")
            self._customers = []

        for customer in self._customers:
            self.cmbCustomer.addItem(customer["customer_name"], customer["customer_id"])

    def _refresh(self) -> None:
        status = self.cmbStatus.currentText()
        filters = SaleReturnSearchFilters(
            search_text=self.txtSearch.text().strip() or None,
            customer_id=self.cmbCustomer.currentData(),
            status=None if status == "All" else status,
            date_from_ad=None,
            date_to_ad=None,
            include_deleted=False,
            page=1,
            page_size=200,
        )
        try:
            results = self._sale_return_engine.search(filters)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to search sale returns")
            msg.show_error("Could not load sale returns.")
            return

        self.tblReturns.setRowCount(0)
        for dto in results:
            row = self.tblReturns.rowCount()
            self.tblReturns.insertRow(row)
            self.tblReturns.setItem(row, COL_ID, QTableWidgetItem(str(dto.sale_return_id)))
            self.tblReturns.setItem(row, COL_INVOICE, QTableWidgetItem(str(dto.sale_invoice_id)))
            self.tblReturns.setItem(
                row, COL_CUSTOMER, QTableWidgetItem(getattr(dto, "customer_name", str(dto.customer_id)))
            )
            self.tblReturns.setItem(
                row, COL_RETURN_DATE, QTableWidgetItem(str(getattr(dto, "return_date_ad", "")))
            )
            self.tblReturns.setItem(row, COL_REFUND_MODE, QTableWidgetItem(dto.refund_mode))
            self.tblReturns.setItem(row, COL_STATUS, QTableWidgetItem(dto.status))
            self.tblReturns.setItem(row, COL_GRAND_TOTAL, QTableWidgetItem(f"{float(dto.grand_total):.2f}"))

    def _selected_return_id(self) -> Optional[int]:
        row = self.tblReturns.currentRow()
        if row < 0:
            return None
        item = self.tblReturns.item(row, COL_ID)
        return int(item.text()) if item else None

    def _selected_status(self) -> Optional[str]:
        row = self.tblReturns.currentRow()
        if row < 0:
            return None
        item = self.tblReturns.item(row, COL_STATUS)
        return item.text() if item else None

    # ------------------------------------------------------------------
    def _on_view(self) -> None:
        sale_return_id = self._selected_return_id()
        if sale_return_id is None:
            msg.show_error("Please select a sale return first.")
            return
        self.view_requested.emit(sale_return_id)

    def _on_cancel(self) -> None:
        sale_return_id = self._selected_return_id()
        if sale_return_id is None:
            msg.show_error("Please select a sale return first.")
            return
        if self._selected_status() != "Posted":
            msg.show_error("Only a Posted sale return can be cancelled.")
            return
        dialog = CancellationReasonDialog(self)
        reason = dialog.get_reason()
        if not reason:
            return
        try:
            self._sale_return_engine.cancel_return(sale_return_id, reason, self._current_user_id)
            msg.show_info("Sale return cancelled and stock reversed.")
        except ValidationError as exc:
            msg.show_error(str(exc))
            return
        except RecordNotFoundError as exc:
            msg.show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to cancel sale return %s", sale_return_id)
            msg.show_error("An unexpected error occurred while cancelling the sale return.")
            return

        self._refresh()

    def _on_delete(self) -> None:
        sale_return_id = self._selected_return_id()
        if sale_return_id is None:
            msg.show_error("Please select a sale return first.")
            return
        if self._selected_status() != "Draft":
            msg.show_error("Only Draft sale returns can be deleted.")
            return
        if not msg.confirm("Delete this draft sale return? This cannot be undone."):
            return
        try:
            self._sale_return_engine.delete_draft(sale_return_id, self._current_user_id)
            msg.show_info("Draft sale return deleted.")
        except ValidationError as exc:
            msg.show_error(str(exc))
            return
        except RecordNotFoundError as exc:
            msg.show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to delete sale return %s", sale_return_id)
            msg.show_error("An unexpected error occurred while deleting the sale return.")
            return

        self._refresh()