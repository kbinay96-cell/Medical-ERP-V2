"""
screens/management_dashboard_screen.py

Management Dashboard Screen - Medical ERP V2

The Reports module's own landing page. Renders every active
management_dashboard_widget row (KPI / List / Trend) grouped by type.
Screen layer only -- no SQL, no business logic; ReportEngine.
get_management_dashboard() already does all query execution.

KPI/List/Trend "data" row shape is a convention this screen and the
seed migration (database/migrations/0033_seed_management_dashboard_
widgets.sql) agree on together, since management_dashboard_widget has
no columns_definition (unlike report_definition):
    - KPI:   exactly one row, single "value" key.
    - List:  N rows, arbitrary keys -- rendered as a generic table,
             column headers derived from the row's own keys.
    - Trend: N rows, "period" (label) + "value" (number) keys.

Dashboard-tile-to-report drill-through: management_dashboard_widget
has no drill-down column of its own, so _WIDGET_DRILL_DOWN below is a
screen-level lookup (same pattern as report_runner_screen.py's
_CATEGORY_GROUPS), not a schema feature. A widget_code not listed here
simply isn't clickable.

Gross Profit / Net Profit / Cash / Bank KPIs are intentionally NOT
seeded/rendered -- they require chart_of_accounts/journal_entry, part
of the not-yet-started Accounts module. Nothing here fakes that data.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis

from engines.report_engine import ReportEngine

_WIDGET_DRILL_DOWN: dict[str, str] = {
    "RECEIVABLE": "CUSTOMER_OUTSTANDING",
    "PAYABLE": "SUPPLIER_OUTSTANDING",
    "EXPIRED_STOCK_VALUE": "EXPIRED_ITEMS",
}

_GRID_COLUMNS = 2

_LIST_VISIBLE_ROWS = 10   
_LIST_ROW_HEIGHT = 18    


def _format_currency(value: Any) -> str:
    if value is None:
        return "0.00"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:,.2f}" if isinstance(value, float) else str(value)
    return str(value)


class _ClickableFrame(QFrame):
    """QFrame that emits `clicked` on a left mouse press -- proper
    subclass override, not an instance-level mousePressEvent patch
    (which Qt's virtual dispatch does not reliably honor)."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.clicked.emit()
        super().mousePressEvent(event)


class ManagementDashboardScreen(QWidget):
    close_requested = Signal()
    open_report_requested = Signal(str)   # report_code -- parent opens ReportRunnerScreen with this

    def __init__(self, parent, engine: ReportEngine, embedded: bool = False) -> None:
        super().__init__(parent)
        self._engine = engine
        self._embedded = embedded

        self.setWindowTitle("Management Dashboard")
        self.setMinimumSize(1200, 700)

        root = QVBoxLayout(self)

        if self._embedded:
            top_row = QHBoxLayout()
            btn_back_page = QPushButton("← Back", self)
            btn_back_page.clicked.connect(self.close_requested.emit)
            top_row.addWidget(btn_back_page)
            top_row.addStretch()
            root.addLayout(top_row)

        header_row = QHBoxLayout()
        title = QLabel("Management Dashboard", self)
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_row.addWidget(title)
        header_row.addStretch()

        self._period_combo = QComboBox(self)
        self._period_combo.addItem("This Month", "this_month")
        self._period_combo.addItem("Custom Range", "custom")
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        header_row.addWidget(self._period_combo)

        self._date_from_edit = QDateEdit(self)
        self._date_from_edit.setCalendarPopup(True)
        self._date_from_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_from_edit.setVisible(False)
        header_row.addWidget(self._date_from_edit)

        self._date_to_edit = QDateEdit(self)
        self._date_to_edit.setCalendarPopup(True)
        self._date_to_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_to_edit.setVisible(False)
        header_row.addWidget(self._date_to_edit)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setVisible(False)
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        header_row.addWidget(self._refresh_button)

        root.addLayout(header_row)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        kpi_label = QLabel("Overview", self)
        kpi_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        content_layout.addWidget(kpi_label)
        self._kpi_row_layout = QHBoxLayout()
        content_layout.addLayout(self._kpi_row_layout)

        list_label = QLabel("Top Lists", self)
        list_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        content_layout.addWidget(list_label)
        self._list_grid_layout = QGridLayout()
        content_layout.addLayout(self._list_grid_layout)
        self._list_grid_row = 0
        self._list_grid_col = 0
        # widget_code -> True when the user collapsed that List table. Kept
        # across refresh() so a rebuild (period change / Refresh) does not
        # re-open tables the user hid.
        self._list_collapsed: dict[str, bool] = {}

        trend_label = QLabel("Trends", self)
        trend_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        content_layout.addWidget(trend_label)
        # Trends are stacked in a single full-width column (one chart per row).
        self._trend_layout = QVBoxLayout()
        content_layout.addLayout(self._trend_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        self._apply_this_month_and_refresh()

    # ------------------------------------------------------------------ #
    # PERIOD SELECTOR
    # ------------------------------------------------------------------ #
    def _on_period_changed(self, _index: int) -> None:
        is_custom = self._period_combo.currentData() == "custom"
        self._date_from_edit.setVisible(is_custom)
        self._date_to_edit.setVisible(is_custom)
        self._refresh_button.setVisible(is_custom)
        if not is_custom:
            self._apply_this_month_and_refresh()

    def _apply_this_month_and_refresh(self) -> None:
        today = QDate.currentDate()
        first_of_month = QDate(today.year(), today.month(), 1)
        self._date_from_edit.setDate(first_of_month)
        self._date_to_edit.setDate(today)
        self.refresh({"date_from": first_of_month.toPython(), "date_to": today.toPython()})

    def _on_refresh_clicked(self) -> None:
        self.refresh({
            "date_from": self._date_from_edit.date().toPython(),
            "date_to": self._date_to_edit.date().toPython(),
        })

    # ------------------------------------------------------------------ #
    # RENDER
    # ------------------------------------------------------------------ #
    def refresh(self, filters: dict[str, Any]) -> None:
        results = self._engine.get_management_dashboard(filters)
        self._clear_sections()
        for widget in results:
            if widget["widget_type"] == "KPI":
                self._render_kpi_tile(widget)
            elif widget["widget_type"] == "List":
                self._render_list_widget(widget)
            elif widget["widget_type"] == "Trend":
                self._render_trend_chart(widget)

    def _clear_sections(self) -> None:
        for layout in (self._kpi_row_layout, self._list_grid_layout, self._trend_layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._list_grid_row = 0
        self._list_grid_col = 0

    def _advance_list_grid_position(self) -> None:
        self._list_grid_col += 1
        if self._list_grid_col >= _GRID_COLUMNS:
            self._list_grid_col = 0
            self._list_grid_row += 1

    def _render_kpi_tile(self, widget: dict[str, Any]) -> None:
        rows = widget["data"]
        value = rows[0].get("value") if rows else None
        report_code = _WIDGET_DRILL_DOWN.get(widget["widget_code"])

        tile = _ClickableFrame(self)
        tile.setFrameShape(QFrame.Shape.StyledPanel)
        tile.setMinimumWidth(180)
        tile.setStyleSheet(
            "QFrame { border: 1px solid palette(mid); border-radius: 8px; padding: 10px; }"
        )
        tile_layout = QVBoxLayout(tile)
        value_label = QLabel(_format_currency(value), tile)
        value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        name_label = QLabel(widget["widget_name"], tile)
        name_label.setStyleSheet("font-size: 11px; color: palette(dark);")
        tile_layout.addWidget(value_label)
        tile_layout.addWidget(name_label)

        if report_code:
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.clicked.connect(lambda code=report_code: self.open_report_requested.emit(code))

        self._kpi_row_layout.addWidget(tile)

    def _render_list_widget(self, widget: dict[str, Any]) -> None:
        rows = widget["data"]
        widget_code = widget["widget_code"]
        container = QFrame(self)
        container_layout = QVBoxLayout(container)

        title_row = QHBoxLayout()
        title = QLabel(widget["widget_name"], container)
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        title_row.addWidget(title)
        title_row.addStretch()
        toggle_button = QPushButton(container)
        toggle_button.setFlat(True)
        toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        title_row.addWidget(toggle_button)
        container_layout.addLayout(title_row)

        table = QTableWidget(container)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setDefaultSectionSize(_LIST_ROW_HEIGHT)
        if rows:
            columns = list(rows[0].keys())
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels([c.replace("_", " ").title() for c in columns])
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, key in enumerate(columns):
                    table.setItem(r, c, QTableWidgetItem(_format_cell(row.get(key))))
        # Fixed height = header + _LIST_VISIBLE_ROWS rows + frame. A fixed
        # height (not just a max) stops the scroll-area layout from squashing
        # the table; the page scrolls instead.
        table.setFixedHeight(
            table.horizontalHeader().sizeHint().height()
            + _LIST_ROW_HEIGHT * _LIST_VISIBLE_ROWS
            + table.frameWidth() * 2
        )
        container_layout.addWidget(table)

        def _apply_state() -> None:
            collapsed = self._list_collapsed.get(widget_code, False)
            table.setVisible(not collapsed)
            toggle_button.setText("Show More ▼" if collapsed else "Show Less ▲")

        def _toggle(_checked: bool = False) -> None:
            self._list_collapsed[widget_code] = not self._list_collapsed.get(widget_code, False)
            _apply_state()

        toggle_button.clicked.connect(_toggle)
        _apply_state()

        self._list_grid_layout.addWidget(container, self._list_grid_row, self._list_grid_col)
        self._advance_list_grid_position()

    def _render_trend_chart(self, widget: dict[str, Any]) -> None:
        rows = widget["data"]
        bar_set = QBarSet(widget["widget_name"])
        categories: list[str] = []
        for row in rows:
            bar_set.append(float(row.get("value") or 0))
            categories.append(str(row.get("period", "")))

        series = QBarSeries()
        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(widget["widget_name"])
        chart.legend().hide()

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart_view = QChartView(chart, self)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(220)
        chart_view.setMaximumHeight(260)

        self._trend_layout.addWidget(chart_view)


__all__ = ["ManagementDashboardScreen"]