"""
screens/report_runner_screen.py

Report Runner Screen - Medical ERP V2

THE single screen that renders ANY report_definition row -- the entire
point of the data-driven Reports architecture (one file instead of
200+). Screen layer only: collects input, calls the Engine, renders
whatever DTO comes back. No SQL, no business logic here.

Export (Excel/PDF/Print) buttons are DELIBERATELY NOT included in this
version -- the project's existing ReportLab/openpyxl export utility
(mentioned in the Reports blueprint as "already used elsewhere in the
app") has not yet been verified (exact module/function signature
unconfirmed). Adding buttons that call an unverified/nonexistent
utility would be placeholder code, which this project's rules forbid.
Wire export once that utility is confirmed -- everything else
(category tree, dynamic filters, results grid, drill-down) is fully
functional without it.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from PySide6.QtCore import Qt, QDate, QStringListModel, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDateEdit, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QToolBar, QToolButton, QVBoxLayout,
    QWidget,
)

from engines.exceptions import RecordNotFoundError, ValidationError
from engines.report_engine import ReportEngine
from models.role_model import get_role_name
from utils.integration_adapters import show_error
from utils.searchable_combo_helper import populate_searchable_combo

_TREE_ROLE_KIND = Qt.UserRole + 1   # "category" | "report"
_TREE_ROLE_CODE = Qt.UserRole       # category_id (int) or report_code (str)

_STATUS_VALUES = ["Draft", "Posted", "Cancelled"]
_PAYMENT_MODE_VALUES = ["Cash", "Bank Transfer", "Cheque", "Card", "Other"]

# Related report_category names collapsed under one parent menu button,
# so the horizontal toolbar shows fewer, more meaningful top-level
# items. A category name NOT listed here falls back to its own name as
# its own group (safe default for any future new category). Keyed by
# category_name (stable business label), not category_id.
_CATEGORY_GROUPS: dict[str, str] = {
    "Sales": "Sales",
    "Sales Return": "Sales",
    "Purchase": "Purchase",
    "Purchase Return": "Purchase",
    "Stock": "Stock",
    "Customers/Receivables": "Parties",
    "Suppliers/Payables": "Parties",
    "Cash & Bank": "Cash & Bank",
    "Tax/VAT": "Tax & Profit",
    "Profit & Margin": "Tax & Profit",
    "Expiry & Loss": "Expiry & Loss",
    "Item Analysis": "Item Analysis",
    "Manufacturer Analysis": "Item Analysis",
    "Country Analysis": "Item Analysis",
    "Discount & Free Quantity": "Discounts",
}


def _format_cell(value: Any, col_type: str) -> str:
    if value is None:
        return ""
    if col_type == "currency":
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


class ReportRunnerScreen(QWidget):
    """
    Left panel: category tree -> report list per category.
    Right panel: dynamic filter panel (built from the selected report's
    applicable_filters) + Run button + results grid.
    Row double-click drills down: into another report (handled
    internally, since this screen already knows how to run any
    report_code), or into a source document's own View screen (NOT
    handled internally -- emitted via drill_down_requested, since this
    screen has no business knowing how every other module opens its
    own detail view; the parent, e.g. DashboardScreen, owns that).
    """

    close_requested = Signal()
    drill_down_requested = Signal(str, dict)   # (drill_down_source_type, full_row_dict)

    def __init__(
        self,
        parent,
        engine: ReportEngine,
        roleid: int,
        item_engine=None,
        supplier_engine=None,
        initial_report_code: Optional[str] = None,
        embedded: bool = False,
        initial_filters: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._role_name = get_role_name(roleid)
        self._item_engine = item_engine
        self._supplier_engine = supplier_engine
        self._embedded = embedded

        self._current_definition: Optional[dict] = None
        self._filter_widgets: dict[str, tuple[QWidget, str, Optional[QCheckBox]]] = {}
        self._last_result = None
        self._nav_stack: list[str] = []

        self.setWindowTitle("Reports")
        self.setMinimumSize(1200, 700)

        root = QVBoxLayout(self)

        if self._embedded:
            top_row = QHBoxLayout()
            btn_back_page = QPushButton("← Back", self)
            btn_back_page.clicked.connect(self.close_requested.emit)
            top_row.addWidget(btn_back_page)
            top_row.addStretch()
            root.addLayout(top_row)

        # Drill-back button + horizontal category/report menu bar share
        # ONE row now (was two separate rows) -- shrinks vertical
        # space, and the drill-back button naturally sits to the left
        # of the menu whenever it becomes visible.
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)

        self._drill_back_button = QPushButton("← Back to previous report", self)
        self._drill_back_button.setVisible(False)
        self._drill_back_button.clicked.connect(self._go_back_one_level)
        nav_row.addWidget(self._drill_back_button)

        # Horizontal category/report navigation bar (replaces the old
        # left-side QTreeWidget, then the flat-per-category QToolBar).
        # Related categories are now grouped under one parent
        # QToolButton (see _CATEGORY_GROUPS + _load_categories) so the
        # row stays short; each button's dropdown QMenu still shows the
        # original category names as section headers. Styled bold with
        # a bottom border so it visually reads as a menu bar, not a
        # generic toolbar.
        self._nav_toolbar = QToolBar(self)
        self._nav_toolbar.setMovable(False)
        self._nav_toolbar.setFloatable(False)
        self._nav_toolbar.setStyleSheet(
            "QToolBar { spacing: 4px; padding: 4px 2px; border: none;"
            " border-bottom: 2px solid palette(mid); }"
            "QToolButton { font-weight: bold; font-size: 15px;"
            " padding: 7px 16px; border-radius: 4px; }"
            "QToolButton:hover { background-color: palette(midlight); }"
            "QToolButton::menu-indicator { width: 0px; }"
        )
        nav_row.addWidget(self._nav_toolbar, stretch=1)
        root.addLayout(nav_row)

        # Global report search bar, directly under the nav bar. Round
        # (pill-shaped) input, built from the same category/report data
        # already loaded for the toolbar (no separate query) -- filters
        # across every report in every category, and jumps straight to
        # the selected report on pick.
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 4, 0, 4)
        search_row.addStretch()

        search_label = QLabel("Search", self)
        search_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        search_row.addWidget(search_label)

        self._search_bar = QLineEdit(self)
        self._search_bar.setPlaceholderText("🔍 search any Reports...")
        self._search_bar.setFixedHeight(34)
        self._search_bar.setMaximumWidth(800)
        self._search_bar.setStyleSheet(
            "QLineEdit { border: 1px solid palette(mid); border-radius: 13px;"
            " padding: 2px 12px; font-size: 12px; }"
            "QLineEdit:focus { border: 1px solid palette(highlight); }"
        )
        self._search_completer_model = QStringListModel(self)
        self._search_completer = QCompleter(self._search_completer_model, self)
        self._search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._search_completer.activated.connect(self._on_search_result_activated)
        self._search_bar.setCompleter(self._search_completer)
        search_row.addWidget(self._search_bar)
        search_row.addStretch()

        root.addLayout(search_row)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)

        self._report_title_label = QLabel("Select a report from the menu above", self)
        self._report_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(self._report_title_label)

        # Filter panel: one compact horizontal row instead of stacked
        # form rows, so date/type/etc. all fit side-by-side without
        # needing to scroll for the typical filter count. Horizontal
        # scrollbar stays available as a fallback only, for a report
        # with an unusually large number of filters.
        self._filter_scroll = QScrollArea(self)
        self._filter_scroll.setWidgetResizable(True)
        self._filter_scroll.setFixedHeight(70)
        self._filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._filter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._filter_container = QWidget()
        self._filter_row_layout = QHBoxLayout(self._filter_container)
        self._filter_row_layout.setContentsMargins(4, 4, 4, 4)
        self._filter_row_layout.setSpacing(14)
        self._filter_scroll.setWidget(self._filter_container)
        right_layout.addWidget(self._filter_scroll)

        action_row = QHBoxLayout()
        self._run_button = QPushButton("Run Report", self)
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._on_run_clicked)
        action_row.addWidget(self._run_button)
        action_row.addStretch()
        right_layout.addLayout(action_row)

        self._summary_label = QLabel("", self)
        right_layout.addWidget(self._summary_label)

        self._table = QTableWidget(0, 0, self)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        right_layout.addWidget(self._table, stretch=1)

        root.addWidget(right_panel, stretch=1)

        # "Report Name (Category)" -> report_code, built by
        # _load_categories, used by the search bar.
        self._report_index: dict[str, str] = {}

        self._load_categories()

        if initial_report_code:
            self._on_report_selected(initial_report_code, initial_filters)
            if initial_filters:
                # Caller supplied filters (Record Detail Hub ledger/history
                # button): run the report right away, like the drill-down
                # path does. Deferred to the event loop so the screen is
                # fully constructed and navigated-to before it runs.
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._on_run_clicked)

    # ------------------------------------------------------------------ #
    # CATEGORY / REPORT NAVIGATION (horizontal toolbar + dropdown menus)
    # ------------------------------------------------------------------ #
    def _load_categories(self) -> None:
        self._nav_toolbar.clear()
        self._report_index = {}
        search_labels: list[str] = []

        # group_label -> QMenu. Related categories share one menu (one
        # QMenu.addSection() header per original category inside it),
        # so the toolbar shows one button per GROUP, not per category.
        group_menus: dict[str, QMenu] = {}
        group_order: list[str] = []

        for category in self._engine.list_categories():
            category_name = category["category_name"]
            reports = self._engine.list_reports_by_category(category["report_category_id"])
            if not reports:
                continue  # empty category -- no reports seeded yet, don't show a dead button

            group_label = _CATEGORY_GROUPS.get(category_name, category_name)
            if group_label not in group_menus:
                menu = QMenu(group_label, self)
                # Submenu items intentionally smaller/lighter than the
                # bold 15px toolbar buttons above, so the top-level
                # menu bar reads as clearly "heavier" than its own
                # dropdown contents.
                menu.setStyleSheet(
                    "QMenu::item { font-weight: normal; font-size: 12px;"
                    " padding: 4px 24px 4px 12px; }"
                    "QMenu::section {"
                    " font-weight: bold; font-size: 11px; color: palette(dark);"
                    " padding: 4px 12px; }"
                )
                group_menus[group_label] = menu
                group_order.append(group_label)
            menu = group_menus[group_label]
            menu.addSection(category_name)

            for report in reports:
                action = QAction(report["report_name"], self)
                action.setData(report["report_code"])
                action.triggered.connect(
                    lambda checked=False, code=report["report_code"]: self._on_nav_report_chosen(code)
                )
                menu.addAction(action)

                label = f"{report['report_name']} ({category_name})"
                self._report_index[label] = report["report_code"]
                search_labels.append(label)

        for group_label in group_order:
            button = QToolButton(self)
            button.setText(group_label)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(group_menus[group_label])
            self._nav_toolbar.addWidget(button)

        self._search_completer_model.setStringList(search_labels)

    def _on_nav_report_chosen(self, report_code: str) -> None:
        self._nav_stack.clear()
        self._drill_back_button.setVisible(False)
        self._on_report_selected(report_code)

    def _on_search_result_activated(self, label: str) -> None:
        report_code = self._report_index.get(label)
        if report_code is None:
            return
        self._search_bar.clear()
        self._nav_stack.clear()
        self._drill_back_button.setVisible(False)
        self._on_report_selected(report_code)

    # ------------------------------------------------------------------ #
    # REPORT SELECTION + FILTER PANEL
    # ------------------------------------------------------------------ #
    def _on_report_selected(self, report_code: str, prefill: Optional[dict[str, Any]] = None) -> None:
        definition = self._engine.get_report_definition(report_code)
        if definition is None:
            show_error(self, "Reports", f"Report '{report_code}' was not found or is inactive.")
            return

        self._current_definition = definition
        self._report_title_label.setText(definition["report_name"])
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._summary_label.setText("")
        self._build_filter_panel(list(definition["applicable_filters"] or []), prefill or {})
        self._run_button.setEnabled(True)

    def _build_filter_panel(self, applicable_filters: list[str], prefill: dict[str, Any]) -> None:
        while self._filter_row_layout.count():
            item = self._filter_row_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._filter_widgets = {}

        for key in applicable_filters:
            widget, kind, checkbox = self._make_filter_widget(key, prefill.get(key))
            self._filter_widgets[key] = (widget, kind, checkbox)

            field_box = QWidget(self._filter_container)
            field_layout = QVBoxLayout(field_box)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(2)

            if checkbox is not None:
                # Optional field (date_from/date_to): the checkbox
                # itself carries the label + on/off toggle, no separate
                # label above it.
                field_layout.addWidget(checkbox)
            else:
                label = QLabel(self._label_for(key), self)
                label.setStyleSheet("font-size: 10px; color: palette(dark);")
                field_layout.addWidget(label)

            field_layout.addWidget(widget)
            self._filter_row_layout.addWidget(field_box)

        self._filter_row_layout.addStretch()

    @staticmethod
    def _label_for(key: str) -> str:
        return key.replace("_", " ").title()

    def _make_filter_widget(self, key: str, prefill_value: Any) -> tuple[QWidget, str, Optional[QCheckBox]]:
        if key in ("date_from", "date_to"):
            date_edit = QDateEdit(self)
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("yyyy-MM-dd")
            date_edit.setFixedWidth(112)
            default = QDate.currentDate().addMonths(-1) if key == "date_from" else QDate.currentDate()
            date_edit.setDate(default)

            # Checkbox makes the date filter genuinely optional: checked
            # (default, matches prior always-applied behavior) sends the
            # date value; unchecked disables the picker and sends None,
            # so run_report() simply won't filter on this date at all
            # (validate_date_range() already allows a missing date_from
            # or date_to -- confirmed, no engine-side change needed).
            checkbox = QCheckBox(self._label_for(key), self)
            checkbox.setChecked(True)
            checkbox.toggled.connect(date_edit.setEnabled)

            return date_edit, "date", checkbox

        if key == "customer_id":
            from engines.customer_engine import search_customers
            customers = search_customers(is_active=True)
            combo = QComboBox(self)
            combo.setMaximumWidth(170)
            populate_searchable_combo(
                combo,
                items=[SimpleNamespace(**c) for c in customers],
                display_attr="customer_name", data_attr="customer_id",
                placeholder="All Customers",
            )
            self._preselect_combo(combo, prefill_value)
            return combo, "combo", None

        if key == "supplier_id" and self._supplier_engine is not None:
            dtos, _total = self._supplier_engine.search_suppliers(page=1, page_size=5000)
            combo = QComboBox(self)
            combo.setMaximumWidth(170)
            populate_searchable_combo(
                combo, items=dtos, display_attr="supplier_name", data_attr="supplier_id",
                placeholder="All Suppliers",
            )
            self._preselect_combo(combo, prefill_value)
            return combo, "combo", None

        if key == "item_id" and self._item_engine is not None:
            dtos, _total = self._item_engine.search_items(page=1, page_size=5000)
            combo = QComboBox(self)
            combo.setMaximumWidth(170)
            populate_searchable_combo(
                combo, items=dtos, display_attr="item_name", data_attr="item_id",
                placeholder="All Items",
            )
            self._preselect_combo(combo, prefill_value)
            return combo, "combo", None

        if key == "status":
            combo = QComboBox(self)
            combo.setMaximumWidth(140)
            combo.addItem("All", None)
            for value in _STATUS_VALUES:
                combo.addItem(value, value)
            self._preselect_combo(combo, prefill_value)
            return combo, "combo", None

        if key == "payment_mode":
            combo = QComboBox(self)
            combo.setMaximumWidth(140)
            combo.addItem("All", None)
            for value in _PAYMENT_MODE_VALUES:
                combo.addItem(value, value)
            self._preselect_combo(combo, prefill_value)
            return combo, "combo", None

        # Fallback for filters without a confirmed lookup source yet
        # (manufacturer_id, batch_id, category_id, etc.) -- a plain
        # numeric-ID text field is a complete, functional filter input,
        # not a placeholder; upgrade to a searchable combo once that
        # module's listing method is confirmed.
        line_edit = QLineEdit(self)
        line_edit.setMaximumWidth(140)
        line_edit.setPlaceholderText(f"{self._label_for(key)} (ID)")
        if prefill_value is not None:
            line_edit.setText(str(prefill_value))
        return line_edit, "text", None

    @staticmethod
    def _preselect_combo(combo: QComboBox, value: Any) -> None:
        if value is None:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _get_filter_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, (widget, kind, checkbox) in self._filter_widgets.items():
            if checkbox is not None and not checkbox.isChecked():
                values[key] = None
                continue
            if kind == "date":
                values[key] = widget.date().toPython()
            elif kind == "combo":
                values[key] = widget.currentData()
            elif kind == "text":
                text = widget.text().strip()
                values[key] = text or None
        return values

    # ------------------------------------------------------------------ #
    # RUN
    # ------------------------------------------------------------------ #
    def _on_run_clicked(self) -> None:
        if self._current_definition is None:
            return
        filters = self._get_filter_values()
        try:
            result = self._engine.run_report(
                self._current_definition["report_code"], filters, self._role_name
            )
        except (ValidationError, RecordNotFoundError) as exc:
            show_error(self, "Reports", str(exc))
            return
        except Exception:
            show_error(self, "Reports", "An unexpected error occurred while running this report.")
            return

        self._last_result = result
        self._render_results_grid(result)

    def _render_results_grid(self, result) -> None:
        columns = result.columns_definition
        rows = result.rows

        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([c["label"] for c in columns])
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, coldef in enumerate(columns):
                text = _format_cell(row.get(coldef["key"]), coldef["type"])
                item = QTableWidgetItem(text)
                if coldef["type"] in ("currency", "number"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)

        totals = []
        for coldef in columns:
            if coldef["type"] == "currency":
                total = sum(float(row.get(coldef["key"]) or 0) for row in rows)
                totals.append(f"{coldef['label']}: {total:,.2f}")
        summary = f"{len(rows)} record(s)"
        if totals:
            summary += "   |   " + "   |   ".join(totals)
        self._summary_label.setText(summary)

    # ------------------------------------------------------------------ #
    # DRILL-DOWN
    # ------------------------------------------------------------------ #
    def _on_row_double_clicked(self, row_index: int, _column: int) -> None:
        if self._current_definition is None or self._last_result is None:
            return
        if row_index >= len(self._last_result.rows):
            return
        row_data = self._last_result.rows[row_index]

        drill_report_code = self._current_definition.get("drill_down_report_code")
        drill_source_type = self._current_definition.get("drill_down_source_type")

        if drill_report_code:
            next_definition = self._engine.get_report_definition(drill_report_code)
            prefill = {}
            if next_definition:
                prefill = {
                    k: v for k, v in row_data.items()
                    if k in (next_definition.get("applicable_filters") or []) and v is not None
                }
            self._nav_stack.append(self._current_definition["report_code"])
            self._drill_back_button.setVisible(True)
            self._on_report_selected(drill_report_code, prefill)
            self._on_run_clicked()
        elif drill_source_type:
            self.drill_down_requested.emit(drill_source_type, dict(row_data))

    def _go_back_one_level(self) -> None:
        if not self._nav_stack:
            self._drill_back_button.setVisible(False)
            return
        previous_code = self._nav_stack.pop()
        self._drill_back_button.setVisible(bool(self._nav_stack))
        self._on_report_selected(previous_code)


__all__ = ["ReportRunnerScreen"]