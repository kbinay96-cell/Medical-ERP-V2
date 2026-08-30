# screens/purchase_invoice_form_screen.py
from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from engines.exceptions import DuplicateRecordError, ValidationError
from engines.purchase_engine import PurchaseEngine
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.item_lookup_registry import manufacturer_engine
from engines import settings_engine
from utils.searchable_combo_helper import populate_searchable_combo

logger = logging.getLogger(__name__)

# line-item grid columns (CC% / Landing Cost / row-remove-button columns
# removed from display per user request — CC%/landing cost are still
# computed internally for the grand-total preview, just not shown as
# columns; row removal now uses a "Remove Selected Row" button above the
# table instead of a per-row button column.)
COL_ITEM = 0
COL_BATCH_NO = 1
COL_EXPIRY = 2
COL_QTY = 3
COL_FREE_QTY = 4
COL_AMOUNT = 5
COL_CURRENT_STOCK = 6   # read-only, live stock at time of item selection
COL_PURCHASE_RATE = 7   # read-only, derived = amount / qty
COL_DISCOUNT_PCT = 8    # auto-filled from Supplier-Mfg Discount, editable
COL_SUPER_DISCOUNT_PCT = 9  # manual, per-purchase extra/scheme discount, editable
COL_MRP = 10
COL_SALE_RATE = 11
COLUMN_COUNT = 12

COLUMN_HEADERS = [
    "Item", "Batch No", "Expiry", "Qty", "Free Qty", "Amount",
    "Current Stock", "Purchase Rate", "Disc %", "Super Disc %", "MRP", "Sale Rate",
]


