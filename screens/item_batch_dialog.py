"""
screens/item_batch_dialog.py

Item Batch Entry Dialog - Medical ERP V2

Built as plain Python widgets (no .ui/Designer file) since every value on
this dialog is a handful of simple fields for one batch entry -- same
reasoning already used for screens/language_dialog.py ("small,
single-purpose dialog").

Responsibilities (Screen/Controller layer -- "No SQL. No business logic."):
    - Collect Batch No., Expiry Month/Year, Quantity, Purchase Rate, Remarks
    - Hand the payload to ItemEngine.add_batch() via utils/item_form_helpers.py
    - Surface whatever the Engine/Validator decide back to the user
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from utils.integration_adapters import get_current_user_id, show_success
from utils.item_form_helpers import build_batch_payload

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "01 - January", "02 - February", "03 - March", "04 - April",
    "05 - May", "06 - June", "07 - July", "08 - August",
    "09 - September", "10 - October", "11 - November", "12 - December",
]


class ItemBatchDialog(QDialog):
    """Add a single batch (quantity + AD month/year expiry) for one item."""

    def __init__(self, parent: Optional[QWidget], item_engine, item_id: int, item_name: str) -> None:
        super().__init__(parent)
        self._engine = item_engine
        self._item_id = item_id

        self.setWindowTitle(f"Add Batch — {item_name}")
        self.setMinimumWidth(380)
        self._build_ui(item_name)
        self._connect_signals()

    # ------------------------------------------------------------------ #
    def _build_ui(self, item_name: str) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(f"New batch for: {item_name}")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()

        self.txtBatchNo = QLineEdit()
        self.txtBatchNo.setPlaceholderText("e.g. B-2027-045")
        form.addRow("Batch No. *", self.txtBatchNo)

        from PySide6.QtCore import QDate
        current_year = QDate.currentDate().year()

        self.cmbExpiryMonth = QComboBox()
        self.cmbExpiryMonth.addItems(MONTH_NAMES)
        form.addRow("Expiry Month *", self.cmbExpiryMonth)

        self.txtExpiryYear = QLineEdit(str(current_year + 1))
        form.addRow("Expiry Year (AD) *", self.txtExpiryYear)

        self.txtBatchQty = QLineEdit("0")
        form.addRow("Quantity *", self.txtBatchQty)

        self.txtBatchPurchaseRate = QLineEdit("0.00")
        form.addRow("Purchase Rate (this batch)", self.txtBatchPurchaseRate)

        self.txtRemarks = QPlainTextEdit()
        self.txtRemarks.setMaximumHeight(60)
        form.addRow("Remarks", self.txtRemarks)

        layout.addLayout(form)

        self.lblValidationMessage = QLabel("")
        self.lblValidationMessage.setStyleSheet("color: #c0392b;")
        self.lblValidationMessage.setWordWrap(True)
        layout.addWidget(self.lblValidationMessage)

        button_row = QHBoxLayout()
        button_row.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btnSave = QPushButton("Save Batch")
        self.btnSave.setDefault(True)
        self.btnCancel = QPushButton("Cancel")
        button_row.addWidget(self.btnSave)
        button_row.addWidget(self.btnCancel)
        layout.addLayout(button_row)

    def _connect_signals(self) -> None:
        self.btnSave.clicked.connect(self._on_save_clicked)
        self.btnCancel.clicked.connect(self.reject)

    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        return {
            "batch_no": self.txtBatchNo.text(),
            "expiry_month_text": str(self.cmbExpiryMonth.currentIndex() + 1),
            "expiry_year_text": self.txtExpiryYear.text(),
            "batch_qty_text": self.txtBatchQty.text(),
            "batch_purchase_rate_text": self.txtBatchPurchaseRate.text(),
            "remarks": self.txtRemarks.toPlainText(),
        }

    def _on_save_clicked(self) -> None:
        self.lblValidationMessage.setText("")

        try:
            payload = build_batch_payload(self._collect_form_values())
        except ValueError as exc:
            self.lblValidationMessage.setText(str(exc))
            return

        current_user_id = get_current_user_id()

        try:
            dto = self._engine.add_batch(self._item_id, payload, current_user_id)
        except ValidationError as exc:
            self.lblValidationMessage.setText("\n".join(exc.errors))
            return
        except DuplicateRecordError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except RecordNotFoundError as exc:
            self.lblValidationMessage.setText(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error saving item batch.")
            self.lblValidationMessage.setText(f"Unexpected error: {exc}")
            return

        show_success(self, "Item Batch", f"Batch '{dto.batch_no}' added ({dto.expiry_display}).")
        self.accept()


__all__ = ["ItemBatchDialog"]
