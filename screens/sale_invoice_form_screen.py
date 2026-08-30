# screens/sale_invoice_form_screen.py
from __future__ import annotations

import logging
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from engines.customer_engine import get_active_customers
from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_engine import SaleEngine
from screens.purchase_invoice_form_screen import _BsDatePicker, _make_blank_until_typed_spin
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)

COL_ITEM = 0
COL_BATCH = 1
COL_EXPIRY = 2
COL_QTY = 3
COL_FREE_QTY = 4
COL_RATE = 5
COL_DISC = 6
COL_AMOUNT = 7
COLUMN_COUNT = 8
COLUMN_HEADERS = ["Item", "Batch", "Expiry", "Qty", "Free Qty", "Rate", "Disc %", "Amount"]


class SaleInvoiceFormScreen(QDialog):
    """Add-only Sales Invoice. Posted invoices are not edited; corrections
    go through Sale Return. Every Save goes through SaleEngine."""

    def __init__(self, parent, engine: SaleEngine, item_engine, current_user_id: int):
        super().__init__(parent)
        self._engine = engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._all_items, _ = self._item_engine.search_items(page=1, page_size=5000)

        self.setWindowTitle("New Sale")
        self.setMinimumSize(1200, 680)
        self._build_ui()
        self._connect_signals()
        self._populate_customer_combo()
        self._add_line_row()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        left = QFormLayout()
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(260)
        left.addRow("Customer:", self.customer_combo)

        self.payment_mode_combo = QComboBox()
        self.payment_mode_combo.addItems(["Cash", "Credit", "Partial"])
        left.addRow("Payment Mode:", self.payment_mode_combo)
        top.addLayout(left)

        mid = QFormLayout()
        self.invoice_date_input = _BsDatePicker()
        mid.addRow("Invoice Date (BS):", self.invoice_date_input)
        self.paid_amount_input = _make_blank_until_typed_spin(maximum=100_000_000)
        self.paid_amount_input.setEnabled(False)
        mid.addRow("Paid Amount:", self.paid_amount_input)
        top.addLayout(mid)

        top.addStretch()
        buttons = QVBoxLayout()
        self.add_line_button = QPushButton("+ Add Item")
        self.remove_line_button = QPushButton("Remove Selected Row")
        self.list_button = QPushButton("View Sale List")
        buttons.addWidget(self.add_line_button)
        buttons.addWidget(self.remove_line_button)
        buttons.addWidget(self.list_button)
        top.addLayout(buttons)
        root.addLayout(top)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_BATCH, QHeaderView.Stretch)
        self.table.setColumnWidth(COL_EXPIRY, 90)
        self.table.setColumnWidth(COL_QTY, 80)
        self.table.setColumnWidth(COL_FREE_QTY, 80)
        self.table.setColumnWidth(COL_RATE, 90)
        self.table.setColumnWidth(COL_DISC, 70)
        self.table.setColumnWidth(COL_AMOUNT, 100)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, stretch=1)

        charges = QFormLayout()
        self.bill_discount_input = _make_blank_until_typed_spin(maximum=100_000_000)
        charges.addRow("Bill Discount (Amount):", self.bill_discount_input)
        root.addLayout(charges)

        totals = QHBoxLayout()
        totals.addStretch()
        self.round_off_label = QLabel("Round Off: 0.00")
        self.grand_total_label = QLabel("Grand Total: 0.00")
        self.grand_total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        totals.addWidget(self.round_off_label)
        totals.addWidget(self.grand_total_label)
        root.addLayout(totals)

        footer = QHBoxLayout()
        footer.addStretch()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        footer.addWidget(self.save_button)
        footer.addWidget(self.cancel_button)
        root.addLayout(footer)

    def _connect_signals(self) -> None:
        self.add_line_button.clicked.connect(lambda: self._add_line_row())
        self.remove_line_button.clicked.connect(self._on_remove_selected_row)
        self.list_button.clicked.connect(self._on_view_list_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.payment_mode_combo.currentTextChanged.connect(self._on_payment_mode_changed)
        self.bill_discount_input.valueChanged.connect(self._update_grand_total_preview)
        self.paid_amount_input.valueChanged.connect(self._update_grand_total_preview)

    def _populate_customer_combo(self) -> None:
        rows = get_active_customers()
        items = [
            SimpleNamespace(
                customer_name=f"{r['customer_code']} — {r['customer_name']}",
                customer_id=r["customer_id"],
            )
            for r in rows
        ]
        populate_searchable_combo(
            self.customer_combo,
            items=items,
            display_attr="customer_name",
            data_attr="customer_id",
            placeholder="Select customer...",
        )

    def _on_payment_mode_changed(self, mode: str) -> None:
        self.paid_amount_input.setEnabled(mode == "Partial")
        if mode != "Partial":
            self.paid_amount_input.setValue(0)
        self._update_grand_total_preview()

    def _add_line_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_combo = QComboBox()
        populate_searchable_combo(
            item_combo,
            items=self._all_items,
            display_attr="item_name",
            data_attr="item_id",
            placeholder="Select item...",
        )
        item_combo.currentIndexChanged.connect(lambda _i, r=row: self._on_item_changed(r))
        self.table.setCellWidget(row, COL_ITEM, item_combo)

        batch_combo = QComboBox()
        batch_combo.currentIndexChanged.connect(lambda _i, r=row: self._on_batch_changed(r))
        self.table.setCellWidget(row, COL_BATCH, batch_combo)

        expiry_label = QLabel("")
        expiry_label.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, COL_EXPIRY, expiry_label)

        qty = _make_blank_until_typed_spin()
        qty.valueChanged.connect(lambda _v, r=row: self._recalculate_row(r))
        self.table.setCellWidget(row, COL_QTY, qty)

        free_qty = _make_blank_until_typed_spin()
        free_qty.valueChanged.connect(lambda _v, r=row: self._recalculate_row(r))
        self.table.setCellWidget(row, COL_FREE_QTY, free_qty)

        rate = _make_blank_until_typed_spin()
        rate.valueChanged.connect(lambda _v, r=row: self._recalculate_row(r))
        self.table.setCellWidget(row, COL_RATE, rate)

        disc = _make_blank_until_typed_spin()
        disc.setMaximum(100)
        disc.valueChanged.connect(lambda _v, r=row: self._recalculate_row(r))
        self.table.setCellWidget(row, COL_DISC, disc)

        amount = _make_blank_until_typed_spin()
        amount.setReadOnly(True)
        self.table.setCellWidget(row, COL_AMOUNT, amount)

    def _on_item_changed(self, row: int) -> None:
        item_combo = self.table.cellWidget(row, COL_ITEM)
        item_id = item_combo.currentData() if item_combo else None
        batch_combo = self.table.cellWidget(row, COL_BATCH)
        batch_combo.blockSignals(True)
        batch_combo.clear()
        batch_combo.addItem("Select batch...", None)

        if item_id:
            try:
                batches = self._item_engine.get_available_batches(item_id)
            except Exception:
                logger.exception("Failed to load batches for item %s", item_id)
                batches = []
            for batch in batches:
                label = (
                    f"{batch.batch_no}  {batch.expiry_display}  "
                    f"(qty {float(batch.batch_qty):.2f})"
                )
                batch_combo.addItem(label, batch.item_batch_id)

            item = next((i for i in self._all_items if i.item_id == item_id), None)
            if item is not None:
                self.table.cellWidget(row, COL_RATE).setValue(float(item.sale_rate or 0))

        batch_combo.blockSignals(False)
        self._on_batch_changed(row)

    def _on_batch_changed(self, row: int) -> None:
        batch_combo = self.table.cellWidget(row, COL_BATCH)
        item_batch_id = batch_combo.currentData() if batch_combo else None
        expiry_label = self.table.cellWidget(row, COL_EXPIRY)
        if not item_batch_id:
            expiry_label.setText("")
            return
        try:
            batch = self._item_engine.get_batch(item_batch_id)
            expiry_label.setText(batch.expiry_display)
        except RecordNotFoundError:
            expiry_label.setText("")
        self._recalculate_row(row)

    def _recalculate_row(self, row: int) -> None:
        qty = self.table.cellWidget(row, COL_QTY).value()
        rate = self.table.cellWidget(row, COL_RATE).value()
        disc = self.table.cellWidget(row, COL_DISC).value()
        amount = qty * rate * (1 - disc / 100.0)
        amount_widget = self.table.cellWidget(row, COL_AMOUNT)
        amount_widget.blockSignals(True)
        amount_widget.setValue(round(amount, 2))
        amount_widget.blockSignals(False)
        self._update_grand_total_preview()

    def _update_grand_total_preview(self) -> None:
        raw_total = 0.0
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, COL_AMOUNT)
            if widget is not None:
                raw_total += widget.value()
        after = raw_total - self.bill_discount_input.value()
        rounded = round(after)
        round_off = round(rounded - after, 2)
        self.round_off_label.setText(f"Round Off: {round_off:.2f}")
        self.grand_total_label.setText(f"Grand Total: {rounded:.2f}")

    def _on_remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_grand_total_preview()

    def _on_view_list_clicked(self) -> None:
        from screens.sale_invoice_list_screen import SaleInvoiceListScreen

        dialog = SaleInvoiceListScreen(
            parent=self,
            engine=self._engine,
            item_engine=self._item_engine,
            current_user_id=self._current_user_id,
        )
        dialog.setWindowFlag(Qt.Window)
        dialog.show()

    def _collect_form_values(self) -> dict:
        lines = []
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, COL_ITEM)
            batch_combo = self.table.cellWidget(row, COL_BATCH)
            lines.append(
                {
                    "item_id": item_combo.currentData() if item_combo else None,
                    "item_batch_id": batch_combo.currentData() if batch_combo else None,
                    "qty": self.table.cellWidget(row, COL_QTY).value(),
                    "free_qty": self.table.cellWidget(row, COL_FREE_QTY).value(),
                    "rate": self.table.cellWidget(row, COL_RATE).value(),
                    "discount_percent": self.table.cellWidget(row, COL_DISC).value(),
                }
            )
        return {
            "customer_id": self.customer_combo.currentData(),
            "invoice_date_bs": self.invoice_date_input.get_bs_date_string(),
            "payment_mode": self.payment_mode_combo.currentText(),
            "paid_amount": self.paid_amount_input.value(),
            "bill_discount_amount": self.bill_discount_input.value(),
            "lines": lines,
        }

    def _on_save_clicked(self) -> None:
        payload = self._collect_form_values()
        try:
            invoice = self._engine.create_sale_invoice(payload, self._current_user_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot Save", str(exc))
            return
        except RecordNotFoundError as exc:
            QMessageBox.warning(self, "Cannot Save", str(exc))
            return
        except Exception:
            logger.exception("Failed to create sale invoice")
            QMessageBox.critical(self, "Error", "Could not save the sale invoice. Please try again.")
            return

        QMessageBox.information(
            self,
            "Saved",
            f"Sale invoice {invoice.invoice_number} saved.\nGrand Total: {invoice.grand_total:.2f}",
        )
        self.accept()
