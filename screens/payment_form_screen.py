"""
screens/payment_form_screen.py

Payment Add/Edit/View Screen - Medical ERP V2

Mirrors screens/receipt_form_screen.py exactly, applied to the supplier
side (and ONLY these responsibilities -- "No SQL. No business logic."):
    - Supplier picker (searchable combo, backed by engines.supplier_engine's
      get_active_suppliers(), matching the customer_engine convention used
      by ReceiptFormScreen).
    - Header fields: Payment Date (BS, defaults to today), Payment Mode,
      Amount, Reference No. (Bank Transfer/Cheque/Card only), Bank Name
      (same modes), Remarks.
    - On Supplier + Amount entered: calls engine.get_outstanding_invoices()
      and shows a PREVIEW allocation grid (FIFO, client-side, purely for
      instant feedback -- the authoritative allocation is always whatever
      the Engine actually computes/accepts on Save).
    - User can override the preview, same as Receipt's grid.
    - Unallocated amount shown live as "Advance: Rs {x}".
    - Save (new): engine.create_payment(...).
    - Save (editing an existing Posted payment): engine.edit_payment(
      payment_id, updated_by, header_changes={...}, new_allocations=...).
    - Surfaces ValidationError / RecordNotFoundError / DuplicateRecordError
      messages back to the user.
    - read_only=True opens the same layout in View mode.

EMBEDDING CONVENTION: identical to ReceiptFormScreen -- plain QWidget,
constructed with embedded=True, pushed onto Dashboard's
stackedContentArea via _navigate_to(). Emits:
    saved             -- after a successful Save.
    close_requested   -- when "<- Back"/"Cancel" is pressed.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QAbstractItemView,
    QSpinBox,
    QTextEdit,
    QDateEdit,
)

from engines.exceptions import (
    DuplicateRecordError,
    RecordNotFoundError,
    ValidationError,
)
from engines import date_engine
from engines.date_engine import DateEngineError
from utils.message import show_error, show_info

logger = logging.getLogger(__name__)


def _safe_ad_to_bs(ad_value: Any) -> str:
    """Best-effort AD -> BS conversion for display. Never raises."""
    if ad_value is None:
        return ""
    try:
        return date_engine.ad_to_bs(ad_value)
    except DateEngineError:
        logger.warning("ad_to_bs failed for value=%r; showing raw value.", ad_value)
        return str(ad_value)


class PaymentFormScreen(QWidget):
    """Add / Edit / View screen for a single Payment -- embeddable page,
    pushed onto Dashboard's stackedContentArea (same convention as
    ReceiptFormScreen).

    Args:
        parent: Parent widget (Dashboard, per _navigate_to's usage).
        engine: The shared PaymentEngine instance.
        current_user_id: The logged-in user's id, used as created_by/updated_by.
        supplier_engine: The engines.supplier_engine MODULE (pass the module
            itself, matching the customer_engine convention on Receipt),
            not an instance of a class.
        payment_id: Pass to open in Edit (or View) mode; omit for Add mode.
        embedded: Matches the rest of the codebase's embeddable screens.
        read_only: Opens in View mode -- all inputs disabled, no Save.
    """

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget],
        engine: "PaymentEngine",
        current_user_id: int,
        supplier_engine=None,
        payment_id: Optional[int] = None,
        embedded: bool = False,
        read_only: bool = False,
        initial_supplier_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._current_user_id = current_user_id
        self._supplier_engine = supplier_engine
        self._payment_id = payment_id
        self._embedded = embedded
        self._read_only = read_only
        self._is_edit_mode = payment_id is not None

        self._original_header: dict = {}
        self._original_allocations: list[dict] = []
        self._allocation_grid_touched = False
        self._selected_supplier_id: Optional[int] = None
        self._ob_allocated_preview: float = 0.0

        self.setObjectName("scrPaymentForm")

        self._build_ui()
        self._connect_signals()
        self._load_supplier_list()

        if self._is_edit_mode:
            self._load_existing_payment()
        elif initial_supplier_id is not None:
            self._preselect_supplier(initial_supplier_id)

        if self._read_only:
            self._apply_read_only_mode()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_bar = QHBoxLayout()
        self.btnBack = QPushButton("\u2190 Back", self)
        self.btnBack.setObjectName("btnBack")
        self.btnBack.setCursor(Qt.CursorShape.PointingHandCursor)
        top_bar.addWidget(self.btnBack)

        title = "View Payment" if self._read_only else (
            "Edit Payment" if self._is_edit_mode else "New Payment"
        )
        self.lblFormTitle = QLabel(title, self)
        self.lblFormTitle.setObjectName("lblFormTitle")
        self.lblFormTitle.setStyleSheet("font-weight: 600; font-size: 15px;")
        top_bar.addWidget(self.lblFormTitle)
        top_bar.addStretch(1)
        root.addLayout(top_bar)

        form = QFormLayout()
        form.setSpacing(8)

        self.cmbSupplier = QComboBox(self)
        self.cmbSupplier.setObjectName("cmbSupplier")
        self.cmbSupplier.setMinimumWidth(280)
        form.addRow("Supplier:", self.cmbSupplier)

        self.dtPaymentDate = QDateEdit(self)
        self.dtPaymentDate.setObjectName("dtPaymentDate")
        self.dtPaymentDate.setCalendarPopup(True)
        from PySide6.QtCore import QDate
        self.dtPaymentDate.setDate(QDate.currentDate())
        form.addRow("Payment Date (BS):", self.dtPaymentDate)

        self.cmbPaymentMode = QComboBox(self)
        self.cmbPaymentMode.setObjectName("cmbPaymentMode")
        self.cmbPaymentMode.addItems(["Cash", "Bank Transfer", "Cheque", "Card"])
        form.addRow("Payment Mode:", self.cmbPaymentMode)

        self.txtAmount = QSpinBox(self)
        self.txtAmount.setObjectName("txtAmount")
        self.txtAmount.setRange(0, 999999999)
        self.txtAmount.setSingleStep(100)
        form.addRow("Amount:", self.txtAmount)

        self.txtReferenceNo = QLineEdit(self)
        self.txtReferenceNo.setObjectName("txtReferenceNo")
        form.addRow("Reference No.:", self.txtReferenceNo)

        self.txtBankName = QLineEdit(self)
        self.txtBankName.setObjectName("txtBankName")
        form.addRow("Bank Name:", self.txtBankName)

        self.txtRemarks = QTextEdit(self)
        self.txtRemarks.setObjectName("txtRemarks")
        self.txtRemarks.setFixedHeight(80)
        form.addRow("Remarks:", self.txtRemarks)

        root.addLayout(form)

        self.lblOpeningBalance = QLabel("", self)
        self.lblOpeningBalance.setObjectName("lblOpeningBalance")
        self.lblOpeningBalance.setStyleSheet("font-weight: 600; color: #a15c00;")
        self.lblOpeningBalance.setVisible(False)
        root.addWidget(self.lblOpeningBalance)

        allocation_group_title = QLabel("Allocation (FIFO Preview)", self)
        allocation_group_title.setStyleSheet("font-weight: 600;")
        root.addWidget(allocation_group_title)

        self.tblAllocations = QTableWidget(self)
        self.tblAllocations.setObjectName("tblAllocations")
        self.tblAllocations.setColumnCount(5)
        self.tblAllocations.setHorizontalHeaderLabels(
            ["Invoice #", "Invoice Date", "Outstanding", "Allocate", "Auto"]
        )
        self.tblAllocations.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tblAllocations.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.tblAllocations)

        self.lblAdvance = QLabel("", self)
        self.lblAdvance.setObjectName("lblAdvance")
        self.lblAdvance.setStyleSheet("font-style: italic;")
        root.addWidget(self.lblAdvance)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        self.btnSave = QPushButton("Save", self)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(self.btnSave)

        self.btnCancel = QPushButton("Cancel", self)
        self.btnCancel.setObjectName("btnCancel")
        self.btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(self.btnCancel)
        button_row.addStretch(1)

        root.addLayout(button_row)

    def _connect_signals(self) -> None:
        self.btnBack.clicked.connect(self.close_requested.emit)
        self.btnCancel.clicked.connect(self.close_requested.emit)
        self.btnSave.clicked.connect(self._on_save_clicked)

        self.cmbSupplier.currentIndexChanged.connect(self._on_supplier_or_amount_changed)
        self.txtAmount.valueChanged.connect(self._on_supplier_or_amount_changed)

        self.cmbPaymentMode.currentIndexChanged.connect(self._on_payment_mode_changed)
        self._on_payment_mode_changed()

    def _on_payment_mode_changed(self) -> None:
        mode = self.cmbPaymentMode.currentText()
        needs_ref = mode in ("Bank Transfer", "Cheque", "Card")
        self.txtReferenceNo.setVisible(needs_ref)
        self.txtBankName.setVisible(needs_ref)

    def _current_payment_date_bs(self) -> str:
        """Converts whatever AD date is currently set on the QDateEdit
        into its BS display string, for header-change comparisons."""
        ad_date = self.dtPaymentDate.date().toPython()
        return _safe_ad_to_bs(ad_date)

    # ------------------------------------------------------------------ #
    # Supplier loading
    # ------------------------------------------------------------------ #
    def _load_supplier_list(self) -> None:
        if self._supplier_engine is None:
            return
        try:
            suppliers = self._supplier_engine.get_active_suppliers()
        except Exception:
            logger.exception("_load_supplier_list failed")
            suppliers = []

        self.cmbSupplier.clear()
        self.cmbSupplier.addItem("-- Select Supplier --", userData=None)
        for sup in suppliers:
            self.cmbSupplier.addItem(
                sup.supplier_name,
                userData=sup.supplier_id,
            )

    def _preselect_supplier(self, supplier_id: int) -> bool:
        """Select `supplier_id` on a blank form (Record Detail Hub -> New
        Payment). Goes through cmbSupplier's normal currentIndexChanged
        chain, exactly as if the user had picked the supplier by hand.
        Returns False (form left blank) if the supplier is not in the
        active-supplier list."""
        index = self.cmbSupplier.findData(supplier_id)
        if index < 0:
            return False
        self.cmbSupplier.setCurrentIndex(index)
        return True

    def _on_supplier_or_amount_changed(self) -> None:
        supplier_id = self.cmbSupplier.currentData()
        amount = self.txtAmount.value()
        if supplier_id and amount > 0:
            self._load_fifo_preview(supplier_id, amount)
        else:
            self.tblAllocations.setRowCount(0)
            self.lblAdvance.setText("")
            self.lblOpeningBalance.setText("")
            self.lblOpeningBalance.setVisible(False)
            self._ob_allocated_preview = 0.0

    # ------------------------------------------------------------------ #
    # FIFO preview
    # ------------------------------------------------------------------ #
    def _load_fifo_preview(self, supplier_id: int, amount: float) -> None:
        # Opening balance is ALWAYS settled first (see PaymentEngine.create_payment()) --
        # this preview must reserve that portion of `amount` before building
        # the invoice-allocation preview, otherwise the grid and the Advance
        # label show numbers that don't match what actually gets saved.
        try:
            ob_outstanding = self._engine.get_opening_balance_outstanding(supplier_id)
        except Exception:
            logger.exception("get_opening_balance_outstanding failed")
            ob_outstanding = 0.0

        self._ob_allocated_preview = round(min(amount, ob_outstanding), 2)
        if self._ob_allocated_preview > 0:
            self.lblOpeningBalance.setText(
                f"Opening Balance Settled: Rs {self._ob_allocated_preview:.2f} "
                f"(of Rs {ob_outstanding:.2f} outstanding)"
            )
            self.lblOpeningBalance.setVisible(True)
        else:
            self.lblOpeningBalance.setText("")
            self.lblOpeningBalance.setVisible(False)

        remaining_for_invoices = round(amount - self._ob_allocated_preview, 2)

        try:
            open_invoices = self._engine.get_outstanding_invoices(supplier_id)
        except Exception:
            logger.exception("get_outstanding_invoices failed")
            return

        remaining = remaining_for_invoices
        allocation_rows = []
        for inv in open_invoices:
            if remaining <= 0:
                break
            alloc_amount = min(remaining, float(inv["outstanding_amount"]))
            allocation_rows.append({
                "purchase_invoice_id": inv["purchase_invoice_id"],
                "invoice_number": inv["invoice_number"],
                "invoice_date_bs": _safe_ad_to_bs(inv["invoice_date_ad"]),
                "outstanding_amount": float(inv["outstanding_amount"]),
                "allocate_amount": round(alloc_amount, 2),
                "checked": True,
            })
            remaining = round(remaining - alloc_amount, 2)

        allocated = round(sum(r["allocate_amount"] for r in allocation_rows), 2)
        advance = round(remaining_for_invoices - allocated, 2)
        self.lblAdvance.setText(f"Advance: Rs {advance:.2f}")

        self._populate_allocation_grid(allocation_rows)

    def _populate_allocation_grid(self, allocation_rows: list[dict]) -> None:
        # BUG FIX: column 3 (allocate amount) is a QSpinBox set via
        # setCellWidget() -- it is a WIDGET, not a QTableWidgetItem. The old
        # code connected `self.tblAllocations.itemChanged`, which only fires
        # for item data changes and can NEVER fire from a user editing this
        # spin box -- so manual allocation edits were silently discarded on
        # Save (Engine always fell back to auto-FIFO instead), and on top of
        # that, the connect() call re-ran once per row every time this
        # method rebuilt the grid, permanently accumulating duplicate
        # connections. Fixed by connecting each spin box's own
        # `valueChanged` signal directly, once, at creation time.
        self.tblAllocations.setRowCount(0)
        for row_data in allocation_rows:
            row = self.tblAllocations.rowCount()
            self.tblAllocations.insertRow(row)

            inv_item = QTableWidgetItem(row_data["invoice_number"])
            inv_item.setData(Qt.ItemDataRole.UserRole, row_data["purchase_invoice_id"])
            self.tblAllocations.setItem(row, 0, inv_item)

            self.tblAllocations.setItem(row, 1, QTableWidgetItem(row_data["invoice_date_bs"]))

            outstanding_item = QTableWidgetItem(f"{row_data['outstanding_amount']:.2f}")
            outstanding_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            self.tblAllocations.setItem(row, 2, outstanding_item)

            alloc_spin = QSpinBox()
            alloc_spin.setRange(0, int(row_data["outstanding_amount"]))
            alloc_spin.setValue(int(row_data["allocate_amount"]))
            alloc_spin.valueChanged.connect(self._on_allocation_row_changed)
            self.tblAllocations.setCellWidget(row, 3, alloc_spin)

            auto_item = QTableWidgetItem()
            auto_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserTristate
            )
            self.tblAllocations.setItem(row, 4, auto_item)

        self._allocation_grid_touched = False

    def _on_allocation_row_changed(self) -> None:
        self._allocation_grid_touched = True
        total_allocated = 0.0
        for row in range(self.tblAllocations.rowCount()):
            alloc_spin = self.tblAllocations.cellWidget(row, 3)
            if alloc_spin:
                total_allocated += float(alloc_spin.value())
        advance = round(self.txtAmount.value() - total_allocated - self._ob_allocated_preview, 2)
        self.lblAdvance.setText(f"Advance: Rs {advance:.2f}")

    # ------------------------------------------------------------------ #
    # Load existing payment (Edit / View mode)
    # ------------------------------------------------------------------ #
    def _load_existing_payment(self) -> None:
        try:
            dto = self._engine.get_by_id(self._payment_id)
        except RecordNotFoundError as exc:
            show_error(str(exc))
            return

        self.cmbSupplier.setCurrentText(dto.supplier_name)
        self._selected_supplier_id = dto.supplier_id

        from PySide6.QtCore import QDate
        ad_value = dto.payment_date_ad
        try:
            qdate = QDate(ad_value.year, ad_value.month, ad_value.day)
            if not qdate.isValid():
                qdate = QDate.currentDate()
        except Exception:
            qdate = QDate.currentDate()
        self.dtPaymentDate.setDate(qdate)

        self.cmbPaymentMode.setCurrentText(dto.payment_mode)
        self.txtAmount.setValue(int(dto.amount))
        self.txtReferenceNo.setText(dto.reference_no or "")
        self.txtBankName.setText(dto.bank_name or "")
        self.txtRemarks.setText(dto.remarks or "")

        self._original_allocations = [
            {
                "purchase_invoice_id": a.purchase_invoice_id,
                "invoice_number": a.internal_ref_number or "",
                "allocated_amount": a.allocated_amount,
            }
            for a in (dto.allocations or [])
        ]

        allocation_rows = [
            {
                "purchase_invoice_id": alloc["purchase_invoice_id"],
                "invoice_number": alloc.get("invoice_number", ""),
                "invoice_date_bs": "",
                "outstanding_amount": float(alloc.get("allocated_amount", 0)),
                "allocate_amount": float(alloc.get("allocated_amount", 0)),
                "checked": True,
            }
            for alloc in self._original_allocations
        ]
        self._populate_allocation_grid(allocation_rows)
        self._allocation_grid_touched = False

        self._original_header = {
            "supplier_id": dto.supplier_id,
            "payment_date_bs": dto.payment_date_bs,
            "payment_mode": dto.payment_mode,
            "amount": dto.amount,
            "reference_no": dto.reference_no,
            "bank_name": dto.bank_name,
            "remarks": dto.remarks,
        }

    def _collect_header_changes(self) -> dict:
        current = {
            "supplier_id": self._selected_supplier_id,
            "payment_date_bs": self._current_payment_date_bs(),
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

    def _collect_allocations(self) -> list[dict]:
        rows = []
        for row in range(self.tblAllocations.rowCount()):
            invoice_item = self.tblAllocations.item(row, 0)
            if invoice_item:
                invoice_id = invoice_item.data(Qt.ItemDataRole.UserRole)
            else:
                continue

            alloc_spin = self.tblAllocations.cellWidget(row, 3)
            if not alloc_spin:
                continue
            allocate_amount = float(alloc_spin.value())
            if allocate_amount <= 0:
                continue

            rows.append({
                "purchase_invoice_id": invoice_id,
                "allocated_amount": allocate_amount,
                "is_auto_allocated": False,
                "remarks": "",
            })
        return rows

    # ------------------------------------------------------------------ #
    # Read-only mode
    # ------------------------------------------------------------------ #
    def _apply_read_only_mode(self) -> None:
        self.cmbSupplier.setEnabled(False)
        self.dtPaymentDate.setEnabled(False)
        self.cmbPaymentMode.setEnabled(False)
        self.txtAmount.setEnabled(False)
        self.txtReferenceNo.setEnabled(False)
        self.txtBankName.setEnabled(False)
        self.txtRemarks.setEnabled(False)
        self.tblAllocations.setEnabled(False)
        self.btnSave.setVisible(False)
        self.btnSave.hide()

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _on_save_clicked(self) -> None:
        if self._read_only:
            return

        supplier_id = self.cmbSupplier.currentData()
        if not supplier_id:
            show_error("Please select a supplier.")
            return

        payment_date_ad = self.dtPaymentDate.date().toPython()

        manual_allocations = (
            self._collect_allocations() if self._allocation_grid_touched else None
        )

        try:
            if self._is_edit_mode:
                header_changes = self._collect_header_changes()
                new_allocations = (
                    self._collect_allocations()
                    if self._allocation_grid_touched
                    else None
                )
                payment_dto = self._engine.edit_payment(
                    payment_id=self._payment_id,
                    updated_by=self._current_user_id,
                    header_changes=header_changes or None,
                    new_allocations=new_allocations,
                )
            else:
                payment_dto = self._engine.create_payment(
                    supplier_id=supplier_id,
                    payment_date_ad=payment_date_ad,
                    payment_mode=self.cmbPaymentMode.currentText(),
                    amount=self.txtAmount.value(),
                    created_by=self._current_user_id,
                    reference_no=self.txtReferenceNo.text().strip() or None,
                    bank_name=self.txtBankName.text().strip() or None,
                    remarks=self.txtRemarks.toPlainText().strip() or None,
                    manual_allocations=manual_allocations,
                )
        except (ValidationError, DuplicateRecordError, RecordNotFoundError) as exc:
            show_error(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception(
                "Unexpected error saving payment (edit_mode=%s)", self._is_edit_mode
            )
            show_error("Could not save this payment. Please try again.")
            return

        show_info(f"Payment {payment_dto.payment_number} saved successfully.")
        self.saved.emit()