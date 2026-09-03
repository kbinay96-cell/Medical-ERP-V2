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

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.sale_engine import EngineErrorWithInvoice, SaleEngine
from models.customer_model import get_active_customers_by_area, get_areas
from screens.purchase_invoice_form_screen import _BsDatePicker, _make_blank_until_typed_spin
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)

# Column indices (physical grid columns; visibility is per-setting).
COL_ITEM = 0
COL_BATCH = 1
COL_EXPIRY = 2
COL_QTY = 3
COL_FREE_QTY = 4
COL_RATE = 5
COL_MRP = 6
COL_DISC = 7
COL_TAX = 8
COL_AMOUNT = 9
COLUMN_COUNT = 10
COLUMN_HEADERS = [
    "Item", "Batch", "Expiry", "Qty", "Free Qty",
    "Rate", "MRP", "Disc %", "Tax %", "Amount",
]

COLUMN_SETTINGS = {
    "batch":  (COL_BATCH, "Batch"),
    "expiry": (COL_EXPIRY, "Expiry"),
    "free":   (COL_FREE_QTY, "Free Qty"),
    "mrp":    (COL_MRP, "MRP"),
    "discount_percent": (COL_DISC, "Disc %"),
    "tax":    (COL_TAX, "Tax %"),
}

ALWAYS_VISIBLE_COLUMNS = {COL_ITEM, COL_QTY, COL_RATE, COL_AMOUNT}