class _BsDatePicker(QWidget):
    """Minimal BS (Bikram Sambat) date entry — three plain number boxes
    (Year-Month-Day) rather than a calendar popup, since no BS-calendar
    widget exists anywhere in this project yet and BS month lengths vary
    by year (no safe day-range table to validate against here). Promote
    this to its own shared widgets file later if other modules need a
    BS date picker too."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2070, 2150)
        self.year_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 32)
        self.day_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)

        layout.addWidget(self.year_spin)
        layout.addWidget(QLabel("-"))
        layout.addWidget(self.month_spin)
        layout.addWidget(QLabel("-"))
        layout.addWidget(self.day_spin)

        # Best-effort default to today's BS date — never blocks the
        # widget from working if the Date Engine isn't reachable.
        try:
            from engines.date_engine import ad_to_bs
            self.set_bs_date_string(ad_to_bs(date.today()))
        except Exception:
            logger.warning("Could not default BS date picker to today's date.")

    def set_bs_date_string(self, bs_date_str: str) -> None:
        try:
            y, m, d = bs_date_str.split("-")
            self.year_spin.setValue(int(y))
            self.month_spin.setValue(int(m))
            self.day_spin.setValue(int(d))
        except Exception:
            pass

    def get_bs_date_string(self) -> str:
        return f"{self.year_spin.value():04d}-{self.month_spin.value():02d}-{self.day_spin.value():02d}"


def _make_blank_until_typed_spin(decimals: int = 2, maximum: float = 10_000_000) -> QDoubleSpinBox:
    """A QDoubleSpinBox that shows BLANK instead of '0.00' until a value
    is actually entered, and hides the up/down arrow buttons so it reads
    as a plain flat input box, not a spinner."""
    spin = QDoubleSpinBox()
    spin.setRange(0, maximum)
    spin.setDecimals(decimals)
    spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
    spin.setSpecialValueText(" ")  # shown only when value == minimum (0)
    return spin


class PurchaseInvoiceFormScreen(QDialog):
    """Add-only screen (Purchase Invoices are not edited after posting —
    corrections go through Purchase Return). No SQL, no business logic —
    every Save goes through PurchaseEngine.create_purchase_invoice(); CC%
    and Landing Cost are still computed live via the Engine's own helpers
    for the Grand Total preview, they're just not shown as their own
    columns anymore.

    Entry model (confirmed): user types Qty, Free Qty (auto-suggested
    from the item+supplier's last-used scheme, e.g. "10+1", but always
    editable) and Item Amount (the gross paid-qty amount, before
    discount%). Purchase Rate is derived (Amount / Qty), never typed
    directly. Discount % auto-fills from
    SupplierManufacturerDiscountEngine.get_discount() via the item's
    manufacturer, but stays editable per line. Every field in a row
    except the Item combo starts disabled/blank and only becomes
    editable once an item is actually selected for that row."""

    def __init__(
        self,
        parent,
        engine: PurchaseEngine,
        purchase_order_engine,
        supplier_engine,
        item_engine,
        current_user_id: int,
        item_free_scheme_engine: ItemFreeSchemeEngine | None = None,
    ):
        super().__init__(parent)
        self._engine = engine
        self._purchase_order_engine = purchase_order_engine
        self._supplier_engine = supplier_engine
        self._item_engine = item_engine
        self._current_user_id = current_user_id
        self._scheme_engine = item_free_scheme_engine or ItemFreeSchemeEngine()
        self._linked_purchase_order_id: int | None = None
        self._attached_bill_path: str | None = None
        self._row_landing_costs: dict[int, float] = {}
        self._row_pricing_meta: dict[int, tuple[float, float]] = {}
        self._row_last_item_id: dict[int, int] = {}

        # Cached once — reused to populate every row's item combo without
        # re-querying the DB per row. NOTE: assumes ItemEngine.search_items()
        # follows the same (page, page_size) -> (rows, total_count) shape as
        # every other search_x() in this codebase — please confirm/correct
        # if ItemEngine's real signature differs.
        self._all_items, _ = self._item_engine.search_items(page=1, page_size=5000)

        self.setWindowTitle("New Purchase Invoice")
        self.setMinimumSize(1300, 720)

        self._build_ui()
        self._connect_signals()
        self._populate_supplier_combo()

    # -- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ---- Header: two field-groups on the left, 3 stacked buttons on the right ----
        top_row = QHBoxLayout()

        left_form = QFormLayout()
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(240)
        left_form.addRow("Supplier:", self.supplier_combo)

        self.invoice_number_input = QLineEdit()
        left_form.addRow("Invoice Number:", self.invoice_number_input)
        top_row.addLayout(left_form)

        mid_form = QFormLayout()
        self.invoice_date_input = _BsDatePicker()
        mid_form.addRow("Invoice Date (BS):", self.invoice_date_input)

        self.link_po_combo = QComboBox()
        self.link_po_combo.setMinimumWidth(200)
        self.link_po_combo.addItem("(No linked Purchase Order)", None)
        self.link_po_combo.setToolTip(
            "Optional. If you already sent this supplier a Purchase Order, "
            "link it here to auto-fill this invoice's items from that order. "
            "Leave as '(No linked Purchase Order)' for a direct purchase."
        )
        mid_form.addRow("Link to Purchase Order:", self.link_po_combo)
        top_row.addLayout(mid_form)

        top_row.addStretch()

        button_col = QVBoxLayout()
        self.add_line_button = QPushButton("+ Add Item")
        button_col.addWidget(self.add_line_button)

        self.attach_bill_button = QPushButton("📎 Attach Bill (optional)")
        button_col.addWidget(self.attach_bill_button)
        self.attach_bill_label = QLabel("No file attached")
        self.attach_bill_label.setStyleSheet("color: gray; font-size: 11px;")
        button_col.addWidget(self.attach_bill_label)

        self.purchase_list_button = QPushButton("View Purchase List")
        button_col.addWidget(self.purchase_list_button)
        top_row.addLayout(button_col)

        root.addLayout(top_row)

        # ---- Row-level actions above the table ----
        table_action_row = QHBoxLayout()
        self.remove_line_button = QPushButton("Remove Selected Row")
        table_action_row.addWidget(self.remove_line_button)
        table_action_row.addStretch()
        root.addLayout(table_action_row)

        # ---- Line-item grid ----
        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)
        self.table.setColumnWidth(COL_BATCH_NO, 110)
        self.table.setColumnWidth(COL_EXPIRY, 130)
        self.table.setColumnWidth(COL_QTY, 70)
        self.table.setColumnWidth(COL_FREE_QTY, 70)
        self.table.setColumnWidth(COL_AMOUNT, 100)
        self.table.setColumnWidth(COL_CURRENT_STOCK, 90)
        self.table.setColumnWidth(COL_PURCHASE_RATE, 100)
        self.table.setColumnWidth(COL_DISCOUNT_PCT, 70)
        self.table.setColumnWidth(COL_SUPER_DISCOUNT_PCT, 90)
        self.table.setColumnWidth(COL_MRP, 90)
        self.table.setColumnWidth(COL_SALE_RATE, 90)
        self.table.setColumnHidden(COL_SALE_RATE, not self._is_wholesaler())
        self.table.verticalHeader().setDefaultSectionSize(34)  # room so the
        # expiry date picker (and every other row widget) never gets clipped
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, stretch=1)  # table takes all extra vertical space

        # ---- invoice-level charges + discount + round-off ----
        charges_form = QFormLayout()
        self.freight_input = _make_blank_until_typed_spin()
        charges_form.addRow("Freight Amount:", self.freight_input)

        self.other_charges_input = _make_blank_until_typed_spin()
        charges_form.addRow("Other Charges:", self.other_charges_input)

        self.bill_discount_input = _make_blank_until_typed_spin(maximum=100_000_000)
        self.bill_discount_input.setToolTip(
            "Use this when the supplier discounts the WHOLE bill directly, "
            "instead of item-by-item. Subtracted straight from the grand total."
        )
        charges_form.addRow("Bill Discount (Amount):", self.bill_discount_input)

        root.addLayout(charges_form)

        # ---- live totals preview ----
        totals_row = QHBoxLayout()
        totals_row.addStretch()
        self.round_off_label = QLabel("Round Off: 0.00")
        totals_row.addWidget(self.round_off_label)
        self.grand_total_label = QLabel("Grand Total: 0.00")
        self.grand_total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        totals_row.addWidget(self.grand_total_label)
        root.addLayout(totals_row)

        footer_row = QHBoxLayout()
        footer_row.addStretch()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        footer_row.addWidget(self.save_button)
        footer_row.addWidget(self.cancel_button)
        root.addLayout(footer_row)

    def _connect_signals(self) -> None:
        self.add_line_button.clicked.connect(lambda: self._add_line_row())
        self.remove_line_button.clicked.connect(self._on_remove_selected_row)
        self.attach_bill_button.clicked.connect(self._on_attach_bill_clicked)
        self.purchase_list_button.clicked.connect(self._on_view_purchase_list_clicked)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)
        self.link_po_combo.currentIndexChanged.connect(
            lambda idx: self._on_link_po_selected(self.link_po_combo.currentData())
        )
        self.freight_input.valueChanged.connect(self._recalculate_all_line_previews)
        self.other_charges_input.valueChanged.connect(self._recalculate_all_line_previews)
        self.bill_discount_input.valueChanged.connect(self._update_grand_total_preview)

    def _populate_supplier_combo(self) -> None:
        suppliers, _ = self._supplier_engine.search_suppliers(page=1, page_size=1000)
        populate_searchable_combo(
            self.supplier_combo,
            items=suppliers,
            display_attr="supplier_name",
            data_attr="supplier_id",
        )

    # -- Bill attachment (external file only — never persisted in DB) -------

    def _on_attach_bill_clicked(self) -> None:
        source_path, _ = QFileDialog.getOpenFileName(
            self, "Select Bill Image/PDF", "", "Documents (*.png *.jpg *.jpeg *.pdf)"
        )
        if not source_path:
            return

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Save the Bill Copy")
        if not dest_dir:
            return

        try:
            dest_path = Path(dest_dir) / Path(source_path).name
            shutil.copy2(source_path, dest_path)
        except Exception:
            logger.exception("Failed to copy attached bill file")
            QMessageBox.warning(self, "Attachment Failed", "Could not copy the selected file.")
            return

        self._attached_bill_path = str(dest_path)
        self.attach_bill_label.setText(f"Saved: {dest_path.name}")
        self.attach_bill_label.setStyleSheet("color: green; font-size: 11px;")

    # -- Purchase List access ------------------------------------------------

    def _on_view_purchase_list_clicked(self) -> None:
        from screens.purchase_invoice_list_screen import PurchaseInvoiceListScreen
        dialog = PurchaseInvoiceListScreen(
            parent=self,
            engine=self._engine,
            supplier_engine=self._supplier_engine,
            item_engine=self._item_engine,
            current_user_id=self._current_user_id,
        )
        dialog.setWindowFlag(Qt.Window)
        dialog.show()

    # -- PO linking -----------------------------------------------------------

    def _on_supplier_changed(self, _index: int) -> None:
        """Filters the 'Link to Purchase Order' combo to this supplier's
        Draft/Sent POs. Also re-resolves discount% and free-scheme
        suggestions for every already-added line, since both depend on
        which supplier is selected."""
        supplier_id = self.supplier_combo.currentData()
        self.link_po_combo.blockSignals(True)
        self.link_po_combo.clear()
        self.link_po_combo.addItem("(No linked Purchase Order)", None)

        if supplier_id:
            for status in ("Draft", "Sent"):
                orders, _ = self._purchase_order_engine.search_purchase_orders(
                    supplier_id=supplier_id, status=status, page=1, page_size=200
                )
                for order in orders:
                    self.link_po_combo.addItem(order.po_number, order.purchase_order_id)

        self.link_po_combo.blockSignals(False)
        self._linked_purchase_order_id = None

        for row in range(self.table.rowCount()):
            self._on_item_or_qty_changed(row)

    def _on_link_po_selected(self, purchase_order_id: int | None) -> None:
        """Pre-fills line items from the selected PO if chosen, still
        fully editable."""
        self._linked_purchase_order_id = purchase_order_id
        if not purchase_order_id:
            return

        order = self._purchase_order_engine.get_purchase_order(purchase_order_id)
        self.table.setRowCount(0)
        self._row_landing_costs.clear()
        for line in order.lines:
            self._add_line_row(item_id=line.item_id, qty=line.ordered_qty, amount=line.ordered_qty * line.rate)

    # -- line-item grid --------------------------------------------------------

    def _add_line_row(
        self,
        item_id: int | None = None,
        qty: float = 0.0,
        amount: float = 0.0,
    ) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_combo = QComboBox()
        item_combo.setEditable(True)
        item_combo.setMinimumWidth(220)
        populate_searchable_combo(
            item_combo, items=self._all_items, display_attr="item_name", data_attr="item_id"
        )
        item_combo.setCurrentIndex(-1)
        if item_id is not None:
            idx = item_combo.findData(item_id)
            if idx >= 0:
                item_combo.setCurrentIndex(idx)
        item_combo.currentIndexChanged.connect(lambda _, r=row: self._on_item_or_qty_changed(r))
        self.table.setCellWidget(row, COL_ITEM, item_combo)

        batch_item = QTableWidgetItem("")
        self.table.setItem(row, COL_BATCH_NO, batch_item)

        expiry_edit = QDateEdit()
        expiry_edit.setCalendarPopup(True)
        expiry_edit.setDisplayFormat("MM/yyyy")
        expiry_edit.setDate(QDate.currentDate())
        self.table.setCellWidget(row, COL_EXPIRY, expiry_edit)

        qty_spin = _make_blank_until_typed_spin()
        qty_spin.setValue(qty)
        qty_spin.valueChanged.connect(lambda _, r=row: self._on_item_or_qty_changed(r))
        self.table.setCellWidget(row, COL_QTY, qty_spin)

        free_qty_spin = _make_blank_until_typed_spin()
        free_qty_spin.valueChanged.connect(lambda _, r=row: self._recalculate_line_preview(r))
        self.table.setCellWidget(row, COL_FREE_QTY, free_qty_spin)

        amount_spin = _make_blank_until_typed_spin(maximum=100_000_000)
        amount_spin.setValue(amount)
        amount_spin.valueChanged.connect(lambda _, r=row: self._recalculate_line_preview(r))
        self.table.setCellWidget(row, COL_AMOUNT, amount_spin)

        stock_item = QTableWidgetItem("")
        stock_item.setFlags(stock_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_CURRENT_STOCK, stock_item)

        rate_item = QTableWidgetItem("")
        rate_item.setFlags(rate_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_PURCHASE_RATE, rate_item)

        discount_spin = _make_blank_until_typed_spin(maximum=100)
        discount_spin.valueChanged.connect(lambda _, r=row: self._recalculate_line_preview(r))
        self.table.setCellWidget(row, COL_DISCOUNT_PCT, discount_spin)

        super_discount_spin = _make_blank_until_typed_spin(maximum=100)
        super_discount_spin.valueChanged.connect(lambda _, r=row: self._recalculate_line_preview(r))
        self.table.setCellWidget(row, COL_SUPER_DISCOUNT_PCT, super_discount_spin)

        mrp_spin = _make_blank_until_typed_spin()
        mrp_spin.valueChanged.connect(lambda _, r=row: self._recalculate_line_preview(r))
        self.table.setCellWidget(row, COL_MRP, mrp_spin)

        sale_rate_spin = _make_blank_until_typed_spin()
        self.table.setCellWidget(row, COL_SALE_RATE, sale_rate_spin)

        # Everything except the Item combo starts disabled/blank until an
        # item is actually chosen for this row.
        self._set_row_enabled(row, enabled=item_id is not None)

        self._on_item_or_qty_changed(row)

    def _set_row_enabled(self, row: int, enabled: bool) -> None:
        batch_item = self.table.item(row, COL_BATCH_NO)
        if batch_item:
            flags = batch_item.flags()
            batch_item.setFlags((flags | Qt.ItemIsEditable) if enabled else (flags & ~Qt.ItemIsEditable))

        for col in (COL_EXPIRY, COL_QTY, COL_FREE_QTY, COL_AMOUNT, COL_DISCOUNT_PCT, COL_SUPER_DISCOUNT_PCT, COL_MRP, COL_SALE_RATE):
            widget = self.table.cellWidget(row, col)
            if widget:
                widget.setEnabled(enabled)

    def _on_remove_selected_row(self) -> None:
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "No Row Selected", "Click a row first, then Remove Selected Row.")
            return
        for row in selected_rows:
            self.table.removeRow(row)
        self._row_landing_costs.clear()
        self._recalculate_all_line_previews()

    # -- auto-fill: discount% + free-qty scheme + derived rate ---------------

    def _get_business_type(self) -> str:
        """Reads the global Retailer/Wholesaler pricing-mode setting."""
        try:
          return settings_engine.get_setting('general.business_type', 'Retailer')
        except Exception:
          logger.exception("Failed to load business type setting.")
          return 'Retailer'

    def _is_wholesaler(self) -> bool:
        return self._get_business_type() == 'Wholesaler'

    def _on_item_or_qty_changed(self, row_index: int) -> None:
        """Fires when the item combo OR qty changes on a row. Enables the
        rest of the row once an item is chosen, and re-resolves the
        per-item discount% and suggested free qty — both stay fully
        editable afterwards."""
        if row_index >= self.table.rowCount():
            return

        item_combo = self.table.cellWidget(row_index, COL_ITEM)
        supplier_id = self.supplier_combo.currentData()
        item_id = item_combo.currentData() if item_combo else None

        self._set_row_enabled(row_index, enabled=item_id is not None)

        item_changed = self._row_last_item_id.get(row_index) != item_id
        self._row_last_item_id[row_index] = item_id

        if item_id and item_changed:
          try:
              item_dto = self._item_engine.get_item(item_id)
              margin = 0.0
              if item_dto.manufacturer_id:
                  try:
                      margin = float(
                          manufacturer_engine().get_manufacturer(item_dto.manufacturer_id).default_margin_percent
                          or 0
                      )
                  except Exception:
                      logger.exception("Failed to load manufacturer margin for item_id=%s.", item_id)
              super_discount = float(item_dto.super_discount_percent or 0)
              self._row_pricing_meta[row_index] = (margin, super_discount)

              batch_item = self.table.item(row_index, COL_BATCH_NO)
              if batch_item is not None:
                  batches = self._item_engine.get_batches(item_id)
                  if batches:
                      last_batch = max(batches, key=lambda b: b.item_batch_id)
                      batch_item.setText(last_batch.batch_no)

              mrp_spin = self.table.cellWidget(row_index, COL_MRP)
              if mrp_spin is not None and item_dto.mrp:
                  mrp_spin.blockSignals(True)
                  mrp_spin.setValue(float(item_dto.mrp))
                  mrp_spin.blockSignals(False)

              stock_item = self.table.item(row_index, COL_CURRENT_STOCK)
              if stock_item is not None:
                  current_stock = self._item_engine.get_total_stock(item_id)
                  stock_item.setText(f"{current_stock:g}")
          except Exception:
              logger.exception("Failed to load item pricing/batch info for item_id=%s.", item_id)

        qty_widget = self.table.cellWidget(row_index, COL_QTY)
        qty = qty_widget.value() if qty_widget else 0.0

        if item_id and supplier_id:
            discount_percent = self._engine._resolve_discount_percent(item_id, supplier_id)
            discount_widget = self.table.cellWidget(row_index, COL_DISCOUNT_PCT)
            discount_widget.blockSignals(True)
            discount_widget.setValue(discount_percent)
            discount_widget.blockSignals(False)

            suggested_free_qty = self._scheme_engine.suggest_free_qty(item_id, supplier_id, qty)
            free_qty_spin = self.table.cellWidget(row_index, COL_FREE_QTY)
            free_qty_spin.blockSignals(True)
            free_qty_spin.setValue(suggested_free_qty)
            free_qty_spin.blockSignals(False)

        self._recalculate_line_preview(row_index)

    # -- live calculation preview ---------------------------------------------

    def _recalculate_all_line_previews(self) -> None:
        for row in range(self.table.rowCount()):
            self._recalculate_line_preview(row)
        self._update_grand_total_preview()

    def _recalculate_line_preview(self, row_index: int) -> None:
        """Derives Purchase Rate = Amount / Qty, then runs the same
        Engine calculation helpers used at save-time for CC% and Landing
        Cost (kept internally for the Grand Total preview, not shown as
        their own columns anymore) — this screen never re-implements
        that math itself."""
        if row_index >= self.table.rowCount():
            return

        item_combo = self.table.cellWidget(row_index, COL_ITEM)
        item_id = item_combo.currentData() if item_combo else None
        qty = self.table.cellWidget(row_index, COL_QTY).value()
        free_qty = self.table.cellWidget(row_index, COL_FREE_QTY).value()
        amount = self.table.cellWidget(row_index, COL_AMOUNT).value()
        discount_percent = self.table.cellWidget(row_index, COL_DISCOUNT_PCT).value()
        super_discount_widget = self.table.cellWidget(row_index, COL_SUPER_DISCOUNT_PCT)
        super_discount_percent = super_discount_widget.value() if super_discount_widget else 0.0

        total_units = qty + free_qty
        # Purchase Rate = Amount after BOTH discounts (sequential/chain --
        # each discount applies on what's left after the previous one),
        # divided by total units (paid + free), so the user sees the real
        # final per-unit cost directly on screen.
        discounted_amount = amount * (1 - discount_percent / 100) * (1 - super_discount_percent / 100)
        purchase_rate = round(discounted_amount / total_units, 4) if total_units > 0 else 0.0
        rate_item = self.table.item(row_index, COL_PURCHASE_RATE)
        rate_item.setText(f"{purchase_rate:.2f}" if total_units > 0 else "")

        # MRP is now manual-entry (pre-filled from the item's last-remembered
        # MRP when the item is selected -- see _on_item_or_qty_changed).
        # Sale Rate (Wholesaler mode) derives from whatever MRP is on screen
        # right now, using PTR = MRP x (1 - margin%/100).
        margin, _unused_item_super_discount = self._row_pricing_meta.get(row_index, (0.0, 0.0))
        mrp_spin = self.table.cellWidget(row_index, COL_MRP)
        current_mrp = mrp_spin.value() if mrp_spin is not None else 0.0
        ptr = current_mrp * (1 - margin / 100)

        sale_rate_spin = self.table.cellWidget(row_index, COL_SALE_RATE)
        if sale_rate_spin is not None and self._is_wholesaler():
          sale_rate_spin.blockSignals(True)
          sale_rate_spin.setValue(ptr if current_mrp > 0 else 0.0)
          sale_rate_spin.blockSignals(False)

        cc_percent = self._engine._resolve_cc_percent(item_id) if item_id else 0.0

        from engines.purchase_engine import PurchaseInvoiceLineDTO

        preview_line = PurchaseInvoiceLineDTO(
            item_id=item_id or 0,
            batch_no="",
            expiry_month=1,
            expiry_year=2070,
            qty=qty,
            free_qty=free_qty,
            purchase_rate=purchase_rate, 
            cc_percent=cc_percent,
            mrp=0.0,
            sale_rate=0.0,
            discount_percent=discount_percent,
        )

        total_freight = self.freight_input.value()
        total_other = self.other_charges_input.value()
        all_lines = self._build_preview_lines_for_allocation(row_index, preview_line)
        allocated = self._engine._allocate_invoice_level_charges(all_lines, total_freight, total_other)
        calculated = self._engine._calculate_line_amounts(allocated[row_index])

        self._row_landing_costs[row_index] = calculated.landing_cost_per_unit

        self._update_grand_total_preview()

    def _build_preview_lines_for_allocation(self, current_row: int, current_line) -> list:
        """Rebuilds a lightweight DTO list across all rows so the freight/
        other-charge allocation preview reflects every row's share, not
        just the one being edited."""
        from engines.purchase_engine import PurchaseInvoiceLineDTO

        lines = []
        for row in range(self.table.rowCount()):
            if row == current_row:
                lines.append(current_line)
                continue
            item_combo = self.table.cellWidget(row, COL_ITEM)
            item_id = item_combo.currentData() if item_combo else None
            qty = self.table.cellWidget(row, COL_QTY).value()
            amount = self.table.cellWidget(row, COL_AMOUNT).value()
            rate = round(amount / qty, 4) if qty > 0 else 0.0
            lines.append(
                PurchaseInvoiceLineDTO(
                    item_id=item_id or 0,
                    batch_no="",
                    expiry_month=1,
                    expiry_year=2070,
                    qty=qty,
                    free_qty=self.table.cellWidget(row, COL_FREE_QTY).value(),
                    purchase_rate=rate,
                    discount_percent=self.table.cellWidget(row, COL_DISCOUNT_PCT).value(),
                    cc_percent=0.0,
                    mrp=0.0,
                    sale_rate=0.0,
                )
            )
        return lines

    def _update_grand_total_preview(self) -> None:
        """Mirrors the Engine's own raw-total -> bill-discount ->
        round-off sequence, purely for display — the Engine recomputes
        this authoritatively at save time; this is never trusted as the
        value actually persisted."""
        raw_total = 0.0
        for row in range(self.table.rowCount()):
            landing_cost = self._row_landing_costs.get(row, 0.0)
            qty = self.table.cellWidget(row, COL_QTY).value()
            free_qty = self.table.cellWidget(row, COL_FREE_QTY).value()
            raw_total += landing_cost * (qty + free_qty)

        bill_discount = self.bill_discount_input.value()
        after_discount = raw_total - bill_discount
        rounded_total = round(after_discount)
        round_off = round(rounded_total - after_discount, 2)

        self.round_off_label.setText(f"Round Off: {round_off:.2f}")
        self.grand_total_label.setText(f"Grand Total: {rounded_total:.2f}")

    # -- save ----------------------------------------------------------------

    def _collect_form_values(self) -> dict:
        lines = []
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, COL_ITEM)
            item_id = item_combo.currentData() if item_combo else None
            qty = self.table.cellWidget(row, COL_QTY).value()
            amount = self.table.cellWidget(row, COL_AMOUNT).value()
            purchase_rate = round(amount / qty, 4) if qty > 0 else 0.0
            expiry_date = self.table.cellWidget(row, COL_EXPIRY).date()

            lines.append(
                {
                    "item_id": item_id,
                    "batch_no": self.table.item(row, COL_BATCH_NO).text().strip(),
                    "expiry_month": expiry_date.month(),
                    "expiry_year": expiry_date.year(),
                    "qty": qty,
                    "free_qty": self.table.cellWidget(row, COL_FREE_QTY).value(),
                    "purchase_rate": purchase_rate,
                    "discount_percent": self.table.cellWidget(row, COL_DISCOUNT_PCT).value(),
                    "mrp": self.table.cellWidget(row, COL_MRP).value(),
                    "sale_rate": self.table.cellWidget(row, COL_SALE_RATE).value(),
                }
            )

        return {
            "supplier_id": self.supplier_combo.currentData(),
            "invoice_number": self.invoice_number_input.text().strip(),
            "invoice_date_bs": self.invoice_date_input.get_bs_date_string(),
            "purchase_order_id": self._linked_purchase_order_id,
            "total_freight": self.freight_input.value(),
            "total_other_charges": self.other_charges_input.value(),
            "bill_discount_amount": self.bill_discount_input.value(),
            "lines": lines,
        }

    def _on_save_clicked(self) -> None:
        payload = self._collect_form_values()
        supplier_id = payload["supplier_id"]

        try:
            invoice_dto = self._engine.create_purchase_invoice(payload, self._current_user_id)
        except DuplicateRecordError as exc:
            QMessageBox.warning(self, "Duplicate Invoice", str(exc))
            return
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot Save", str(exc))
            return
        except Exception:
            logger.exception("Failed to create purchase invoice")
            QMessageBox.critical(self, "Error", "Could not save the purchase invoice. Please try again.")
            return

        # Save each line's free-qty scheme for next time — never blocks
        # or reverses the invoice save if a scheme write fails.
        for line in payload["lines"]:
            if line["item_id"] and supplier_id:
                self._scheme_engine.save_scheme(
                    line["item_id"], supplier_id, line["qty"], line["free_qty"], self._current_user_id
                )
            if line["item_id"] and line.get("mrp"):
                self._item_engine.update_item_mrp(line["item_id"], line["mrp"])

        QMessageBox.information(
            self, "Saved", f"Purchase invoice {invoice_dto.internal_ref_number} saved successfully."
        )
        self.accept()