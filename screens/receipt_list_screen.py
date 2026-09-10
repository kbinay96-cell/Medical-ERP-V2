"""
screens/receipt_list_screen.py

Receipt List Screen - Medical ERP V2

Responsibility (and ONLY this -- "No SQL. No business logic."):
    - List/search/filter Receipts (Customer/Receipt No./Reference text,
      Payment Mode, Status, Date range).
    - View (read-only inline form), Edit (Posted only, inline form),
      Cancel (Posted only, via the shared CancellationReasonDialog),
      Delete (Draft only), View Audit Log.

--------------------------------------------------------------------------
EMBEDDING CONVENTION (matches CompanyListScreen / ItemListScreen exactly,
as confirmed against the real dashboard_screen.py during Receipt Part 3
wiring): this Screen no longer owns its own internal QStackedWidget.
Instead it is a plain QWidget constructed with `embedded=True` and
pushed onto Dashboard's `self.ui.stackedContentArea` via `_navigate_to()`.
Opening the Add/Edit/View form is Dashboard's job, not this Screen's:

    close_requested          -- emitted by this Screen's own "<- Back"
                                 button (leaves the Receipt module
                                 entirely). Dashboard connects this to
                                 `_navigate_back`, same as
                                 CompanyListScreen/ItemListScreen.
    form_requested(object)    -- emitted for "+ New Receipt" (arg=None)
                                 and per-row "Edit" (arg=receipt_id).
                                 Dashboard connects this to
                                 `_open_receipt_form(receipt_id=None)`,
                                 which builds ReceiptFormScreen(embedded=True)
                                 and calls `_navigate_to()`.
    view_requested(int)       -- emitted for per-row "View". Dashboard
                                 connects this to `_view_receipt_form`,
                                 which builds the same form with
                                 read_only=True. (Company/Item didn't need
                                 a separate read-only view signal; Receipt
                                 does, per the original blueprint's View
                                 action -- this is a deliberate, documented
                                 extension of the established convention,
                                 not a guess at it.)

After the form's `saved` signal fires, Dashboard's `_on_receipt_form_saved`
calls `_navigate_back()` and then `self.receipt_list.refresh()` -- this
Screen's `refresh()` is unchanged from before.
--------------------------------------------------------------------------

REAL INTERFACES THIS FILE MATCHES (verified against the actual repo
during Receipt Part 3 wiring):

    - There is no ReceiptEngine.list_receipts(). The real method is
      `search(filters: ReceiptSearchFilters) -> list[ReceiptDTO]`
      (models/receipt_model.py's ReceiptSearchFilters dataclass):
          search_text, customer_id, status, payment_mode,
          date_from_ad, date_to_ad, include_deleted, page, page_size.

    - Rows returned are ReceiptDTO objects, not dicts -- accessed via
      .receipt_number, .receipt_date_bs, .customer_name, .payment_mode,
      .amount, .advance_amount, .status, .receipt_id.

    - cancel_receipt(receipt_id, cancellation_reason, updated_by) ->
      ReceiptDTO. Raises ValidationError / RecordNotFoundError on failure.

    - delete_draft(receipt_id, deleted_by) -> None. Raises
      ValidationError / RecordNotFoundError on failure -- no success
      message comes back from the Engine, so a static message is shown.

    - engines.exceptions.ValidationError / RecordNotFoundError.

    - Dashboard's own convention for the acting user's id is
      `current_user_id` (matches PurchaseOrderListScreen / SaleInvoiceListScreen
      / etc, all called with `current_user_id=self.login_result.userid`)
      -- renamed from the earlier draft's `current_userid` to match.

    - screens/cancellation_reason_dialog.py did not exist in the real
      repo -- created alongside this file (kept as a genuine small popup
      dialog; Company/Item's embedded convention is about full-page
      navigation, not about small confirmation-style dialogs).
--------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from engines.exceptions import RecordNotFoundError, ValidationError
from utils.message import confirm, show_error, show_info
from screens.cancellation_reason_dialog import CancellationReasonDialog
from screens.receipt_audit_log_dialog import ReceiptAuditLogDialog

if TYPE_CHECKING:
    from engines.receipt_engine import ReceiptEngine
    from models.receipt_model import ReceiptSearchFilters

logger = logging.getLogger(__name__)

_STATUS_OPTIONS = ["All", "Draft", "Posted", "Cancelled"]
_PAYMENT_MODE_OPTIONS = ["All", "Cash", "Bank Transfer", "Cheque", "Card", "Other"]

_COLUMN_HEADERS = [
    "Receipt No.",
    "Date (BS)",
    "Customer",
    "Payment Mode",
    "Amount",
    "Advance",
    "Status",
    "Actions",
]


class ReceiptListScreen(QWidget):
    """List/search/filter screen for Receipts. Opening Add/Edit/View is
    delegated to Dashboard via signals (see module docstring) -- this
    Screen never opens ReceiptFormScreen itself."""

    close_requested = Signal()
    form_requested = Signal(object)  # receipt_id (int) for Edit, or None for Add
    view_requested = Signal(int)  # receipt_id, always for an existing receipt

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: "ReceiptEngine",
        current_user_id: int,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._current_user_id = current_user_id
        self._embedded = embedded
        self._rows_cache: list = []

        self.setObjectName("scrReceiptList")
        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ---- Top bar: Back + Toolbar ------------------------------------ #
        top_bar = QHBoxLayout()
        self.btnBack = QPushButton("\u2190 Back", self)
        self.btnBack.setObjectName("btnBack")
        self.btnBack.setCursor(Qt.CursorShape.PointingHandCursor)
        top_bar.addWidget(self.btnBack)

        self.toolbarReceipt = QToolBar(self)
        self.toolbarReceipt.setObjectName("toolbarReceipt")
        self.btnNewReceipt = QPushButton("+ New Receipt", self)
        self.btnNewReceipt.setObjectName("btnNewReceipt")
        self.btnNewReceipt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toolbarReceipt.addWidget(self.btnNewReceipt)
        top_bar.addWidget(self.toolbarReceipt)
        top_bar.addStretch(1)
        root.addLayout(top_bar)

        # ---- Filter bar ------------------------------------------------ #
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        filter_bar.addWidget(QLabel("Search:"))
        self.txtSearchText = QLineEdit(self)
        self.txtSearchText.setObjectName("txtSearchText")
        self.txtSearchText.setPlaceholderText("Receipt no. / customer name / reference no...")
        filter_bar.addWidget(self.txtSearchText, stretch=2)

        filter_bar.addWidget(QLabel("Payment Mode:"))
        self.cmbPaymentModeFilter = QComboBox(self)
        self.cmbPaymentModeFilter.setObjectName("cmbPaymentModeFilter")
        self.cmbPaymentModeFilter.addItems(_PAYMENT_MODE_OPTIONS)
        filter_bar.addWidget(self.cmbPaymentModeFilter, stretch=1)

        filter_bar.addWidget(QLabel("Status:"))
        self.cmbStatusFilter = QComboBox(self)
        self.cmbStatusFilter.setObjectName("cmbStatusFilter")
        self.cmbStatusFilter.addItems(_STATUS_OPTIONS)
        filter_bar.addWidget(self.cmbStatusFilter, stretch=1)

        filter_bar.addWidget(QLabel("From:"))
        self.dtFromDate = QDateEdit(self)
        self.dtFromDate.setObjectName("dtFromDate")
        self.dtFromDate.setCalendarPopup(True)
        self.dtFromDate.setDate(self.dtFromDate.minimumDate())
        filter_bar.addWidget(self.dtFromDate, stretch=1)

        filter_bar.addWidget(QLabel("To:"))
        self.dtToDate = QDateEdit(self)
        self.dtToDate.setObjectName("dtToDate")
        self.dtToDate.setCalendarPopup(True)
        filter_bar.addWidget(self.dtToDate, stretch=1)

        self.btnApplyFilter = QPushButton("Filter", self)
        self.btnApplyFilter.setObjectName("btnApplyFilter")
        filter_bar.addWidget(self.btnApplyFilter)

        self.btnClearFilter = QPushButton("Clear", self)
        self.btnClearFilter.setObjectName("btnClearFilter")
        filter_bar.addWidget(self.btnClearFilter)

        root.addLayout(filter_bar)

        # ---- Table ------------------------------------------------------ #
        self.tblReceipts = QTableWidget(0, len(_COLUMN_HEADERS), self)
        self.tblReceipts.setObjectName("tblReceipts")
        self.tblReceipts.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.tblReceipts.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblReceipts.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tblReceipts.setAlternatingRowColors(True)
        self.tblReceipts.verticalHeader().setVisible(False)
        header = self.tblReceipts.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(len(_COLUMN_HEADERS) - 1, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.tblReceipts, stretch=1)

        self.lblEmptyState = QLabel("No receipts found for the selected filters.", self)
        self.lblEmptyState.setObjectName("lblReceiptListEmpty")
        self.lblEmptyState.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblEmptyState.setVisible(False)
        root.addWidget(self.lblEmptyState)

    def _connect_signals(self) -> None:
        self.btnBack.clicked.connect(self.close_requested.emit)
        self.btnNewReceipt.clicked.connect(lambda: self.form_requested.emit(None))
        self.btnApplyFilter.clicked.connect(self.refresh)
        self.btnClearFilter.clicked.connect(self._on_clear_filter_clicked)

    # ------------------------------------------------------------------ #
    # Data loading
    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        """Re-queries the Engine using the current filter bar values and
        repopulates the table. Called on load, after Filter/Clear, and
        by Dashboard's `_on_receipt_form_saved` after a Save."""
        filters = self._collect_filters()
        try:
            self._rows_cache = self._engine.search(filters)
        except ValidationError as exc:
            show_error(str(exc))
            self._rows_cache = []
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error searching receipts with filters=%s", filters)
            show_error("Could not load the receipt list. Please try again.")
            self._rows_cache = []

        self._populate_table(self._rows_cache)

    def _collect_filters(self) -> "ReceiptSearchFilters":
        from models.receipt_model import ReceiptSearchFilters  # local import: only Model owns this dataclass

        search_text = self.txtSearchText.text().strip() or None
        payment_mode = self.cmbPaymentModeFilter.currentText()
        status = self.cmbStatusFilter.currentText()

        return ReceiptSearchFilters(
            search_text=search_text,
            status=None if status == "All" else status,
            payment_mode=None if payment_mode == "All" else payment_mode,
            date_from_ad=(
                None
                if self.dtFromDate.date() == self.dtFromDate.minimumDate()
                else self.dtFromDate.date().toPython()
            ),
            date_to_ad=self.dtToDate.date().toPython(),
        )

    def _on_clear_filter_clicked(self) -> None:
        self.txtSearchText.clear()
        self.cmbPaymentModeFilter.setCurrentIndex(0)
        self.cmbStatusFilter.setCurrentIndex(0)
        self.dtFromDate.setDate(self.dtFromDate.minimumDate())
        self.refresh()

    def _populate_table(self, rows: list) -> None:
        if not rows:
            self.tblReceipts.setVisible(False)
            self.lblEmptyState.setVisible(True)
            self.tblReceipts.setRowCount(0)
            return

        self.tblReceipts.setVisible(True)
        self.lblEmptyState.setVisible(False)
        self.tblReceipts.setRowCount(len(rows))

        for row_index, receipt in enumerate(rows):
            self._set_cell(row_index, 0, receipt.receipt_number)
            self._set_cell(row_index, 1, receipt.receipt_date_bs)
            self._set_cell(row_index, 2, receipt.customer_name)
            self._set_cell(row_index, 3, receipt.payment_mode)
            self._set_cell(row_index, 4, f"{receipt.amount:,.2f}")
            self._set_cell(row_index, 5, f"{receipt.advance_amount:,.2f}")
            self._set_cell(row_index, 6, receipt.status)
            self.tblReceipts.setCellWidget(
                row_index, 7, self._build_action_cell(receipt.receipt_id, receipt.status)
            )

    def _set_cell(self, row: int, column: int, value: object) -> None:
        item = QTableWidgetItem("" if value is None else str(value))
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tblReceipts.setItem(row, column, item)

    def _build_action_cell(self, receipt_id: int, status: str) -> QWidget:
        cell = QWidget(self.tblReceipts)
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        btn_view = QPushButton("View", cell)
        btn_view.setObjectName("btnViewReceipt")
        btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view.clicked.connect(lambda: self.view_requested.emit(receipt_id))
        layout.addWidget(btn_view)

        btn_log = QPushButton("Audit Log", cell)
        btn_log.setObjectName("btnViewAuditLog")
        btn_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_log.clicked.connect(lambda: self._on_view_audit_log_clicked(receipt_id))
        layout.addWidget(btn_log)

        if status == "Posted":
            btn_edit = QPushButton("Edit", cell)
            btn_edit.setObjectName("btnEditReceipt")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda: self.form_requested.emit(receipt_id))
            layout.addWidget(btn_edit)

            btn_cancel = QPushButton("Cancel", cell)
            btn_cancel.setObjectName("btnCancelReceipt")
            btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cancel.clicked.connect(lambda: self._on_cancel_clicked(receipt_id))
            layout.addWidget(btn_cancel)
        elif status == "Draft":
            btn_delete = QPushButton("Delete", cell)
            btn_delete.setObjectName("btnDeleteReceipt")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.clicked.connect(lambda: self._on_delete_clicked(receipt_id))
            layout.addWidget(btn_delete)

        layout.addStretch(1)
        return cell

    # ------------------------------------------------------------------ #
    # Actions that stay local to this Screen (no Dashboard navigation
    # involved -- small popups, not full-page forms)
    # ------------------------------------------------------------------ #
    def _on_cancel_clicked(self, receipt_id: int) -> None:
        dialog = CancellationReasonDialog(self)
        if not dialog.exec():
            return
        reason = dialog.get_reason()
        if not reason:
            show_error("A cancellation reason is required.")
            return

        try:
            self._engine.cancel_receipt(
                receipt_id=receipt_id,
                cancellation_reason=reason,
                updated_by=self._current_user_id,
            )
        except (ValidationError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error cancelling receipt_id=%s", receipt_id)
            show_error("Could not cancel this receipt. Please try again.")
            return

        show_info("Receipt cancelled successfully.")
        self.refresh()

    def _on_delete_clicked(self, receipt_id: int) -> None:
        if not confirm("Delete this draft receipt? This cannot be undone."):
            return

        try:
            self._engine.delete_draft(receipt_id=receipt_id, deleted_by=self._current_user_id)
        except (ValidationError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error deleting draft receipt_id=%s", receipt_id)
            show_error("Could not delete this receipt. Please try again.")
            return

        show_info("Draft receipt deleted.")
        self.refresh()

    def _on_view_audit_log_clicked(self, receipt_id: int) -> None:
        dialog = ReceiptAuditLogDialog(self, engine=self._engine, receipt_id=receipt_id)
        dialog.exec()