class SaleInvoiceFormScreen(QDialog):
    """Add-only Sales Invoice (blueprint Phase-1 core screen)."""

    def __init__(
        self,
        parent,
        engine: SaleEngine,
        item_engine,
        item_free_scheme_engine,
        customer_engine=None,
        current_user_id: int = 1,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._customer_engine = customer_engine
        self._current_user_id = current_user_id
        self._all_items, _ = self._item_engine.search_items(page=1, page_size=5000)

        self.setWindowTitle("New Sale")
        self.setMinimumSize(1300, 700)
        self._build_ui()
        self._connect_signals()
        self._populate_area_combo()
        self._add_empty_row()
# ================================================================== #
    # UI CONSTRUCTION
    # ================================================================== #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        left = QFormLayout()

        self.area_combo = QComboBox()
        self.area_combo.setMinimumWidth(180)
        left.addRow("Area:", self.area_combo)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(260)
        left.addRow("Customer:", self.customer_combo)

        self.price_level_label = QLabel("-")
        left.addRow("Price Level:", self.price_level_label)

        self.credit_limit_label = QLabel("-")
        left.addRow("Credit Limit:", self.credit_limit_label)
        top.addLayout(left)

        mid = QFormLayout()
        self.invoice_date_input = _BsDatePicker()
        mid.addRow("Invoice Date (BS):", self.invoice_date_input)

        self.payment_type_combo = QComboBox()
        self.payment_type_combo.addItems(["Cash", "Bank", "eSewa", "Khalti", "IPS"])
        mid.addRow("Payment Type:", self.payment_type_combo)

        self.amount_paid_input = _make_blank_until_typed_spin(maximum=100_000_000)
        mid.addRow("Amount Paid:", self.amount_paid_input)

        self.sale_mode_label = QLabel("Mode: Retail")
        self.sale_mode_label.setStyleSheet("font-weight: bold;")
        mid.addRow(self.sale_mode_label)
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
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self._apply_column_visibility()
        root.addWidget(self.table, stretch=1)

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
        self.area_combo.currentIndexChanged.connect(self._on_area_changed)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_changed)
        self.add_line_button.clicked.connect(lambda: self._add_empty_row())
        self.remove_line_button.clicked.connect(self._on_remove_selected_row)
        self.list_button.clicked.connect(self._on_view_list_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.amount_paid_input.valueChanged.connect(self._update_grand_total_preview)

    # ================================================================== #
    # SETTINGS-DRIVEN COLUMN VISIBILITY
    # ================================================================== #
    def _build_visible_columns(self) -> list[tuple[int, str]]:
        """Returns ordered list of (column_index, header) that should be
        visible, per settings. Item, Qty, Rate, Amount are always shown."""
        from engines.settings_engine import get_setting

        visible: list[tuple[int, str]] = []
        visible.append((COL_ITEM, "Item"))
        visible.append((COL_QTY, "Qty"))
        visible.append((COL_RATE, "Rate"))
        visible.append((COL_AMOUNT, "Amount"))

        for key, (idx, header) in COLUMN_SETTINGS.items():
            if bool(get_setting(f"sale.column_show_{key}", False)):
                visible.append((idx, header))

        return visible

    def _apply_column_visibility(self) -> None:
        """Hides every column not in the visible set â€” single source of truth
        for what prints later (the future print routine iterates this same set)."""
        visible_indices = {idx for idx, _ in self._build_visible_columns()}
        for idx in range(COLUMN_COUNT):
            if idx in ALWAYS_VISIBLE_COLUMNS or idx in visible_indices:
                self.table.setColumnHidden(idx, False)
            else:
                self.table.setColumnHidden(idx, True)
# ================================================================== #
    # HEADER COMBO CASCADE
    # ================================================================== #
    def _populate_area_combo(self) -> None:
        areas = get_areas(active_only=True)
        items = [
            SimpleNamespace(area_name=r["area_name"], area_id=r["area_id"])
            for r in areas
        ]
        populate_searchable_combo(
            self.area_combo,
            items=items,
            display_attr="area_name",
            data_attr="area_id",
            placeholder="Select area...",
        )

    def _on_area_changed(self, _index: int) -> None:
        area_id = self.area_combo.currentData()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        rows = get_active_customers_by_area(int(area_id)) if area_id else []
        items = [
            SimpleNamespace(
                customer_name=f"{r['customer_code']} â€” {r['customer_name']}",
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
        self.customer_combo.blockSignals(False)

    def _on_customer_changed(self, _index: int) -> None:
        customer_id = self.customer_combo.currentData()
        if not customer_id:
            self.price_level_label.setText("-")
            self.credit_limit_label.setText("-")
            return
        try:
            from engines.customer_engine import get_customer
            customer = get_customer(int(customer_id))
            if customer is None and self._customer_engine is not None:
                customer = self._customer_engine.get_customer(int(customer_id))
        except Exception:
            logger.exception("Could not load customer %s detail", customer_id)
            customer = None
        if customer:
            self.price_level_label.setText(str(customer.get("price_level_id") or "-"))
            self.credit_limit_label.setText(f"{float(customer.get('credit_limit') or 0):.2f}")
        else:
            self.price_level_label.setText("-")
            self.credit_limit_label.setText("-")

    # ================================================================== #
    # GRID â€” ROW BUILD + INLINE ITEM COMBO
    # ================================================================== #
    def _add_empty_row(self) -> None:
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
        item_combo.currentIndexChanged.connect(lambda _i, r=row: self._on_row_item_selected(r))
        self.table.setCellWidget(row, COL_ITEM, item_combo)

        batch_label = QLabel("")
        batch_label.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, COL_BATCH, batch_label)

        expiry_label = QLabel("")
        expiry_label.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, COL_EXPIRY, expiry_label)

        qty = _make_blank_until_typed_spin()
        qty.valueChanged.connect(lambda _v, r=row: self._on_row_qty_changed(r))
        self.table.setCellWidget(row, COL_QTY, qty)

        free_qty = _make_blank_until_typed_spin()
        free_qty.setEnabled(False)  # shown/auto-filled only in Wholesale
        free_qty.valueChanged.connect(lambda _v, r=row: self._on_row_qty_changed(r))
        self.table.setCellWidget(row, COL_FREE_QTY, free_qty)

        rate = _make_blank_until_typed_spin()
        rate.valueChanged.connect(lambda _v, r=row: self._on_row_qty_changed(r))
        self.table.setCellWidget(row, COL_RATE, rate)

        mrp_label = QLabel("")
        mrp_label.setAlignment(Qt.AlignRight)
        self.table.setCellWidget(row, COL_MRP, mrp_label)

        disc = _make_blank_until_typed_spin()
        disc.setMaximum(100)
        disc.valueChanged.connect(lambda _v, r=row: self._on_row_qty_changed(r))
        self.table.setCellWidget(row, COL_DISC, disc)

        tax_label = QLabel("")
        tax_label.setAlignment(Qt.AlignRight)
        self.table.setCellWidget(row, COL_TAX, tax_label)

        amount = _make_blank_until_typed_spin()
        amount.setReadOnly(True)
        self.table.setCellWidget(row, COL_AMOUNT, amount)

        if not hasattr(self, "_row_entry_modes"):
            self._row_entry_modes = {}
        mode_combo = QComboBox()
        mode_combo.addItem("Free Qty", "free_qty")
        mode_combo.addItem("Net Rate", "net_rate")
        mode_combo.currentIndexChanged.connect(lambda _i, r=row: self._on_row_entry_mode_toggled(r))
        self._row_entry_modes[row] = mode_combo
# ------------------------------------------------------------------ #
    def _on_row_item_selected(self, row: int) -> None:
        item_combo = self.table.cellWidget(row, COL_ITEM)
        item_id = item_combo.currentData() if item_combo else None
        if not item_id:
            return

        qty_widget = self.table.cellWidget(row, COL_QTY)
        qty = float(qty_widget.value() or 0)
        entry_mode = "free_qty"
        if hasattr(self, "_row_entry_modes") and row in self._row_entry_modes:
            entry_mode = self._row_entry_modes[row].currentData()

        preview_input: dict = {
            "item_id": int(item_id),
            "qty": qty if qty > 0 else 1,
            "entry_mode": entry_mode,
        }
        try:
            is_wholesale = self._engine.is_wholesale_mode()
            line = self._engine.compute_line(preview_input, is_wholesale)
        except Exception:
            logger.exception("compute_line preview failed for row %s item %s", row, item_id)
            QMessageBox.warning(self, "Item Issue", "Could not resolve this item for sale (no stock or invalid).")
            return

        batch_label = self.table.cellWidget(row, COL_BATCH)
        if batch_label and line.get("batch_no"):
            batch_label.setText(str(line["batch_no"]))

        expiry_label = self.table.cellWidget(row, COL_EXPIRY)
        if expiry_label and line.get("expiry_year"):
            expiry_label.setText(f"{line['expiry_year']}-{int(line['expiry_month']):02d}")

        rate_widget = self.table.cellWidget(row, COL_RATE)
        if rate_widget:
            rate_widget.setValue(float(line["rate"]))

        mrp_label = self.table.cellWidget(row, COL_MRP)
        if mrp_label:
            try:
                item_obj = next((i for i in self._all_items if i.item_id == int(item_id)), None)
                mrp = float(getattr(item_obj, "mrp", 0) or 0) if item_obj else 0
            except Exception:
                mrp = 0
            mrp_label.setText(f"{mrp:.2f}")

        if is_wholesale and line.get("free_qty") is not None:
            free_widget = self.table.cellWidget(row, COL_FREE_QTY)
            if free_widget:
                free_widget.setEnabled(True)
                free_widget.setValue(float(line["free_qty"]))

        self._on_row_qty_changed(row)

        # Excel-style continuous entry: selecting item in the LAST row appends a new row.
        if row == self.table.rowCount() - 1:
            self._add_empty_row()

    # ------------------------------------------------------------------ #
    def _on_row_entry_mode_toggled(self, row: int) -> None:
        # Re-run the preview so Free/Rate refresh for the new mode.
        self._on_row_qty_changed(row)

    # ------------------------------------------------------------------ #
    def _on_row_qty_changed(self, row: int) -> None:
        item_combo = self.table.cellWidget(row, COL_ITEM)
        item_id = item_combo.currentData() if item_combo else None
        qty_widget = self.table.cellWidget(row, COL_QTY)
        qty = float(qty_widget.value() or 0)
        rate_widget = self.table.cellWidget(row, COL_RATE)
        rate = float(rate_widget.value() or 0) if rate_widget else 0
        disc_widget = self.table.cellWidget(row, COL_DISC)
        disc = float(disc_widget.value() or 0) if disc_widget else 0

        amount_widget = self.table.cellWidget(row, COL_AMOUNT)
        if not amount_widget:
            return

        if not item_id or qty <= 0:
            amount_widget.setValue(0)
            self._update_grand_total_preview()
            return

        try:
            entry_mode = "free_qty"
            if hasattr(self, "_row_entry_modes") and row in self._row_entry_modes:
                entry_mode = self._row_entry_modes[row].currentData()
            free_widget = self.table.cellWidget(row, COL_FREE_QTY)
            free_val = float(free_widget.value() or 0) if free_widget else 0
            is_wholesale = self._engine.is_wholesale_mode()
            line = self._engine.compute_line(
                {
                    "item_id": int(item_id),
                    "qty": qty,
                    "rate": rate if rate > 0 else None,
                    "discount_percent": disc,
                    "free_qty": free_val,
                    "entry_mode": entry_mode,
                },
                is_wholesale,
            )
        except Exception:
            logger.exception("compute_line re-preview failed for row %s", row)
            amount_widget.setValue(0)
            self._update_grand_total_preview()
            return

        if rate_widget and float(line["rate"]) != rate and rate == 0:
            rate_widget.setValue(float(line["rate"]))

        if free_widget is not None and line.get("free_qty") is not None:
            free_widget.blockSignals(True)
            free_widget.setValue(float(line["free_qty"]))
            free_widget.blockSignals(False)

        tax_label = self.table.cellWidget(row, COL_TAX)
        if tax_label:
            tax_label.setText(f"{float(line['tax_percent'] or 0):.2f}")

        amount_widget.setValue(round(float(line["amount"]), 2))
        self._update_grand_total_preview()
# ------------------------------------------------------------------ #
    def _update_grand_total_preview(self) -> None:
        raw_total = 0.0
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, COL_AMOUNT)
            if widget is not None:
                raw_total += widget.value()
        rounded = round(raw_total)
        round_off = round(rounded - raw_total, 2)
        self.round_off_label.setText(f"Round Off: {round_off:.2f}")
        self.grand_total_label.setText(f"Grand Total: {rounded:.2f}")

    # ------------------------------------------------------------------ #
    def _on_remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            if hasattr(self, "_row_entry_modes"):
                self._row_entry_modes.pop(row, None)
            self._update_grand_total_preview()

    # ------------------------------------------------------------------ #
    def _on_view_list_clicked(self) -> None:
        from screens.sale_invoice_list_screen import SaleInvoiceListScreen

        dialog = SaleInvoiceListScreen(
            parent=self,
            engine=self._engine,
            item_engine=self._item_engine,
            item_free_scheme_engine=self._item_free_scheme_engine,
            current_user_id=self._current_user_id,
        )
        dialog.setWindowFlag(Qt.Window)
        dialog.show()

    # ================================================================== #
    # SAVE
    # ================================================================== #
    def _collect_form_values(self) -> dict:
        lines = []
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, COL_ITEM)
            item_id = item_combo.currentData() if item_combo else None
            if not item_id:
                continue  # only rows with an item selected are sent

            qty_widget = self.table.cellWidget(row, COL_QTY)
            qty = float(qty_widget.value() or 0)
            free_widget = self.table.cellWidget(row, COL_FREE_QTY)
            free_qty = float(free_widget.value() or 0) if free_widget else 0

            if qty <= 0 and free_qty <= 0:
                continue  # skip effectively-empty rows

            rate_widget = self.table.cellWidget(row, COL_RATE)
            rate = float(rate_widget.value() or 0) if rate_widget else 0
            disc_widget = self.table.cellWidget(row, COL_DISC)
            disc = float(disc_widget.value() or 0) if disc_widget else 0

            entry_mode = "free_qty"
            if hasattr(self, "_row_entry_modes") and row in self._row_entry_modes:
                entry_mode = self._row_entry_modes[row].currentData()

            lines.append({
                "item_id": int(item_id),
                "qty": qty,
                "free_qty": free_qty,
                "rate": rate,
                "discount_percent": disc,
                "entry_mode": entry_mode,
            })

        return {
            "customer_id": self.customer_combo.currentData(),
            "area_id": self.area_combo.currentData(),
            "invoice_date_bs": self.invoice_date_input.get_bs_date_string(),
            "payment_type": self.payment_type_combo.currentText(),
            "amount_paid_now": self.amount_paid_input.value(),
            "lines": lines,
        }

    # ------------------------------------------------------------------ #
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
        except EngineErrorWithInvoice as exc:
            # Distinct partial-success: invoice saved but some stock lines failed.
            lines_text = "\n".join(f"  - {e}" for e in exc.stock_errors)
            QMessageBox.warning(
                self,
                "Saved with Stock Issues",
                f"Invoice {exc.dto.invoice_number} was created, but stock could "
                f"not be reduced for:\n{lines_text}\n\n"
                f"Grand Total: {exc.dto.grand_total:.2f}",
            )
            self.accept()
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
