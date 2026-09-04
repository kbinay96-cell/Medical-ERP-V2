"""
screens/receipt_form_screen.py

Receipt Add/Edit/View Screen - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Customer picker (searchable combo, backed by engines.customer_engine's
      module-level get_active_customers()).
    - Header fields: Receipt Date (BS, defaults to today), Payment Mode,
      Amount, Reference No. (Bank Transfer/Cheque/Card only), Bank Name
      (same modes), Remarks.
    - On Customer + Amount entered: calls engine.get_outstanding_invoices()
      and shows a PREVIEW allocation grid, computed client-side here
      purely for instant feedback (oldest-first walk mirroring the
      Engine's own FIFO pass). The authoritative allocation is always
      whatever the Engine actually computes/accepts on Save.
    - User can override the preview (uncheck / retype / add a row),
      which switches Save from manual_allocations=None (pure auto) to
      an explicit list matching whatever is on screen.
    - Unallocated amount is shown live as "Advance: Rs {x}" -- informational,
      never blocks Save.
    - Save (new): engine.create_receipt(...) -- explicit kwargs, raises on
      failure, returns a ReceiptDTO on success.
    - Save (editing a Posted receipt): engine.edit_receipt(receipt_id,
      updated_by, header_changes={...only changed fields...},
      new_allocations=... if grid touched, else None) -- raises on
      failure, returns a ReceiptDTO on success.
    - Surfaces ValidationError / RecordNotFoundError / DuplicateRecordError
      messages back to the user.
    - read_only=True opens the same layout in View mode (all inputs
      disabled, Save hidden) -- reused by ReceiptListScreen's "View" action.

--------------------------------------------------------------------------
EMBEDDING NOTE (changed from the earlier popup version): this is now a
plain QWidget, not a QDialog -- it is meant to be pushed onto
ReceiptListScreen's internal QStackedWidget rather than opened with
.exec(). It emits two signals instead of accept()/reject():

    saved            -- emitted after a successful Save (list should
                         return to its list page and refresh()).
    back_requested    -- emitted when the "<- Back" button is pressed
                         without saving (list should just return to its
                         list page, no refresh needed).

See ReceiptListScreen for how these are connected.
--------------------------------------------------------------------------

REAL INTERFACES THIS FILE MATCHES (verified against the actual repo
during Receipt Part 3 wiring):

    - engines.receipt_engine.ReceiptEngine.get_outstanding_invoices(customer_id)
      -> list[dict], each: sale_invoice_id, invoice_number, invoice_date_ad
      (an AD date, NOT bs), outstanding_amount.

    - ReceiptEngine.create_receipt(
          customer_id: int, receipt_date_ad: date, payment_mode: str,
          amount: float, created_by: int, reference_no: Optional[str] = None,
          bank_name: Optional[str] = None, remarks: Optional[str] = None,
          manual_allocations: Optional[list[dict]] = None,
          status: str = "Posted",
      ) -> ReceiptDTO
      Raises ValidationError / DuplicateRecordError on failure -- does
      NOT return a (bool, str, id) tuple. receipt_date_bs and
      receipt_number are computed internally by the Engine.

    - ReceiptEngine.edit_receipt(receipt_id, updated_by, header_changes,
      new_allocations) -> ReceiptDTO. Raises on failure.

    - ReceiptEngine.get_by_id(receipt_id) -> Optional[ReceiptDTO]. Use
      `.to_dict()` for convenient field access, or `.allocations` (a list
      of ReceiptAllocationDTO: receipt_allocation_id, sale_invoice_id,
      allocated_amount, is_auto_allocated, remarks, invoice_number).

    - engines.exceptions.ValidationError / DuplicateRecordError /
      RecordNotFoundError (NOT utils.exceptions -- that module doesn't exist).

    - engines.date_engine.ad_to_bs(ad_date) -> str, bs_to_ad(bs_text) -> date,
      both can raise DateEngineError -- wrapped in try/except here.

    - engines.customer_engine is a MODULE of plain functions, not a class.
      get_active_customers() -> list[dict] with customer_id, customer_code,
      customer_name -- loaded once at open time; typing in the combo
      filters the already-loaded list via a QCompleter.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
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

from engines import date_engine
from engines.date_engine import DateEngineError
from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from utils.message import show_error, show_info

if TYPE_CHECKING:
    from engines.receipt_engine import ReceiptEngine

logger = logging.getLogger(__name__)

_PAYMENT_MODES = ["Cash", "Bank Transfer", "Cheque", "Card", "Other"]
_MODES_REQUIRING_REFERENCE = {"Bank Transfer", "Cheque", "Card"}

_ALLOCATION_COLUMNS = ["", "Invoice No.", "Invoice Date (BS)", "Outstanding", "Allocate Amount"]
_COL_CHECK = 0
_COL_INVOICE_NO = 1
_COL_INVOICE_DATE = 2
_COL_OUTSTANDING = 3
_COL_ALLOCATE = 4


def _safe_ad_to_bs(ad_value: Any) -> str:
    """Best-effort AD -> BS conversion for display. Never raises -- falls
    back to the raw value's string form so a bad/edge-case date never
    crashes the preview grid."""
    if ad_value is None:
        return ""
    try:
        return date_engine.ad_to_bs(ad_value)
    except DateEngineError:
        logger.warning("ad_to_bs failed for value=%r; showing raw value.", ad_value)
        return str(ad_value)


class ReceiptFormScreen(QWidget):
    """Add / Edit / View screen for a single Receipt -- embeddable page,
    meant to be pushed onto ReceiptListScreen's internal QStackedWidget.

    Args:
        parent: Parent widget (typically ReceiptListScreen's stack).
        engine: The shared ReceiptEngine instance.
        current_userid: The logged-in user's id, used as created_by/updated_by.
        customer_engine: The engines.customer_engine MODULE (pass the module
            itself, e.g. `from engines import customer_engine` then
            `customer_engine=customer_engine`), not an instance of a class.
        receipt_id: Pass to open in Edit (or View) mode; omit for Add mode.
        read_only: Opens in View mode -- all inputs disabled, no Save.
    """

    saved = Signal()
    back_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: "ReceiptEngine",
        current_userid: int,
        customer_engine=None,
        receipt_id: Optional[int] = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._current_userid = current_userid
        self._customer_engine = customer_engine
        self._receipt_id = receipt_id
        self._read_only = read_only
        self._is_edit_mode = receipt_id is not None

        # Original values as loaded from the Engine (Edit mode only) --
        # used to compute a real diff for edit_receipt's header_changes.
        self._original_header: dict = {}
        self._original_allocations: list[dict] = []
        self._allocation_grid_touched = False
        self._selected_customer_id: Optional[int] = None

        self.setObjectName("scrReceiptForm")

        self._build_ui()
        self._connect_signals()
        self._load_customer_list()

        if self._is_edit_mode:
            self._load_existing_receipt()
        else:
            self.dtReceiptDate.setText(_safe_ad_to_bs(date.today()))

        if self._read_only:
            self._apply_read_only_mode()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ---- Top bar: Back + title ---------------------------------------- #
        top_bar = QHBoxLayout()
        self.btnBack = QPushButton("\u2190 Back", self)
        self.btnBack.setObjectName("btnBack")
        self.btnBack.setCursor(Qt.CursorShape.PointingHandCursor)
        top_bar.addWidget(self.btnBack)

        title = "View Receipt" if self._read_only else ("Edit Receipt" if self._is_edit_mode else "New Receipt")
        self.lblFormTitle = QLabel(title, self)
        self.lblFormTitle.setObjectName("lblFormTitle")
        self.lblFormTitle.setStyleSheet("font-weight: 600; font-size: 15px;")
        top_bar.addWidget(self.lblFormTitle)
        top_bar.addStretch(1)
        root.addLayout(top_bar)

        form = QFormLayout()
        form.setSpacing(8)

        self.cmbCustomer = QComboBox(self)
        self.cmbCustomer.setObjectName("cmbCustomer")
        self.cmbCustomer.setEditable(True)
        self.cmbCustomer.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cmbCustomer.setPlaceholderText("Search customer...")
        form.addRow("Customer:", self.cmbCustomer)

        self.dtReceiptDate = QLineEdit(self)
        self.dtReceiptDate.setObjectName("dtReceiptDate")
        self.dtReceiptDate.setPlaceholderText("YYYY-MM-DD (BS)")
        form.addRow("Receipt Date (BS):", self.dtReceiptDate)

        self.cmbPaymentMode = QComboBox(self)
        self.cmbPaymentMode.setObjectName("cmbPaymentMode")
        self.cmbPaymentMode.addItems(_PAYMENT_MODES)
        form.addRow("Payment Mode:", self.cmbPaymentMode)

        self.txtAmount = QDoubleSpinBox(self)
        self.txtAmount.setObjectName("txtAmount")
        self.txtAmount.setMaximum(99_999_999.99)
        self.txtAmount.setDecimals(2)
        self.txtAmount.setPrefix("Rs ")
        form.addRow("Amount:", self.txtAmount)

        self.txtReferenceNo = QLineEdit(self)
        self.txtReferenceNo.setObjectName("txtReferenceNo")
        form.addRow("Reference No.:", self.txtReferenceNo)

        self.txtBankName = QLineEdit(self)
        self.txtBankName.setObjectName("txtBankName")
        form.addRow("Bank Name:", self.txtBankName)

        self.txtRemarks = QTextEdit(self)
        self.txtRemarks.setObjectName("txtRemarks")
        self.txtRemarks.setFixedHeight(60)
        form.addRow("Remarks:", self.txtRemarks)

        root.addLayout(form)

        # ---- Allocation preview grid ------------------------------------ #
        root.addWidget(QLabel("Outstanding Invoices (FIFO preview -- editable):", self))

        self.tblAllocations = QTableWidget(0, len(_ALLOCATION_COLUMNS), self)
        self.tblAllocations.setObjectName("tblAllocations")
        self.tblAllocations.setHorizontalHeaderLabels(_ALLOCATION_COLUMNS)
        self.tblAllocations.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tblAllocations.verticalHeader().setVisible(False)
        header = self.tblAllocations.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.tblAllocations, stretch=1)

        self.lblAdvance = QLabel("Advance: Rs 0.00", self)
        self.lblAdvance.setObjectName("lblAdvance")
        self.lblAdvance.setStyleSheet("font-weight: 600;")
        self.lblAdvance.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.lblAdvance)

        # ---- Footer ------------------------------------------------------ #
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.btnSave = QPushButton("Save", self)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self.btnSave)
        root.addLayout(footer)

    def _connect_signals(self) -> None:
        self.btnBack.clicked.connect(self.back_requested.emit)
        self.btnSave.clicked.connect(self._on_save_clicked)
        self.cmbCustomer.currentIndexChanged.connect(self._on_customer_or_amount_changed)
        self.txtAmount.valueChanged.connect(self._on_customer_or_amount_changed)
        self.cmbPaymentMode.currentTextChanged.connect(self._on_payment_mode_changed)
        self.tblAllocations.itemChanged.connect(self._on_allocation_row_changed)
        self._on_payment_mode_changed(self.cmbPaymentMode.currentText())

    def _apply_read_only_mode(self) -> None:
        for widget in (
            self.cmbCustomer,
            self.dtReceiptDate,
            self.cmbPaymentMode,
            self.txtAmount,
            self.txtReferenceNo,
            self.txtBankName,
            self.txtRemarks,
        ):
            widget.setEnabled(False)
        self.tblAllocations.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.btnSave.setVisible(False)

    # ------------------------------------------------------------------ #
    # Customer list (loaded once, filtered client-side via QCompleter --
    # get_active_customers() is documented as the ONE selection-list call
    # Receipt/Sales/Order Entry should make, not a per-keystroke search)
    # ------------------------------------------------------------------ #
    def _load_customer_list(self) -> None:
        if not self._customer_engine:
            return
        try:
            customers = self._customer_engine.get_active_customers()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load active customer list.")
            show_error("Could not load the customer list. Please try again.")
            return

        self.cmbCustomer.blockSignals(True)
        self.cmbCustomer.clear()
        names = []
        for customer in customers:
            name = customer.get("customer_name", "")
            self.cmbCustomer.addItem(name, userData=customer.get("customer_id"))
            names.append(name)
        self.cmbCustomer.setCurrentIndex(-1)
        self.cmbCustomer.blockSignals(False)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated.connect(self._on_customer_completer_activated)
        self.cmbCustomer.setCompleter(completer)

    def _on_customer_completer_activated(self, text: str) -> None:
        index = self.cmbCustomer.findText(text)
        if index >= 0:
            self.cmbCustomer.setCurrentIndex(index)

    # ------------------------------------------------------------------ #
    # Payment mode conditional fields
    # ------------------------------------------------------------------ #
    def _on_payment_mode_changed(self, mode: str) -> None:
        needs_reference = mode in _MODES_REQUIRING_REFERENCE
        self.txtReferenceNo.setVisible(needs_reference)
        self.txtBankName.setVisible(needs_reference)

    # ------------------------------------------------------------------ #
    # FIFO preview
    # ------------------------------------------------------------------ #
    def _on_customer_or_amount_changed(self) -> None:
        if self._read_only:
            return
        customer_id = self.cmbCustomer.currentData()
        amount = self.txtAmount.value()
        if not customer_id or amount <= 0:
            return
        self._selected_customer_id = customer_id
        self._load_fifo_preview(customer_id, amount)

    def _load_fifo_preview(self, customer_id: int, amount: float) -> None:
        try:
            outstanding_invoices = self._engine.get_outstanding_invoices(customer_id)
        except ValidationError as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error loading outstanding invoices for customer_id=%s", customer_id)
            show_error("Could not load outstanding invoices for this customer.")
            return

        allocation_rows = self._compute_fifo_allocation(outstanding_invoices, amount)
        self._allocation_grid_touched = False
        self._populate_allocation_grid(allocation_rows)

    @staticmethod
    def _compute_fifo_allocation(outstanding_invoices: list[dict], amount: float) -> list[dict]:
        """Client-side mirror of the Engine's oldest-first FIFO walk, used
        purely for instant on-screen preview. Never authoritative -- the
        Engine recomputes/validates independently on Save.

        Real row keys from ReceiptEngine.get_outstanding_invoices():
        sale_invoice_id, invoice_number, invoice_date_ad, outstanding_amount.
        """
        remaining = amount
        rows: list[dict] = []
        for invoice in outstanding_invoices:
            outstanding = float(invoice.get("outstanding_amount", 0))
            allocate = min(outstanding, remaining) if remaining > 0 else 0.0
            rows.append(
                {
                    "sale_invoice_id": invoice.get("sale_invoice_id"),
                    "invoice_number": invoice.get("invoice_number", ""),
                    "invoice_date_bs": _safe_ad_to_bs(invoice.get("invoice_date_ad")),
                    "outstanding_amount": outstanding,
                    "allocate_amount": round(allocate, 2),
                    "checked": allocate > 0,
                }
            )
            remaining = max(0.0, remaining - allocate)
        return rows

    def _populate_allocation_grid(self, allocation_rows: list[dict]) -> None:
        self.tblAllocations.blockSignals(True)
        self.tblAllocations.setRowCount(len(allocation_rows))

        for row_index, row in enumerate(allocation_rows):
            chk = QCheckBox(self.tblAllocations)
            chk.setChecked(row["checked"])
            chk.stateChanged.connect(self._on_allocation_row_changed)
            chk_container = QWidget(self.tblAllocations)
            chk_layout = QHBoxLayout(chk_container)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tblAllocations.setCellWidget(row_index, _COL_CHECK, chk_container)

            self._set_readonly_cell(row_index, _COL_INVOICE_NO, row["invoice_number"])
            self._set_readonly_cell(row_index, _COL_INVOICE_DATE, row["invoice_date_bs"])
            self._set_readonly_cell(row_index, _COL_OUTSTANDING, f"{row['outstanding_amount']:,.2f}")

            allocate_item = QTableWidgetItem(f"{row['allocate_amount']:,.2f}")
            allocate_item.setData(Qt.ItemDataRole.UserRole, row["sale_invoice_id"])
            self.tblAllocations.setItem(row_index, _COL_ALLOCATE, allocate_item)

        self.tblAllocations.blockSignals(False)
        self._recalculate_advance()

    def _set_readonly_cell(self, row: int, column: int, value: object) -> None:
        item = QTableWidgetItem("" if value is None else str(value))
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        self.tblAllocations.setItem(row, column, item)

    def _on_allocation_row_changed(self, *_args) -> None:
        self._allocation_grid_touched = True
        self._recalculate_advance()

    def _recalculate_advance(self) -> None:
        total_amount = self.txtAmount.value()
        allocated_total = 0.0
        for row_index in range(self.tblAllocations.rowCount()):
            if not self._is_row_checked(row_index):
                continue
            allocate_item = self.tblAllocations.item(row_index, _COL_ALLOCATE)
            allocated_total += self._parse_amount(allocate_item.text() if allocate_item else "0")

        advance = max(0.0, total_amount - allocated_total)
        self.lblAdvance.setText(f"Advance: Rs {advance:,.2f}")

    def _is_row_checked(self, row_index: int) -> bool:
        container = self.tblAllocations.cellWidget(row_index, _COL_CHECK)
        if container is None:
            return False
        checkbox = container.findChild(QCheckBox)
        return bool(checkbox and checkbox.isChecked())

    @staticmethod
    def _parse_amount(text: str) -> float:
        try:
            return float(text.replace(",", "").replace("Rs", "").strip() or 0.0)
        except ValueError:
            return 0.0

    def _collect_allocations(self) -> list[dict]:
        """Returns manual_allocations in the shape ReceiptEngine expects:
        a list of {"sale_invoice_id": int, "allocated_amount": float}."""
        allocations: list[dict] = []
        for row_index in range(self.tblAllocations.rowCount()):
            if not self._is_row_checked(row_index):
                continue
            allocate_item = self.tblAllocations.item(row_index, _COL_ALLOCATE)
            amount = self._parse_amount(allocate_item.text() if allocate_item else "0")
            if amount <= 0:
                continue
            allocations.append(
                {
                    "sale_invoice_id": allocate_item.data(Qt.ItemDataRole.UserRole),
                    "allocated_amount": amount,
                }
            )
        return allocations

    # ------------------------------------------------------------------ #
    # Edit mode: load existing receipt
    # ------------------------------------------------------------------ #
    def _load_existing_receipt(self) -> None:
        try:
            receipt_dto = self._engine.get_by_id(self._receipt_id)
        except ValidationError as exc:
            show_error(str(exc))
            self.back_requested.emit()
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error loading receipt_id=%s", self._receipt_id)
            show_error("Could not load this receipt. Please try again.")
            self.back_requested.emit()
            return

        if receipt_dto is None:
            show_error("This receipt could not be found. It may have been removed.")
            self.back_requested.emit()
            return

        receipt = receipt_dto.to_dict()
        self._original_header = dict(receipt)
        self._original_allocations = list(receipt.get("allocations", []) or [])

        self.cmbCustomer.blockSignals(True)
        index = self.cmbCustomer.findData(receipt.get("customer_id"))
        if index < 0:
            self.cmbCustomer.addItem(receipt.get("customer_name", ""), userData=receipt.get("customer_id"))
            index = self.cmbCustomer.count() - 1
        self.cmbCustomer.setCurrentIndex(index)
        self.cmbCustomer.blockSignals(False)
        self._selected_customer_id = receipt.get("customer_id")

        self.dtReceiptDate.setText(receipt.get("receipt_date_bs", "") or "")
        self.cmbPaymentMode.setCurrentText(receipt.get("payment_mode", "Cash"))
        self.txtAmount.setValue(float(receipt.get("amount", 0)))
        self.txtReferenceNo.setText(receipt.get("reference_no", "") or "")
        self.txtBankName.setText(receipt.get("bank_name", "") or "")
        self.txtRemarks.setPlainText(receipt.get("remarks", "") or "")

        allocation_rows = [
            {
                "sale_invoice_id": alloc.get("sale_invoice_id"),
                "invoice_number": alloc.get("invoice_number", ""),
                "invoice_date_bs": "",  # not returned on the allocation DTO; grid shows outstanding/amount only in Edit mode
                "outstanding_amount": float(alloc.get("allocated_amount", 0)),
                "allocate_amount": float(alloc.get("allocated_amount", 0)),
                "checked": True,
            }
            for alloc in self._original_allocations
        ]
        self._populate_allocation_grid(allocation_rows)
        self._allocation_grid_touched = False

    def _collect_header_changes(self) -> dict:
        """Edit mode only -- diff current form values against the
        originally loaded receipt, returns ONLY the changed keys."""
        current = {
            "customer_id": self._selected_customer_id,
            "receipt_date_bs": self.dtReceiptDate.text().strip(),
            "payment_mode": self.cmbPaymentMode.currentText(),
            "amount": self.txtAmount.value(),
            "reference_no": self.txtReferenceNo.text().strip() or None,
            "bank_name": self.txtBankName.text().strip() or None,
            "remarks": self.txtRemarks.toPlainText().strip() or None,
        }
        changes = {}
        for key, new_value in current.items():
            old_value = self._original_header.get(key)
            if old_value != new_value:
                changes[key] = new_value
        return changes

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _on_save_clicked(self) -> None:
        if self._read_only:
            return

        customer_id = self.cmbCustomer.currentData()
        if not customer_id:
            show_error("Please select a customer.")
            return

        bs_date_text = self.dtReceiptDate.text().strip()
        try:
            receipt_date_ad = date_engine.bs_to_ad(bs_date_text)
        except DateEngineError as exc:
            show_error(f"Invalid receipt date: {exc}")
            return

        # Pure-auto (None) unless the user actually touched the grid.
        manual_allocations = self._collect_allocations() if self._allocation_grid_touched else None

        try:
            if self._is_edit_mode:
                header_changes = self._collect_header_changes()
                new_allocations = self._collect_allocations() if self._allocation_grid_touched else None
                receipt_dto = self._engine.edit_receipt(
                    receipt_id=self._receipt_id,
                    updated_by=self._current_userid,
                    header_changes=header_changes or None,
                    new_allocations=new_allocations,
                )
            else:
                receipt_dto = self._engine.create_receipt(
                    customer_id=customer_id,
                    receipt_date_ad=receipt_date_ad,
                    payment_mode=self.cmbPaymentMode.currentText(),
                    amount=self.txtAmount.value(),
                    created_by=self._current_userid,
                    reference_no=self.txtReferenceNo.text().strip() or None,
                    bank_name=self.txtBankName.text().strip() or None,
                    remarks=self.txtRemarks.toPlainText().strip() or None,
                    manual_allocations=manual_allocations,
                )
        except (ValidationError, DuplicateRecordError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error saving receipt (edit_mode=%s)", self._is_edit_mode)
            show_error("Could not save this receipt. Please try again.")
            return

        show_info(f"Receipt {receipt_dto.receipt_number} saved successfully.")
        self.saved.emit()