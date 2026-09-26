"""
screens/payment_list_screen.py

Payment List Screen - Medical ERP V2

Mirrors screens/receipt_list_screen.py exactly, applied to the supplier
side (and ONLY this responsibility -- "No SQL. No business logic."):
    - List/search/filter Payments (Supplier/Payment No./Reference text,
      Payment Mode, Status, Date range).
    - View (read-only inline form), Edit (Posted only), Cancel (Posted
      only, via the shared CancellationReasonDialog), Delete (Draft
      only), View Audit Log.

EMBEDDING CONVENTION: identical to ReceiptListScreen. Plain QWidget,
constructed with embedded=True, pushed via _navigate_to(). Emits:
    close_requested          -- own "<- Back" button.
    form_requested(object)   -- "+ New Payment" (None) / per-row Edit
                                 (payment_id).
    view_requested(int)      -- per-row "View".
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QAbstractItemView,
    QVBoxLayout,
)

from engines.exceptions import (
    RecordNotFoundError,
    ValidationError,
)
from engines.date_engine import DateEngineError
from engines import date_engine
from models.payment_model import PaymentSearchFilters
from engines.payment_engine import PaymentDTO
from utils.message import show_error, show_info, confirm
from screens.cancellation_reason_dialog import CancellationReasonDialog

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ["", "Draft", "Posted", "Cancelled"]
PAYMENT_MODE_OPTIONS = ["", "Cash", "Bank Transfer", "Cheque", "Card", "Other"]


class PaymentListScreen(QWidget):
    """List/search/filter screen for Payments. Opening Add/Edit/View is
    delegated to Dashboard via signals (see module docstring)."""

    close_requested = Signal()
    form_requested = Signal(object)   # payment_id (int) for Edit, or None for Add
    view_requested = Signal(int)      # payment_id for View

    TABLE_HEADERS = [
        "Payment #", "Date (BS)", "Supplier", "Mode", "Amount", "Allocated", "Advance", "Status", "Actions",
    ]

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: "PaymentEngine",
        current_user_id: int,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._current_user_id = current_user_id
        self._embedded = embedded
        self._rows_cache: list[PaymentDTO] = []

        self.setObjectName("scrPaymentList")

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_bar = QHBoxLayout()

        if self._embedded:
            self.btnBack = QPushButton("\u2190 Back", self)
            self.btnBack.setObjectName("btnBack")
            self.btnBack.setCursor(Qt.CursorShape.PointingHandCursor)
            top_bar.addWidget(self.btnBack)
        else:
            top_bar.addStretch(1)

        lbl_title = QLabel("Payments", self)
        lbl_title.setStyleSheet("font-weight: 600; font-size: 15px;")
        top_bar.addWidget(lbl_title)
        top_bar.addStretch(1)

        self.btn_new = QPushButton("+ New Payment", self)
        self.btn_new.setObjectName("btnNewPayment")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        top_bar.addWidget(self.btn_new)
        root.addLayout(top_bar)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        filter_bar.addWidget(QLabel("Search:", self))
        self.txtSearch = QLineEdit(self)
        self.txtSearch.setPlaceholderText("Payment #, supplier name, reference...")
        self.txtSearch.setObjectName("txtSearch")
        filter_bar.addWidget(self.txtSearch, stretch=2)

        filter_bar.addWidget(QLabel("Supplier:", self))
        self.cmbSupplier = QComboBox(self)
        self.cmbSupplier.setObjectName("cmbSupplier")
        self.cmbSupplier.addItem("-- All --", userData=None)
        filter_bar.addWidget(self.cmbSupplier, stretch=2)

        filter_bar.addWidget(QLabel("Mode:", self))
        self.cmbPaymentMode = QComboBox(self)
        self.cmbPaymentMode.setObjectName("cmbPaymentMode")
        for mode in PAYMENT_MODE_OPTIONS:
            self.cmbPaymentMode.addItem(mode or "-- All --", userData=mode or None)
        filter_bar.addWidget(self.cmbPaymentMode)

        filter_bar.addWidget(QLabel("Status:", self))
        self.cmbStatus = QComboBox(self)
        self.cmbStatus.setObjectName("cmbStatus")
        for status in STATUS_OPTIONS:
            self.cmbStatus.addItem(status or "-- All --", userData=status or None)
        filter_bar.addWidget(self.cmbStatus)

        filter_bar.addWidget(QLabel("From:", self))
        self.dtFrom = QLineEdit(self)
        self.dtFrom.setPlaceholderText("BS YYYY-MM-DD")
        self.dtFrom.setObjectName("dtFrom")
        filter_bar.addWidget(self.dtFrom, stretch=1)

        filter_bar.addWidget(QLabel("To:", self))
        self.dtTo = QLineEdit(self)
        self.dtTo.setPlaceholderText("BS YYYY-MM-DD")
        self.dtTo.setObjectName("dtTo")
        filter_bar.addWidget(self.dtTo, stretch=1)

        self.btn_search = QPushButton("Search", self)
        self.btn_search.setObjectName("btnSearch")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        filter_bar.addWidget(self.btn_search)

        self.btn_clear = QPushButton("Clear", self)
        self.btn_clear.setObjectName("btnClear")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        filter_bar.addWidget(self.btn_clear)

        filter_bar.addStretch(1)
        root.addLayout(filter_bar)

        self.tblPayments = QTableWidget(self)
        self.tblPayments.setObjectName("tblPayments")
        self.tblPayments.setColumnCount(len(self.TABLE_HEADERS))
        self.tblPayments.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.tblPayments.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tblPayments.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tblPayments.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblPayments.verticalHeader().setVisible(False)
        self.tblPayments.setAlternatingRowColors(True)
        header = self.tblPayments.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self.tblPayments)

    def _connect_signals(self) -> None:
        self.btn_new.clicked.connect(lambda: self.form_requested.emit(None))

        if hasattr(self, "btnBack"):
            self.btnBack.clicked.connect(self.close_requested.emit)

        self.txtSearch.textChanged.connect(self.refresh)
        self.cmbPaymentMode.currentIndexChanged.connect(self.refresh)
        self.cmbStatus.currentIndexChanged.connect(self.refresh)
        self.btn_search.clicked.connect(self.refresh)
        self.btn_clear.clicked.connect(self._on_clear_clicked)

        self.dtFrom.editingFinished.connect(self.refresh)
        self.dtTo.editingFinished.connect(self.refresh)

    def _on_clear_clicked(self) -> None:
        self.txtSearch.clear()
        self.cmbSupplier.setCurrentIndex(0)
        self.cmbPaymentMode.setCurrentIndex(0)
        self.cmbStatus.setCurrentIndex(0)
        self.dtFrom.clear()
        self.dtTo.clear()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def _collect_filters(self) -> "PaymentSearchFilters":
        return PaymentSearchFilters(
            search_text=self.txtSearch.text().strip() or None,
            supplier_id=self.cmbSupplier.currentData() if self.cmbSupplier.currentData() else None,
            status=self.cmbStatus.currentData() if self.cmbStatus.currentData() else None,
            payment_mode=self.cmbPaymentMode.currentData() if self.cmbPaymentMode.currentData() else None,
            date_from_ad=self._parse_bs_date(self.dtFrom.text().strip()) if self.dtFrom.text().strip() else None,
            date_to_ad=self._parse_bs_date(self.dtTo.text().strip()) if self.dtTo.text().strip() else None,
            include_deleted=False,
            page=1,
            page_size=200,
        )

    @staticmethod
    def _parse_bs_date(bs_text: str) -> Optional[date]:
        try:
            return date_engine.bs_to_ad(bs_text)
        except (DateEngineError, ValueError):
            logger.warning("Failed to parse BS date '%s', ignoring date filter", bs_text)
            return None

    def refresh(self) -> None:
        try:
            filters = self._collect_filters()
            rows = self._engine.search(filters)
        except Exception as exc:
            logger.exception("payment_engine.search failed")
            show_error(f"Could not load payments. {exc}")
            return

        self._rows_cache = rows
        self.tblPayments.setRowCount(0)

        if not rows:
            msg = QLabel("No payments match your search.", self)
            msg.setStyleSheet("text-align: center; color: gray;")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tblPayments.setRowCount(1)
            self.tblPayments.setRowHeight(0, 40)
            self.tblPayments.setCellWidget(0, 0, msg)
            self.tblPayments.setSpan(0, 0, 1, self.tblPayments.columnCount())
            return

        for row_idx, dto in enumerate(rows):
            self.tblPayments.insertRow(row_idx)
            self._set_row_data(row_idx, dto)

    def _set_row_data(self, row: int, dto: "PaymentDTO") -> None:
        col_data = [
            str(dto.payment_number),
            dto.payment_date_bs,
            dto.supplier_name or "",
            dto.payment_mode,
            f"Rs {dto.amount:.2f}",
            f"Rs {dto.allocated_amount:.2f}",
            f"Rs {dto.advance_amount:.2f}",
            dto.status,
        ]
        for col, value in enumerate(col_data):
            item = QTableWidgetItem(value)
            if col == 7:
                if dto.status == "Posted":
                    item.setForeground(Qt.GlobalColor.darkGreen)
                elif dto.status == "Cancelled":
                    item.setForeground(Qt.GlobalColor.red)
                elif dto.status == "Draft":
                    item.setForeground(Qt.GlobalColor.gray)
            else:
                if col in (4, 5, 6):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.tblPayments.setItem(row, col, item)

        action_widget = self._build_action_cell(dto.payment_id, dto.status)
        self.tblPayments.setCellWidget(row, 8, action_widget)

    def _build_action_cell(self, payment_id: int, status: str) -> QWidget:
        cell = QWidget(self.tblPayments)
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        btn_view = QPushButton("View", cell)
        btn_view.setObjectName("btnViewPayment")
        btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view.clicked.connect(lambda: self.view_requested.emit(payment_id))
        layout.addWidget(btn_view)

        if status == "Posted":
            btn_edit = QPushButton("Edit", cell)
            btn_edit.setObjectName("btnEditPayment")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda: self.form_requested.emit(payment_id))
            layout.addWidget(btn_edit)

            btn_cancel = QPushButton("Cancel", cell)
            btn_cancel.setObjectName("btnCancelPayment")
            btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cancel.clicked.connect(lambda: self._on_cancel_clicked(payment_id))
            layout.addWidget(btn_cancel)
        elif status == "Draft":
            btn_delete = QPushButton("Delete", cell)
            btn_delete.setObjectName("btnDeletePayment")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.clicked.connect(lambda: self._on_delete_clicked(payment_id))
            layout.addWidget(btn_delete)

        layout.addStretch(1)
        return cell

    def _on_cancel_clicked(self, payment_id: int) -> None:
        dialog = CancellationReasonDialog(self)
        if not dialog.exec():
            return
        reason = dialog.get_reason()
        if not reason:
            show_error("A cancellation reason is required.")
            return

        try:
            self._engine.cancel_payment(
                payment_id=payment_id,
                cancellation_reason=reason,
                updated_by=self._current_user_id,
            )
        except (ValidationError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error cancelling payment_id=%s", payment_id)
            show_error("Could not cancel this payment. Please try again.")
            return

        show_info("Payment cancelled successfully.")
        self.refresh()

    def _on_delete_clicked(self, payment_id: int) -> None:
        if not confirm("Delete this draft payment? This cannot be undone."):
            return

        try:
            self._engine.delete_draft(payment_id=payment_id, deleted_by=self._current_user_id)
        except (ValidationError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error deleting draft payment_id=%s", payment_id)
            show_error("Could not delete this payment. Please try again.")
            return

        show_info("Draft payment deleted.")
        self.refresh()