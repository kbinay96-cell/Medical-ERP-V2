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
      Batch/Expiry (read-only cells), current_rate/rate, and mrp.
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

import os
import tempfile

from screens.sale_invoice_view_dialog import SaleInvoiceViewDialog
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QTime, QDate, QSize
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from engines.exceptions import DuplicateRecordError, ValidationError
from engines.permission_enforcer import PermissionDeniedError
from engines.item_free_scheme_engine import ItemFreeSchemeEngine
from engines.sale_engine import EngineErrorWithInvoice, SaleEngine
from engines.exceptions import RecordNotFoundError
from engines import settings_engine
from utils.searchable_combo_helper import populate_searchable_combo
from utils.window_chrome import apply_standard_window_chrome

# Reused as-is from the Purchase module rather than duplicated -- both are
# private (underscore-prefixed) module-level helpers, but this avoids a
# second, possibly-drifting copy of the same BS-date-picker widget and
# blank-until-typed spinbox factory. If these get promoted to a shared
# utils module later, update this import accordingly.
from screens.purchase_invoice_form_screen import _make_blank_until_typed_spin

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import QWidget
from PySide6.QtWidgets import QGridLayout, QDialog
from PySide6.QtCore import Signal
from datetime import date as _date
from widgets.bs_calendar_date_picker import BSCalendarDatePicker

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
    ("Credit", None),
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
        current_username: str = "system",
        embedded: bool = False,
        existing_invoice_id: Optional[int] = None,
        initial_customer_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self._embedded = embedded
        self.setObjectName("saleInvoiceFormScreen")
        apply_standard_window_chrome(
            self,
            width=1440,
            height=900,
            min_size=QSize(1120, 720),
            start_maximized=True,
            embedded=embedded,
        )

        self._engine = engine
        self._customer_engine = customer_engine
        self._item_engine = item_engine
        self._item_free_scheme_engine = item_free_scheme_engine
        self._current_user_id = current_user_id
        self._current_username = current_username
        self._editing_invoice_id: Optional[int] = None

        # Sale Mode is fixed for the whole invoice the moment the screen
        # opens -- same single-read-then-locked contract SaleEngine itself
        # uses inside create_sale_invoice() (is_wholesale_mode() is read
        # ONCE, not re-checked per line), so the grid's column layout and
        # every row's preview stay consistent for this one invoice even if
        # the Setting changes elsewhere mid-session.
        self._is_wholesale = self._engine.is_wholesale_mode()
        self._free_scheme_enabled = self._engine.is_free_scheme_enabled()

        # Per-row state: whether the user has manually typed into Rate /
        # Free Qty for that row (as opposed to it being auto-filled by a
        # compute_line() preview). An explicit user value always wins and
        # is never clobbered by a later preview -- confirmed rule.
        self._row_rate_overridden: dict[int, bool] = {}
        self._row_free_qty_overridden: dict[int, bool] = {}
        self._row_forced_batch_id: dict[int, int] = {}

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
        if existing_invoice_id is not None:
            self._load_existing_invoice(existing_invoice_id)
        else:
            self._add_line_row()
            if initial_customer_id is not None:
                self._preselect_customer(initial_customer_id)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 7, 10, 7)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        if self._embedded:
            self.btnBack = QPushButton("Back", self)
            self.btnBack.setCursor(Qt.PointingHandCursor)
            self.btnBack.setObjectName("saleSecondaryButton")
            self.btnBack.clicked.connect(self.reject)
            header.addWidget(self.btnBack)
        self.form_title_label = QLabel("New Sale Invoice")
        self.form_title_label.setObjectName("saleFormTitle")
        header.addWidget(self.form_title_label)
        header.addStretch(1)
        invoice_meta = QVBoxLayout()
        invoice_meta.setSpacing(0)
        invoice_label = QLabel("INVOICE NUMBER")
        invoice_label.setObjectName("saleFieldCaption")
        self.invoice_no_label = QLabel("(auto-generated)")
        self.invoice_no_label.setObjectName("saleInvoiceNumber")
        invoice_meta.addWidget(invoice_label)
        invoice_meta.addWidget(self.invoice_no_label)
        header.addLayout(invoice_meta)
        date_panel = QVBoxLayout()
        date_panel.setSpacing(0)
        date_label = QLabel("INVOICE DATE (BS)")
        date_label.setObjectName("saleFieldCaption")
        date_panel.addWidget(date_label)
        self.invoice_date_input = BSCalendarDatePicker()
        self.invoice_date_input.setFixedWidth(145)
        date_panel.addWidget(self.invoice_date_input)
        header.addLayout(date_panel)
        root.addLayout(header)

        details_row = QHBoxLayout()
        details_row.setSpacing(6)

        customer_group = QGroupBox("Customer & Payment")
        customer_group.setObjectName("saleSectionCard")
        customer_grid = QGridLayout(customer_group)
        customer_grid.setContentsMargins(8, 14, 8, 7)
        customer_grid.setHorizontalSpacing(7)
        customer_grid.setVerticalSpacing(2)

        def add_field(layout, text: str, widget, row: int, column: int) -> None:
            caption = QLabel(text)
            caption.setObjectName("saleFieldCaption")
            layout.addWidget(caption, row, column)
            layout.addWidget(widget, row + 1, column)

        self.area_combo = QComboBox()
        self.area_combo.setMinimumWidth(80)
        add_field(customer_grid, "Area", self.area_combo, 0, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(120)
        add_field(customer_grid, "Customer", self.customer_combo, 0, 1)
        self.payment_type_combo = QComboBox()
        for label, data in PAYMENT_TYPE_OPTIONS:
            self.payment_type_combo.addItem(label, data)
        add_field(customer_grid, "Payment type", self.payment_type_combo, 2, 0)
        customer_snapshot = QWidget()
        info_grid = QGridLayout(customer_snapshot)
        info_grid.setContentsMargins(0, 3, 0, 0)
        info_grid.setHorizontalSpacing(8)
        info_grid.setVerticalSpacing(1)
        self.contact_no_label = QLabel("-")
        add_field(info_grid, "Contact no.", self.contact_no_label, 0, 0)
        self.price_level_label = QLabel("-")
        add_field(info_grid, "Price level", self.price_level_label, 0, 1)
        self.credit_limit_label = QLabel("-")
        add_field(info_grid, "Credit limit", self.credit_limit_label, 0, 2)
        self.outstanding_label = QLabel("-")
        self.outstanding_label.setObjectName("saleOutstandingValue")
        add_field(info_grid, "Outstanding", self.outstanding_label, 2, 0)
        self.mode_label = QLabel("Wholesale" if self._is_wholesale else "Retail")
        self.mode_label.setObjectName("saleModeValue")
        add_field(info_grid, "Sale mode", self.mode_label, 2, 1)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(2, 1)
        customer_grid.addWidget(customer_snapshot, 4, 0, 1, 2)
        customer_grid.setColumnStretch(0, 2)
        customer_grid.setColumnStretch(1, 3)
        details_row.addWidget(customer_group, 6)

        amount_group = QGroupBox("Invoice Summary")
        amount_group.setObjectName("saleSectionCard")
        amount_panel = QGridLayout(amount_group)
        amount_panel.setContentsMargins(8, 14, 8, 7)
        amount_panel.setHorizontalSpacing(6)
        amount_panel.setVerticalSpacing(2)
        self.amount_paid_input = _make_blank_until_typed_spin(maximum=100_000_000)
        self.amount_paid_input.setPrefix("Rs. ")
        self.amount_paid_input.setFixedWidth(118)
        add_field(amount_panel, "Paid now", self.amount_paid_input, 0, 0)
        self.bill_discount_mode_combo = QComboBox()
        self.bill_discount_mode_combo.addItems(["Flat", "%"])
        self.bill_discount_mode_combo.setFixedWidth(54)
        self.bill_discount_input = _make_blank_until_typed_spin(maximum=100_000_000)
        self.bill_discount_input.setFixedWidth(104)
        discount_row = QHBoxLayout()
        discount_row.setContentsMargins(0, 0, 0, 0)
        discount_row.setSpacing(3)
        discount_row.addWidget(self.bill_discount_mode_combo)
        discount_row.addWidget(self.bill_discount_input)
        discount_widget = QWidget()
        discount_widget.setLayout(discount_row)
        add_field(amount_panel, "Bill discount", discount_widget, 0, 1)
        self.grand_total_label = QLabel("Total: 0.00")
        self.grand_total_label.setObjectName("saleGrandTotal")
        self.grand_total_label.setWordWrap(True)
        self.grand_total_label.setMaximumWidth(230)
        amount_panel.addWidget(self.grand_total_label, 2, 0, 1, 2)
        self.due_label = QLabel("Due: 0.00")
        self.due_label.setObjectName("saleDueTotal")
        amount_panel.addWidget(self.due_label, 3, 0, 1, 2)
        amount_panel.setColumnStretch(0, 1)
        amount_panel.setColumnStretch(1, 1)
        details_row.addWidget(amount_group, 4)

        root.addLayout(details_row)

        item_group = QGroupBox("Invoice Items")
        item_group.setObjectName("saleSectionCard")
        item_layout = QVBoxLayout(item_group)
        item_layout.setContentsMargins(8, 14, 8, 7)
        item_layout.setSpacing(4)
        item_toolbar = QHBoxLayout()
        item_toolbar.setSpacing(5)
        self.line_count_label = QLabel("0 items")
        self.line_count_label.setObjectName("saleLineCount")
        item_toolbar.addWidget(self.line_count_label)
        item_toolbar.addSpacing(5)
        self.barcode_scan_input = QLineEdit()
        self.barcode_scan_input.setPlaceholderText("Scan barcode")
        self.barcode_scan_input.setClearButtonEnabled(True)
        self.barcode_scan_input.setMaximumWidth(210)
        self.barcode_scan_input.returnPressed.connect(self._on_barcode_scanned)
        item_toolbar.addWidget(self.barcode_scan_input)
        self.connect_mobile_button = QPushButton("Mobile")
        self.connect_mobile_button.setObjectName("saleSecondaryButton")
        self.connect_mobile_button.setToolTip("Connect mobile scanner")
        self.connect_mobile_button.clicked.connect(self._on_connect_mobile_clicked)
        item_toolbar.addWidget(self.connect_mobile_button)
        item_toolbar.addStretch(1)
        self.remove_line_button = QPushButton("Remove")
        self.remove_line_button.setObjectName("saleSecondaryButton")
        item_toolbar.addWidget(self.remove_line_button)
        self.add_line_button = QPushButton("+ Item")
        self.add_line_button.setObjectName("saleSecondaryButton")
        item_toolbar.addWidget(self.add_line_button)
        item_layout.addLayout(item_toolbar)

        self.table = QTableWidget(0, COLUMN_COUNT)
        self.table.setObjectName("saleInvoiceLines")
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        table_header = self.table.horizontalHeader()
        table_header.setSectionResizeMode(COL_ITEM, QHeaderView.Stretch)
        table_header.setMinimumSectionSize(68)
        table_header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for column in (
            COL_EXPIRY, COL_ENTRY_MODE, COL_QTY, COL_FREE_QTY, COL_RATE,
            COL_DISCOUNT_PCT, COL_MRP, COL_TAX_PCT, COL_TAX_AMOUNT, COL_AMOUNT,
        ):
            self.table.horizontalHeaderItem(column).setTextAlignment(
                Qt.AlignCenter | Qt.AlignVCenter
            )
        self.table.setColumnWidth(COL_BATCH_NO, 78)
        self.table.setColumnWidth(COL_EXPIRY, 72)
        self.table.setColumnWidth(COL_PACKING, 58)
        self.table.setColumnWidth(COL_ENTRY_MODE, 78)
        self.table.setColumnWidth(COL_QTY, 56)
        self.table.setColumnWidth(COL_FREE_QTY, 56)
        self.table.setColumnWidth(COL_RATE, 68)
        self.table.setColumnWidth(COL_DISCOUNT_PCT, 54)
        self.table.setColumnWidth(COL_MRP, 66)
        self.table.setColumnWidth(COL_TAX_PCT, 48)
        self.table.setColumnWidth(COL_TAX_AMOUNT, 64)
        self.table.setColumnWidth(COL_AMOUNT, 78)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        item_layout.addWidget(self.table, stretch=1)
        root.addWidget(item_group)

        self._apply_column_visibility()

        footer_row = QHBoxLayout()
        footer_row.setSpacing(8)
        remarks_panel = QVBoxLayout()
        remarks_panel.setSpacing(1)
        remarks_label = QLabel("REMARKS")
        remarks_label.setObjectName("saleFieldCaption")
        remarks_panel.addWidget(remarks_label)
        self.remarks_input = QLineEdit()
        self.remarks_input.setPlaceholderText("Remarks")
        self.remarks_input.setMaximumWidth(280)
        remarks_panel.addWidget(self.remarks_input)
        footer_row.addLayout(remarks_panel, stretch=2)
        self.total_qty_label = QLabel("Total Qty: 0")
        self.total_qty_label.setObjectName("saleFooterMetric")
        footer_row.addWidget(self.total_qty_label)
        self.total_free_qty_label = QLabel("Total Free: 0")
        self.total_free_qty_label.setObjectName("saleFooterMetric")
        footer_row.addWidget(self.total_free_qty_label)
        footer_row.addStretch(1)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("salePrimaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("saleSecondaryButton")
        self.save_button.setFixedWidth(82)
        self.cancel_button.setFixedWidth(72)
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
        show_free = self._free_scheme_enabled
        return {
            COL_ITEM: True,
            COL_BATCH_NO: show_batch,
            COL_EXPIRY: show_expiry,
            COL_PACKING: show_packing,
            COL_ENTRY_MODE: show_free,
            COL_QTY: True,
            COL_FREE_QTY: show_free,
            COL_RATE: self._is_wholesale,
            COL_DISCOUNT_PCT: show_discount,
            COL_MRP: show_mrp,
            COL_TAX_PCT: show_tax,
            COL_TAX_AMOUNT: show_tax,
            COL_AMOUNT: True,
        }

    def _connect_signals(self) -> None:
        self.remove_line_button.clicked.connect(self._on_remove_selected_row)
        self.add_line_button.clicked.connect(self._add_line_row)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.area_combo.currentIndexChanged.connect(
            lambda _: self._on_area_changed(self.area_combo.currentData())
        )
        self.customer_combo.currentIndexChanged.connect(
            lambda _: self._on_customer_changed(self.customer_combo.currentData())
        )
        self.bill_discount_input.valueChanged.connect(lambda _: self._update_totals_preview())
        self.bill_discount_mode_combo.currentIndexChanged.connect(lambda _: self._update_totals_preview())
        self.amount_paid_input.valueChanged.connect(lambda _: self._update_totals_preview())

    # ------------------------------------------------------------------ #
    # Header: Area -> Customer two-combo cascade
    # ------------------------------------------------------------------ #
    def _populate_area_combo(self) -> None:
        _populate_dict_combo(
            self.area_combo, self._areas, display_key="area_name", data_key="area_id",
            placeholder="(All Areas)",
        )

    def _preselect_customer(self, customer_id: int) -> bool:
        """Select `customer_id` on a blank form (Record Detail Hub -> New Sale).

        The Customer combo is only ever filled by the Area -> Customer
        cascade, so the customer's Area is selected first (which repopulates
        the Customer combo through _on_area_changed), then the customer
        itself. Both go through the combos' normal signals -- the same chain
        as a user picking them by hand. Returns False (form left blank) if
        the customer cannot be reached through the cascade."""
        customer = self._customer_engine.get_customer(customer_id)
        if customer is None or customer.get("area_id") is None:
            return False
        area_index = self.area_combo.findData(customer.get("area_id"))
        if area_index < 0:
            return False
        self.area_combo.setCurrentIndex(area_index)
        customer_index = self.customer_combo.findData(customer_id)
        if customer_index < 0:
            return False
        self.customer_combo.setCurrentIndex(customer_index)
        return True

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
            self.contact_no_label.setText("-")
            self.outstanding_label.setText("-")
            return
        customer = self._customer_engine.get_customer(customer_id)
        if customer is None:
            self._selected_price_level_id = None
            self.price_level_label.setText("-")
            self.credit_limit_label.setText("-")
            self.contact_no_label.setText("-")
            self.outstanding_label.setText("-")
            return
        self._selected_price_level_id = customer.get("price_level_id")
        price_level_name = self._price_levels_by_id.get(self._selected_price_level_id, "-")
        self.price_level_label.setText(price_level_name or "-")
        credit_limit = customer.get("credit_limit")
        self.credit_limit_label.setText(f"{credit_limit:,.2f}" if credit_limit is not None else "-")
        contact_no = customer.get("mobile") or customer.get("phone") or customer.get("alternate_mobile")
        self.contact_no_label.setText(contact_no or "-")
        outstanding = self._engine.get_customer_outstanding(customer_id)
        self.outstanding_label.setText(f"{outstanding:,.2f}")

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
        self._update_line_count()

    def _update_line_count(self) -> None:
        count = sum(
            1
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, COL_ITEM).currentData() is not None
        )
        self.line_count_label.setText(f"{count} item{'s' if count != 1 else ''}")

    def _load_existing_invoice(self, invoice_id: int) -> None:
        try:
            dto = self._engine.get_sale_invoice(invoice_id)
        except RecordNotFoundError as exc:
            QMessageBox.critical(self, "Not Found", str(exc))
            self._add_line_row()
            return

        self._editing_invoice_id = invoice_id
        self.setWindowTitle(f"Edit Sale Invoice — {dto.invoice_number}")
        self.form_title_label.setText("Edit Sale Invoice")
        self.invoice_no_label.setText(dto.invoice_number)

        area_idx = self.area_combo.findData(dto.area_id)
        if area_idx >= 0:
            self.area_combo.setCurrentIndex(area_idx)

        customer_idx = self.customer_combo.findData(dto.customer_id)
        if customer_idx >= 0:
            self.customer_combo.setCurrentIndex(customer_idx)

        self.invoice_date_input._set_bs_date(dto.invoice_date_bs)

        payment_idx = self.payment_type_combo.findData(dto.payment_type)
        if payment_idx >= 0:
            self.payment_type_combo.setCurrentIndex(payment_idx)

        self._set_spin_value_silently(self.amount_paid_input, dto.amount_paid_now)

        if dto.bill_discount_percent > 0:
            self.bill_discount_mode_combo.setCurrentText("%")
            self._set_spin_value_silently(self.bill_discount_input, dto.bill_discount_percent)
        else:
            self.bill_discount_mode_combo.setCurrentText("Flat")
            self._set_spin_value_silently(self.bill_discount_input, dto.bill_discount_amount)

        self.remarks_input.setText(dto.remarks or "")

        for line in dto.lines:
            self._load_line_into_row(line)

        self._add_line_row()
        self._update_totals_preview()

    def _load_line_into_row(self, line) -> None:
        self._add_line_row()
        row = self.table.rowCount() - 1

        item_combo = self.table.cellWidget(row, COL_ITEM)
        item_combo.blockSignals(True)
        item_idx = item_combo.findData(line.item_id)
        if item_idx >= 0:
            item_combo.setCurrentIndex(item_idx)
        item_combo.blockSignals(False)

        entry_mode_combo = self.table.cellWidget(row, COL_ENTRY_MODE)
        entry_mode_combo.blockSignals(True)
        entry_idx = entry_mode_combo.findData(line.entry_mode)
        if entry_idx >= 0:
            entry_mode_combo.setCurrentIndex(entry_idx)
        entry_mode_combo.blockSignals(False)

        self._set_spin_value_silently(self.table.cellWidget(row, COL_QTY), line.qty)
        self._set_spin_value_silently(self.table.cellWidget(row, COL_DISCOUNT_PCT), line.discount_percent)

        self._row_rate_overridden[row] = True
        self._row_free_qty_overridden[row] = True
        self._row_forced_batch_id[row] = line.item_batch_id
        self._set_spin_value_silently(self.table.cellWidget(row, COL_RATE), line.rate)
        self._set_spin_value_silently(self.table.cellWidget(row, COL_FREE_QTY), line.free_qty)

        line_input = {
            "item_id": line.item_id,
            "item_batch_id": line.item_batch_id,
            "entry_mode": line.entry_mode,
            "qty": line.qty,
            "rate": line.rate,
            "free_qty": line.free_qty,
            "discount_percent": line.discount_percent,
        }
        try:
            computed = self._engine.compute_line(
                line_input, self._is_wholesale, self._free_scheme_enabled
            )
            self._apply_computed_line_to_row(row, computed)
        except Exception:
            logger.exception("Failed to recompute preview for existing line item_id=%s", line.item_id)

    def _remove_row(self, row: int) -> None:
        if self.table.rowCount() <= 1:
            return  # always keep at least one (possibly blank) row
        self.table.removeRow(row)
        for store in (self._row_rate_overridden, self._row_free_qty_overridden):
            for r in sorted((k for k in store if k > row)):
                store[r - 1] = store.pop(r)
            store.pop(row, None)
        self._update_line_count()
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

    def _on_barcode_scanned(self) -> None:
        barcode = self.barcode_scan_input.text().strip()
        self.barcode_scan_input.clear()
        self._process_scanned_barcode(barcode)

    def _on_connect_mobile_clicked(self) -> None:
        from screens.mobile_connect_dialog import MobileConnectDialog

        dialog = MobileConnectDialog(self, item_lookup_fn=self._item_engine.get_item_id_by_barcode)
        dialog.barcode_scanned.connect(self._process_scanned_barcode)
        dialog.exec()

    def _process_scanned_barcode(self, barcode: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        barcode = (barcode or "").strip()
        if not barcode:
            return
        item_id = self._item_engine.get_item_id_by_barcode(barcode)
        if item_id is None:
            QMessageBox.warning(self, "Barcode Not Found", f"No batch is registered with barcode '{barcode}'.")
            return

        # Reuse the existing blank last row (Excel-style continuous entry
        # already keeps one empty row at the bottom) instead of always
        # inserting a new one.
        last_row = self.table.rowCount() - 1
        item_combo = self.table.cellWidget(last_row, COL_ITEM) if last_row >= 0 else None
        if item_combo is None or item_combo.currentData() is not None:
            last_row = self._add_row()
            item_combo = self.table.cellWidget(last_row, COL_ITEM)

        idx = item_combo.findData(item_id)
        if idx >= 0:
            item_combo.setCurrentIndex(idx)

    def _on_row_item_selected(self, row: int, item_id) -> None:
        if item_id is None:
            return

        # Any manual (re-)selection of the item for this row invalidates
        # any batch that was previously locked in from an edit-mode load --
        # a freshly picked item must go through normal nearest-expiry
        # batch selection, not the old item's batch.
        self._row_forced_batch_id.pop(row, None)

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
            computed = self._engine.compute_line(
                line_input, self._is_wholesale, self._free_scheme_enabled
            )
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
        batch_item = self.table.item(row, COL_BATCH_NO)
        batch_item.setText(str(computed.get("batch_no") or ""))
        batch_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        expiry_month = computed.get("expiry_month")
        expiry_year = computed.get("expiry_year")
        expiry_text = f"{expiry_month:02d}/{expiry_year}" if expiry_month and expiry_year else ""
        expiry_item = self.table.item(row, COL_EXPIRY)
        expiry_item.setText(expiry_text)
        expiry_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        packing_item = self.table.item(row, COL_PACKING)
        packing_item.setText(str(computed.get("packing") or ""))
        packing_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        mrp_item = self.table.item(row, COL_MRP)
        mrp_item.setText(f"{computed.get('mrp', 0):.2f}")
        mrp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tax_percent_item = self.table.item(row, COL_TAX_PCT)
        tax_percent_item.setText(f"{computed.get('tax_percent', 0):.2f}")
        tax_percent_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tax_amount_item = self.table.item(row, COL_TAX_AMOUNT)
        tax_amount_item.setText(f"{computed.get('tax_amount', 0):.2f}")
        tax_amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amount_item = self.table.item(row, COL_AMOUNT)
        amount_item.setText(f"{computed.get('amount', 0):.2f}")
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if not self._row_rate_overridden.get(row):
            self._set_spin_value_silently(self.table.cellWidget(row, COL_RATE), computed.get("rate", 0))
        if not self._row_free_qty_overridden.get(row):
            self._set_spin_value_silently(self.table.cellWidget(row, COL_FREE_QTY), computed.get("free_qty", 0))

        self._update_line_count()

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
        amount_item = self.table.item(row, COL_AMOUNT)
        amount_item.setText(f"{amount:.2f}")
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
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

        bill_discount_value = self.bill_discount_input.value() if self.bill_discount_input.text().strip() else 0.0
        if self.bill_discount_mode_combo.currentText() == "%":
            bill_discount_amount = round(total_amount * bill_discount_value / 100, 2)
        else:
            bill_discount_amount = bill_discount_value

        grand_total_after_discount = total_amount - bill_discount_amount

        self.total_qty_label.setText(f"Total Qty: {total_qty:g}")
        self.total_free_qty_label.setText(f"Total Free: {total_free_qty:g}")
        self.grand_total_label.setText(f"Total: {grand_total_after_discount:,.2f}")
        paid = self.amount_paid_input.value() if self.amount_paid_input.text().strip() else 0.0
        due = grand_total_after_discount - paid
        self.due_label.setText(f"Due: {due:,.2f}")

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
            if row in self._row_forced_batch_id:
                line["item_batch_id"] = self._row_forced_batch_id[row]
            if self._row_rate_overridden.get(row):
                line["rate"] = self.table.cellWidget(row, COL_RATE).value()
            if self._row_free_qty_overridden.get(row):
                line["free_qty"] = self.table.cellWidget(row, COL_FREE_QTY).value()

            lines.append(line)

        _bill_discount_value = self.bill_discount_input.value()
        _bill_discount_is_percent = self.bill_discount_mode_combo.currentText() == "%"

        return {
            "customer_id": self.customer_combo.currentData(),
            "area_id": self.area_combo.currentData(),
            "price_level_id": self._selected_price_level_id,
            "invoice_date_bs": self.invoice_date_input.get_bs_date_string(),
            "payment_type": self.payment_type_combo.currentData(),
            "amount_paid_now": self.amount_paid_input.value(),
            "bill_discount_percent": _bill_discount_value if _bill_discount_is_percent else 0.0,
            "bill_discount_amount": _bill_discount_value if not _bill_discount_is_percent else 0.0,
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
            if self._editing_invoice_id is not None:
                invoice_dto = self._engine.update_sale_invoice(
                    self._editing_invoice_id, payload, self._current_user_id
                )
            else:
                invoice_dto = self._engine.create_sale_invoice(payload, self._current_user_id)
        except EngineErrorWithInvoice as exc:
            QMessageBox.warning(
                self, "Saved With Stock Warning",
                f"Invoice {exc.dto.invoice_number} was created, but stock could not "
                f"be reduced for:\n" + "\n".join(exc.stock_errors),
            )
            self.invoice_no_label.setText(exc.dto.invoice_number)
            self._open_print_preview(exc.dto)
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
        except PermissionDeniedError as exc:
            QMessageBox.warning(self, "Permission Denied", str(exc))
            return
        except Exception:
            logger.exception("Failed to create sale invoice")
            QMessageBox.critical(self, "Error", "Could not save the invoice. Please try again.")
            return

        QMessageBox.information(self, "Saved", f"Sale invoice {invoice_dto.invoice_number} saved successfully.")
        self.invoice_no_label.setText(invoice_dto.invoice_number)
        self._open_print_preview(invoice_dto)
        if self._embedded:
            self.saved.emit()
            self.close_requested.emit()
        else:
            self.accept()


    def _open_print_preview(self, invoice_dto) -> None:
        """Opens the Print Preview dialog automatically after a successful
        save (both clean success and stock-warning success paths -- the
        invoice IS persisted in both). Runs modally before the form closes,
        so the user sees/prints the bill before returning to the list."""
        try:
            dialog = SaleInvoiceViewDialog(
                self, invoice_dto, self._item_engine, self._customer_engine,
                self._free_scheme_enabled,
            )
            dialog.exec()
        except Exception:
            logger.exception("Failed to open Sale Invoice print preview.")
            QMessageBox.warning(
                self, "Print Preview",
                "The invoice was saved, but the print preview could not be opened.",
            )

    def reject(self) -> None:
        if self._embedded:
            self.close_requested.emit()
            return
        super().reject()


__all__ = ["SaleInvoiceFormScreen"]