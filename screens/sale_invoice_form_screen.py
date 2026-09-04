"""
screens/sale_invoice_form_screen.py

Sale Invoice Add Screen/Controller - Medical ERP V2

Responsibilities (and ONLY these -- "No SQL. No business logic."):
    - Area -> Customer two-combo search (confirmed requirement): Area combo
      populated from customer_engine.get_lookup_data()["areas"]; selecting
      an Area repopulates the Customer combo via
      customer_engine.get_active_customers_by_area(area_id).
    - Build the line-item grid's VISIBLE COLUMNS from the Settings group
      "Sale" (sale.column_show_*) -- Qty/Item/Rate/Amount are hard-coded
      always visible; every other column is added/removed based on its
      setting. This same visible-column set is what later prints on the
      invoice (single source of truth, per confirmed requirement) -- no
      separate print-template column list exists anywhere.
    - Row-level inline item entry: the Item cell of EVERY row is itself a
      searchable combo (utils.searchable_combo_helper.populate_searchable_combo,
      same helper the Purchase Invoice form's row combos use). Selecting an
      item in the LAST row auto-appends a new empty row (Excel-style
      continuous entry). A conventional "+ Add Item" toolbar button also
      exists.
    - On item selection / qty change / entry-mode toggle: calls
      engine.compute_line() (a PREVIEW call, not a save) to auto-fill
      Batch/Expiry (read-only cells), current_rate/rate, mrp, and -- in
      Wholesale mode -- the "Scheme: X+Y" tooltip badge on the Free Qty
      cell, sourced directly from ItemFreeSchemeEngine.get_scheme_for_item()
      since compute_line() itself only returns the resolved free_qty, not
      the ratio.
    - Per-row toggle between Free Qty mode and Net Rate mode (confirmed
      requirement) -- a small combo per row; switching modes re-triggers
      the engine preview and resets any manual rate/free_qty override for
      that row, since the two modes give the same field a different
      meaning.
    - Qty is the ONLY field that starts blank and is always editable; Rate
      is always editable (auto-filled, user may override -- an explicit
      user value always wins, never overwritten by a later preview); Batch/
      Expiry are always read-only.
    - Save button -> SaleEngine.create_sale_invoice() -- only rows with an
      item selected AND qty > 0 are sent.
    - Surfaces ValidationError / DuplicateRecordError / the special
      EngineErrorWithInvoice (invoice saved, but a stock line failed)
      distinctly, mirroring PurchaseInvoiceFormScreen._on_save_clicked()'s
      QMessageBox-based error handling (Sale mirrors Purchase's choice to
      use QMessageBox directly rather than utils.message/integration_adapters).

NOTE on the constructor: Part 3's original stub signature was
__init__(self, parent, engine, customer_engine, item_free_scheme_engine) --
this omitted item_engine and current_user_id, both of which
PurchaseInvoiceFormScreen's real constructor takes directly (item_engine for
the one-time row-combo item cache; current_user_id for the audit-stamped
create_sale_invoice() call). Added here for the same reasons.

NOTE on customer_engine.get_active_customers_by_area(): Part 1 of this
blueprint only extended models/customer_model.py with this function, not
engines/customer_engine.py. Per the project's screens-call-engines-only
convention (mirrors every other engine call in this file), a thin
pass-through wrapper is assumed to exist on CustomerEngine:

    def get_active_customers_by_area(area_id: int) -> list[dict]:
        return customer_model.get_active_customers_by_area(area_id)

If that wrapper does not exist yet, add it to engines/customer_engine.py
before wiring this screen.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from engines.exceptions import DuplicateRecordError, ValidationError
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.sale_engine import EngineErrorWithInvoice, SaleEngine
from engines import settings_engine
from utils.searchable_combo_helper import populate_searchable_combo
from utils.window_chrome import apply_standard_window_chrome

# Reused as-is from the Purchase module rather than duplicated -- both are
# private (underscore-prefixed) module-level helpers, but this avoids a
# second, possibly-drifting copy of the same BS-date-picker widget and
# blank-until-typed spinbox factory. If these get promoted to a shared
# utils module later, update this import accordingly.
from screens.purchase_invoice_form_screen import _BsDatePicker, _make_blank_until_typed_spin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
# Column layout -- Item/Qty/Rate/Amount are ALWAYS visible (never gated by
# a Setting); every other column is toggled by _build_visible_columns().
# ---------------------------------------------------------------------- #
COL_ITEM = 0
COL_BATCH_NO = 1
COL_EXPIRY = 2
COL_PACKING = 3
COL_ENTRY_MODE = 4
COL_QTY = 5
COL_FREE_QTY = 6
COL_RATE = 7
COL_DISCOUNT_PCT = 8
COL_MRP = 9
COL_TAX_PCT = 10
COL_TAX_AMOUNT = 11
COL_AMOUNT = 12
COLUMN_COUNT = 13

COLUMN_HEADERS = [
    "Item", "Batch No", "Expiry", "Packing", "Mode", "Qty", "Free Qty",
    "Rate", "Disc %", "MRP", "Tax %", "Tax Amt", "Amount",
]

ENTRY_MODE_OPTIONS = [("Free Qty", "free_qty"), ("Net Rate", "net_rate")]

PAYMENT_TYPE_OPTIONS = [
    ("(Credit -- not paid now)", None),
    ("Cash", "Cash"),
    ("Bank", "Bank"),
    ("eSewa", "eSewa"),
    ("Khalti", "Khalti"),
    ("IPS", "IPS"),
]


def _populate_dict_combo(
    combo: QComboBox,
    rows: list[dict],
    display_key: str,
    data_key: str,
    placeholder: Optional[str] = None,
) -> None:
    """Same searchable-combo behaviour as
    utils.searchable_combo_helper.populate_searchable_combo(), but for rows
    that are plain dicts (customer_engine.get_customer() /
    get_lookup_data() / get_active_customers_by_area() all return raw
    dicts, not DTOs -- confirmed for get_customer(); populate_searchable_combo
    itself uses getattr() and would raise on a dict)."""
    combo.clear()
    if placeholder is not None:
        combo.addItem(placeholder, None)
    for row in rows:
        combo.addItem(str(row.get(display_key, "")), row.get(data_key))

    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    completer = QCompleter([combo.itemText(i) for i in range(combo.count())], combo)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setFilterMode(Qt.MatchContains)
    combo.setCompleter(completer)


class SaleInvoiceFormScreen(QDialog):
    """Add-only screen for creating a Sale Invoice. Every Save goes through
    SaleEngine.create_sale_invoice(); this screen never touches the
    database or SQL directly."""

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        parent,
        engine: SaleEngine,
        customer_engine,
        item_engine,
        item_free_scheme_engine: ItemFreeSchemeEngine,
        current_user_id: int,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._embedded = embedded
        apply_standard_window_chrome(self, width=1300, height=800, start_maximized=True, embedded=embedded)

        self._engine = engine
        self._customer_engine = customer_engine
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._current_user_id = current_user_id

        # Sale Mode is fixed for the whole invoice the moment the screen
        # opens -- same single-read-then-locked contract SaleEngine itself
        # uses inside create_sale_invoice() (is_wholesale_mode() is read
        # ONCE, not re-checked per line), so the grid's column layout and
        # every row's preview stay consistent for this one invoice even if
        # the Setting changes elsewhere mid-session.
        self._is_wholesale = self._engine.is_wholesale_mode()

        # Per-row state: whether the user has manually typed into Rate /
        # Free Qty for that row (as opposed to it being auto-filled by a
        # compute_line() preview). An explicit user value always wins and
        # is never clobbered by a later preview -- confirmed rule.
        self._row_rate_overridden: dict[int, bool] = {}
        self._row_free_qty_overridden: dict[int, bool] = {}

        # One-time cache, same reasoning as PurchaseInvoiceFormScreen's
        # self._all_items -- every row's item combo is populated from this
        # instead of re-querying the DB per row/per keystroke.
        self._all_items, _ = self._item_engine.search_items(page=1, page_size=5000)

        lookup_data = self._customer_engine.get_lookup_data()
        self._areas = lookup_data.get("areas", [])
        # Key names ("price_level_name"/"price_level_id") are the natural
        # guess from get_customer()'s confirmed column names -- verify
        # against the real get_lookup_data() return shape and adjust if
        # different.
        self._price_levels_by_id = {
            row.get("price_level_id"): row.get("price_level_name", "")
            for row in lookup_data.get("price_levels", [])
        }
        self._selected_price_level_id: Optional[int] = None

        self.setWindowTitle("New Sale Invoice")

        self._build_ui()
        self._connect_signals()
        self._populate_area_combo()
        self._add_line_row()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top_row = QHBoxLayout()

        left_form = QFormLayout()
        self.area_combo = QComboBox()
        self.area_combo.setMinimumWidth(200)
        left_form.addRow("Area:", self.area_combo)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(240)
        left_form.addRow("Customer:", self.customer_combo)
        top_row.addLayout(left_form)

        mid_form = QFormLayout()
        self.invoice_date_input = _BsDatePicker()
        mid_form.addRow("Invoice Date (BS):", self.invoice_date_input)

        self.payment_type_combo = QComboBox()
        for label, data in PAYMENT_TYPE_OPTIONS:
            self.payment_type_combo.addItem(label, data)
        mid_form.addRow("Payment Type:", self.payment_type_combo)

        self.amount_paid_input = _make_blank_until_typed_spin(maximum=100_000_000)
        mid_form.addRow("Amount Paid Now:", self.amount_paid_input)
        top_row.addLayout(mid_form)

        # Read-only customer info panel -- purely displays what
        # customer_engine.get_customer() already returns, no new business
        # logic (per confirmed scope).
        info_form = QFormLayout()
        self.price_level_label = QLabel("-")
        info_form.addRow("Price Level:", self.price_level_label)
        self.credit_limit_label = QLabel("-")
        info_form.addRow("Credit Limit:", self.credit_limit_label)
        self.mode_label = QLabel("Wholesale" if self._is_wholesale else "Retail")
        self.mode_label.setStyleSheet("font-weight: bold;")
        info_form.addRow("Sale Mode:", self.mode_label)
        top_row.addLayout(info_form)

        top_row.addStretch()

        button_col = QVBoxLayout()
        self.add_line_button = QPushButton("+ Add Item")
        button_col.addWidget(self.add_line_button)
        top_row.addLayout(button_col)

        root.addLayout(top_row)

        table_action_row = QHBoxLayout()
        self.remove_line_button = QPushButton("Remove Selected Row")
        table_action_row.addWidget(self.remove_line_button)
        table_action_row.addStretch()
        root.addLayout(table_action_row)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)
        self.table.setColumnWidth(COL_BATCH_NO, 100)
        self.table.setColumnWidth(COL_EXPIRY, 90)
        self.table.setColumnWidth(COL_PACKING, 80)
        self.table.setColumnWidth(COL_ENTRY_MODE, 100)
        self.table.setColumnWidth(COL_QTY, 70)
        self.table.setColumnWidth(COL_FREE_QTY, 70)
        self.table.setColumnWidth(COL_RATE, 90)
        self.table.setColumnWidth(COL_DISCOUNT_PCT, 70)
        self.table.setColumnWidth(COL_MRP, 90)
        self.table.setColumnWidth(COL_TAX_PCT, 60)
        self.table.setColumnWidth(COL_TAX_AMOUNT, 90)
        self.table.setColumnWidth(COL_AMOUNT, 100)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.table, stretch=1)

        self._apply_column_visibility()

        remarks_form = QFormLayout()
        self.remarks_input = QLineEdit()
        self.remarks_input.setPlaceholderText("Optional notes about this invoice")
        remarks_form.addRow("Remarks:", self.remarks_input)
        root.addLayout(remarks_form)

        totals_row = QHBoxLayout()
        totals_row.addStretch()
        self.total_qty_label = QLabel("Total Qty: 0")
        totals_row.addWidget(self.total_qty_label)
        self.total_free_qty_label = QLabel("Total Free: 0")
        totals_row.addWidget(self.total_free_qty_label)
        self.grand_total_label = QLabel("Grand Total (preview): 0.00")
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

    def _apply_column_visibility(self) -> None:
        """Reads every sale.column_show_* setting and hides/shows the
        matching grid column. This exact visible-column set is also what
        the (future) print/export routine iterates -- never a separate
        print-template list (confirmed requirement)."""
        visibility = self._build_visible_columns()
        for col, visible in visibility.items():
            self.table.setColumnHidden(col, not visible)

    def _build_visible_columns(self) -> dict[int, bool]:
        show_batch = bool(settings_engine.get_setting("sale.column_show_batch", True))
        show_expiry = bool(settings_engine.get_setting("sale.column_show_expiry", True))
        show_mrp = bool(settings_engine.get_setting("sale.column_show_mrp", True))
        show_discount = bool(settings_engine.get_setting("sale.column_show_discount_percent", True))
        show_packing = bool(settings_engine.get_setting("sale.column_show_packing", True))
        show_tax = bool(settings_engine.get_setting("sale.column_show_tax", False))
        # Free Qty / Entry Mode follow Wholesale mode directly (the SAME
        # setting SaleEngine.is_wholesale_mode() reads) -- never an
        # independent toggle, per confirmed rule #7 ("Free column hidden =
        # Retail, free-scheme never applies").
        show_free = self._is_wholesale
        return {
            COL_ITEM: True,
            COL_BATCH_NO: show_batch,
            COL_EXPIRY: show_expiry,
            COL_PACKING: show_packing,
            COL_ENTRY_MODE: show_free,
            COL_QTY: True,
            COL_FREE_QTY: show_free,
            COL_RATE: True,
            COL_DISCOUNT_PCT: show_discount,
            COL_MRP: show_mrp,
            COL_TAX_PCT: show_tax,
            COL_TAX_AMOUNT: show_tax,
            COL_AMOUNT: True,
        }

    def _connect_signals(self) -> None:
        self.add_line_button.clicked.connect(lambda: self._add_line_row())
        self.remove_line_button.clicked.connect(self._on_remove_selected_row)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.area_combo.currentIndexChanged.connect(
            lambda _: self._on_area_changed(self.area_combo.currentData())
        )
        self.customer_combo.currentIndexChanged.connect(
            lambda _: self._on_customer_changed(self.customer_combo.currentData())
        )

    # ------------------------------------------------------------------ #
    # Header: Area -> Customer two-combo cascade
    # ------------------------------------------------------------------ #
    def _populate_area_combo(self) -> None:
        _populate_dict_combo(
            self.area_combo, self._areas, display_key="area_name", data_key="area_id",
            placeholder="(All Areas)",
        )

    def _on_area_changed(self, area_id) -> None:
        """Repopulates the Customer combo via
        customer_engine.get_active_customers_by_area(area_id) -- the
        confirmed two-combo cascade."""
        if area_id is None:
            self.customer_combo.clear()
            self._on_customer_changed(None)
            return
        customers = self._customer_engine.get_active_customers_by_area(area_id)
        _populate_dict_combo(
            self.customer_combo, customers, display_key="customer_name", data_key="customer_id",
            placeholder="Select customer...",
        )

    def _on_customer_changed(self, customer_id) -> None:
        if customer_id is None:
            self._selected_price_level_id = None
            self.price_level_label.setText("-")
            self.credit_limit_label.setText("-")
            return
        customer = self._customer_engine.get_customer(customer_id)
        if customer is None:
            self._selected_price_level_id = None
            self.price_level_label.setText("-")
            self.credit_limit_label.setText("-")
            return
        self._selected_price_level_id = customer.get("price_level_id")
        price_level_name = self._price_levels_by_id.get(self._selected_price_level_id, "-")
        self.price_level_label.setText(price_level_name or "-")
        credit_limit = customer.get("credit_limit")
        self.credit_limit_label.setText(f"{credit_limit:,.2f}" if credit_limit is not None else "-")

    # ------------------------------------------------------------------ #
    # Grid
    # ------------------------------------------------------------------ #
    def _add_line_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_combo = QComboBox()
        populate_searchable_combo(
            item_combo, items=self._all_items, display_attr="item_name",
            data_attr="item_id", placeholder="Select item...",
        )
        self.table.setCellWidget(row, COL_ITEM, item_combo)
        item_combo.currentIndexChanged.connect(
            lambda _, r=row: self._on_row_item_selected(r, self.table.cellWidget(r, COL_ITEM).currentData())
        )

        for col in (COL_BATCH_NO, COL_EXPIRY, COL_PACKING, COL_MRP, COL_TAX_PCT, COL_TAX_AMOUNT, COL_AMOUNT):
            cell = QTableWidgetItem("")
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, col, cell)

        entry_mode_combo = QComboBox()
        for label, data in ENTRY_MODE_OPTIONS:
            entry_mode_combo.addItem(label, data)
        self.table.setCellWidget(row, COL_ENTRY_MODE, entry_mode_combo)
        entry_mode_combo.currentIndexChanged.connect(lambda _, r=row: self._on_row_entry_mode_toggled(r))

        qty_spin = _make_blank_until_typed_spin(decimals=2, maximum=1_000_000)
        self.table.setCellWidget(row, COL_QTY, qty_spin)
        qty_spin.valueChanged.connect(lambda _, r=row: self._on_row_qty_changed(r))

        free_qty_spin = _make_blank_until_typed_spin(decimals=2, maximum=1_000_000)
        self.table.setCellWidget(row, COL_FREE_QTY, free_qty_spin)
        free_qty_spin.valueChanged.connect(lambda _, r=row: self._on_row_free_qty_edited(r))

        rate_spin = _make_blank_until_typed_spin(decimals=2, maximum=10_000_000)
        self.table.setCellWidget(row, COL_RATE, rate_spin)
        rate_spin.valueChanged.connect(lambda _, r=row: self._on_row_rate_edited(r))

        discount_spin = _make_blank_until_typed_spin(decimals=2, maximum=100)
        self.table.setCellWidget(row, COL_DISCOUNT_PCT, discount_spin)
        discount_spin.valueChanged.connect(lambda _, r=row: self._recalculate_row_amount(r))

        self._row_rate_overridden[row] = False
        self._row_free_qty_overridden[row] = False

        self._apply_column_visibility()

    def _remove_row(self, row: int) -> None:
        if self.table.rowCount() <= 1:
            return  # always keep at least one (possibly blank) row
        self.table.removeRow(row)
        for store in (self._row_rate_overridden, self._row_free_qty_overridden):
            for r in sorted((k for k in store if k > row)):
                store[r - 1] = store.pop(r)
            store.pop(row, None)
        self._update_totals_preview()

    def _on_remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a row to remove first.")
            return
        self._remove_row(row)

    # ------------------------------------------------------------------ #
    # Preview computation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _set_spin_value_silently(spin, value: float) -> None:
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)

    def _on_row_item_selected(self, row: int, item_id) -> None:
        if item_id is None:
            return

        qty_spin = self.table.cellWidget(row, COL_QTY)
        entry_mode_combo = self.table.cellWidget(row, COL_ENTRY_MODE)
        entry_mode = entry_mode_combo.currentData() if entry_mode_combo else "free_qty"
        qty = qty_spin.value() if qty_spin else 0.0

        line_input: dict = {"item_id": item_id, "entry_mode": entry_mode, "qty": qty}
        if self._row_rate_overridden.get(row):
            line_input["rate"] = self.table.cellWidget(row, COL_RATE).value()
        if self._row_free_qty_overridden.get(row):
            line_input["free_qty"] = self.table.cellWidget(row, COL_FREE_QTY).value()

        try:
            computed = self._engine.compute_line(line_input, self._is_wholesale)
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot Add Item", "\n".join(exc.errors))
            item_combo = self.table.cellWidget(row, COL_ITEM)
            item_combo.blockSignals(True)
            item_combo.setCurrentIndex(0)
            item_combo.blockSignals(False)
            return
        except Exception:  # noqa: BLE001
            logger.exception("compute_line preview failed for item_id=%s", item_id)
            QMessageBox.critical(self, "Error", "Could not load item pricing. Please try again.")
            return

        self._apply_computed_line_to_row(row, computed)

        was_last_row = row == self.table.rowCount() - 1
        if was_last_row:
            self._add_line_row()

        self._update_totals_preview()

    def _apply_computed_line_to_row(self, row: int, computed: dict) -> None:
        self.table.item(row, COL_BATCH_NO).setText(str(computed.get("batch_no") or ""))
        expiry_month = computed.get("expiry_month")
        expiry_year = computed.get("expiry_year")
        expiry_text = f"{expiry_month:02d}/{expiry_year}" if expiry_month and expiry_year else ""
        self.table.item(row, COL_EXPIRY).setText(expiry_text)
        self.table.item(row, COL_MRP).setText(f"{computed.get('mrp', 0):.2f}")
        self.table.item(row, COL_TAX_PCT).setText(f"{computed.get('tax_percent', 0):.2f}")
        self.table.item(row, COL_TAX_AMOUNT).setText(f"{computed.get('tax_amount', 0):.2f}")
        self.table.item(row, COL_AMOUNT).setText(f"{computed.get('amount', 0):.2f}")

        if not self._row_rate_overridden.get(row):
            self._set_spin_value_silently(self.table.cellWidget(row, COL_RATE), computed.get("rate", 0))
        if not self._row_free_qty_overridden.get(row):
            self._set_spin_value_silently(self.table.cellWidget(row, COL_FREE_QTY), computed.get("free_qty", 0))

        free_qty_spin = self.table.cellWidget(row, COL_FREE_QTY)
        if self._is_wholesale:
            item_id = self.table.cellWidget(row, COL_ITEM).currentData()
            scheme = self._item_free_scheme_engine.get_scheme_for_item(item_id) if item_id else None
            if scheme is not None:
                scheme_qty, scheme_free = scheme
                free_qty_spin.setToolTip(f"Scheme: {scheme_qty:g}+{scheme_free:g}")
            else:
                free_qty_spin.setToolTip("No free scheme configured for this item.")
        else:
            free_qty_spin.setToolTip("")

    def _on_row_entry_mode_toggled(self, row: int) -> None:
        """Free Qty mode <-> Net Rate mode switch for one row; clears any
        manual override for that row (the two modes give Rate/Free Qty
        different meanings, so a prior override should not silently carry
        over) and re-runs the compute_line() preview so Free/Rate refresh
        immediately."""
        self._row_rate_overridden[row] = False
        self._row_free_qty_overridden[row] = False
        item_id = self.table.cellWidget(row, COL_ITEM).currentData()
        if item_id is None:
            return
        self._on_row_item_selected(row, item_id)

    def _on_row_qty_changed(self, row: int) -> None:
        """Re-runs the compute_line() preview whenever Qty changes, since
        Free/Rate/Amount all depend on it."""
        item_id = self.table.cellWidget(row, COL_ITEM).currentData()
        if item_id is None:
            return
        self._on_row_item_selected(row, item_id)

    def _on_row_rate_edited(self, row: int) -> None:
        """Fires only on a genuine user edit -- programmatic sets from a
        preview go through _set_spin_value_silently() with signals
        blocked. Marks the row's Rate as explicitly overridden (an
        explicit user value always wins over later previews) and updates
        the Amount locally without another engine round trip."""
        self._row_rate_overridden[row] = True
        self._recalculate_row_amount(row)

    def _on_row_free_qty_edited(self, row: int) -> None:
        self._row_free_qty_overridden[row] = True
        self._recalculate_row_amount(row)

    def _recalculate_row_amount(self, row: int) -> None:
        """Lightweight local recompute (no engine round trip) for Rate /
        Free Qty / Discount % edits -- mirrors compute_line()'s own
        gross/discount/amount formula so the grid stays consistent between
        previews without hitting the Engine on every keystroke."""
        qty_spin = self.table.cellWidget(row, COL_QTY)
        rate_spin = self.table.cellWidget(row, COL_RATE)
        discount_spin = self.table.cellWidget(row, COL_DISCOUNT_PCT)
        if not (qty_spin and rate_spin and discount_spin):
            return
        qty = qty_spin.value()
        rate = rate_spin.value()
        discount_percent = discount_spin.value()
        gross = qty * rate
        discount_amount = gross * discount_percent / 100
        amount = gross - discount_amount
        self.table.item(row, COL_AMOUNT).setText(f"{amount:.2f}")
        self._update_totals_preview()

    def _update_totals_preview(self) -> None:
        """Lightweight preview only -- the authoritative totals (including
        CC and tax roll-up) come back from SaleEngine.create_sale_invoice()
        at save time."""
        total_qty = 0.0
        total_free_qty = 0.0
        total_amount = 0.0
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, COL_ITEM)
            if not item_combo or item_combo.currentData() is None:
                continue
            qty_spin = self.table.cellWidget(row, COL_QTY)
            free_qty_spin = self.table.cellWidget(row, COL_FREE_QTY)
            amount_item = self.table.item(row, COL_AMOUNT)
            total_qty += qty_spin.value() if qty_spin else 0.0
            total_free_qty += free_qty_spin.value() if free_qty_spin else 0.0
            try:
                total_amount += float(amount_item.text()) if amount_item and amount_item.text() else 0.0
            except ValueError:
                pass

        self.total_qty_label.setText(f"Total Qty: {total_qty:g}")
        self.total_free_qty_label.setText(f"Total Free: {total_free_qty:g}")
        self.grand_total_label.setText(f"Grand Total (preview): {total_amount:,.2f}")

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _collect_form_values(self) -> dict:
        lines: list[dict] = []
        for row in range(self.table.rowCount()):
            item_combo = self.table.cellWidget(row, COL_ITEM)
            item_id = item_combo.currentData() if item_combo else None
            qty_spin = self.table.cellWidget(row, COL_QTY)
            qty = qty_spin.value() if qty_spin else 0.0

            # Only rows with an item selected AND qty > 0 are sent, per
            # confirmed scope.
            if item_id is None or qty <= 0:
                continue

            entry_mode_combo = self.table.cellWidget(row, COL_ENTRY_MODE)
            entry_mode = entry_mode_combo.currentData() if entry_mode_combo else "free_qty"

            line: dict = {
                "item_id": item_id,
                "entry_mode": entry_mode,
                "qty": qty,
                "discount_percent": self.table.cellWidget(row, COL_DISCOUNT_PCT).value(),
            }
            if self._row_rate_overridden.get(row):
                line["rate"] = self.table.cellWidget(row, COL_RATE).value()
            if self._row_free_qty_overridden.get(row):
                line["free_qty"] = self.table.cellWidget(row, COL_FREE_QTY).value()

            lines.append(line)

        return {
            "customer_id": self.customer_combo.currentData(),
            "area_id": self.area_combo.currentData(),
            "price_level_id": self._selected_price_level_id,
            "invoice_date_bs": self.invoice_date_input.get_bs_date_string(),
            "payment_type": self.payment_type_combo.currentData(),
            "amount_paid_now": self.amount_paid_input.value(),
            "remarks": self.remarks_input.text().strip(),
            "lines": lines,
        }

    def _on_save_clicked(self) -> None:
        payload = self._collect_form_values()

        if payload["customer_id"] is None:
            QMessageBox.warning(self, "Cannot Save", "Select a customer first.")
            return
        if not payload["lines"]:
            QMessageBox.warning(self, "Cannot Save", "Add at least one item with a quantity greater than zero.")
            return

        try:
            invoice_dto = self._engine.create_sale_invoice(payload, self._current_user_id)
        except EngineErrorWithInvoice as exc:
            # Invoice IS saved -- only stock reconciliation failed on one or
            # more lines. Distinct message, NOT treated as a hard failure,
            # mirrors PurchaseInvoiceFormScreen/ItemFormScreen's existing
            # partial-success pattern.
            QMessageBox.warning(
                self, "Saved With Stock Warning",
                f"Invoice {exc.dto.invoice_number} was created, but stock could not "
                f"be reduced for:\n" + "\n".join(exc.stock_errors),
            )
            if self._embedded:
                self.saved.emit()
                self.close_requested.emit()
            else:
                self.accept()
            return
        except DuplicateRecordError as exc:
            QMessageBox.warning(self, "Duplicate Invoice", str(exc))
            return
        except ValidationError as exc:
            QMessageBox.warning(self, "Cannot Save", "\n".join(exc.errors))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create sale invoice")
            QMessageBox.critical(self, "Error", "Could not save the sale invoice. Please try again.")
            return

        QMessageBox.information(self, "Saved", f"Sale invoice {invoice_dto.invoice_number} saved successfully.")
        if self._embedded:
            self.saved.emit()
            self.close_requested.emit()
        else:
            self.accept()

    def reject(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        super().reject()


__all__ = ["SaleInvoiceFormScreen"]