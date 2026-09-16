"""
Reusable BS (Bikram Sambat) calendar date picker.

Redesigned from the inline classes that previously lived inside
screens/sale_invoice_form_screen.py, following the same reuse pattern as
widgets/expiry_date_picker.py (AD side): a single importable widget that
any screen can embed, instead of duplicating the classes per module.

Conversion goes through engines.date_engine only, matching the AD
picker's convention. This widget only ever holds/emits BS date strings
(YYYY-MM-DD); it never talks to the database directly.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from engines.date_engine import DateEngineError, ad_to_bs, get_bs_month_days

_WEEKDAY_HEADERS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_DAY_BUTTON_SIZE = (30, 32)   # explicit per-button size, not a guessed popup size
_NAV_BUTTON_SIZE = 20
_GRID_ROWS = 6                # always render 6 rows so popup size never jumps month-to-month
_DEFAULT_BS_YEAR = 2082
_DEFAULT_BS_MONTH = 1


class BSCalendarPopup(QDialog):
    """Modal BS month-grid picker.

    Size is never hardcoded: it is computed from the actual widgets via
    Qt's own layout system (setFixedSize(self.sizeHint())), so text can
    never be cramped and the dialog is never bigger than it needs to be.

    Opens anchored to the triggering field (right edge aligned, dropping
    down-left) instead of at the raw cursor position, so it always opens
    on a predictable side like a real dropdown.
    """

    date_selected = Signal(str)

    def __init__(
        self,
        bs_year: int,
        bs_month: int,
        selected_bs_date: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bsCalendarPopup")
        self.setProperty("cssClass", "bsCalendarPopup")
        self.setWindowTitle("Select Date (BS)")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(False)

        self._bs_year = bs_year
        self._bs_month = bs_month
        self._selected_bs_date = selected_bs_date
        try:
            self._today_bs_date = ad_to_bs(date.today())
        except DateEngineError:
            self._today_bs_date = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(3)
        self.btnPrevYear = self._make_nav_button("«", "Previous Year", self._go_prev_year)
        self.btnPrevMonth = self._make_nav_button("‹", "Previous Month", self._go_prev_month)
        self.lblMonthYear = QLabel()
        self.lblMonthYear.setObjectName("lblBsCalendarMonthYear")
        self.lblMonthYear.setProperty("cssClass", "bsCalendarMonthLabel")
        self.lblMonthYear.setAlignment(Qt.AlignCenter)
        self.btnNextMonth = self._make_nav_button("›", "Next Month", self._go_next_month)
        self.btnNextYear = self._make_nav_button("»", "Next Year", self._go_next_year)
        nav_row.addWidget(self.btnPrevYear)
        nav_row.addWidget(self.btnPrevMonth)
        nav_row.addWidget(self.lblMonthYear, 1)
        nav_row.addWidget(self.btnNextMonth)
        nav_row.addWidget(self.btnNextYear)
        root.addLayout(nav_row)

        weekday_row = QHBoxLayout()
        weekday_row.setSpacing(2)
        for header_text in _WEEKDAY_HEADERS:
            lbl = QLabel(header_text)
            lbl.setObjectName("lblBsCalendarWeekday")
            lbl.setProperty("cssClass", "bsCalendarWeekdayLabel")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedWidth(_DAY_BUTTON_SIZE[0])
            weekday_row.addWidget(lbl)
        root.addLayout(weekday_row)

        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        root.addLayout(self.grid)

        self._render_month()

        # Let Qt compute the real required size from the widgets we just
        # built, instead of a hand-picked pixel guess.
        self.setFixedSize(self.sizeHint())

    def _make_nav_button(self, text: str, tooltip: str, handler) -> QToolButton:
        button = QToolButton()
        button.setObjectName(f"btnBsCalendarNav{tooltip.replace(' ', '')}")
        button.setProperty("cssClass", "bsCalendarNavButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(_NAV_BUTTON_SIZE, _NAV_BUTTON_SIZE)
        button.clicked.connect(handler)
        return button

    def _go_prev_month(self) -> None:
        self._bs_month -= 1
        if self._bs_month < 1:
            self._bs_month = 12
            self._bs_year -= 1
        self._render_month()

    def _go_next_month(self) -> None:
        self._bs_month += 1
        if self._bs_month > 12:
            self._bs_month = 1
            self._bs_year += 1
        self._render_month()

    def _go_prev_year(self) -> None:
        self._bs_year -= 1
        self._render_month()

    def _go_next_year(self) -> None:
        self._bs_year += 1
        self._render_month()

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_month(self) -> None:
        self._clear_grid()

        try:
            days = get_bs_month_days(self._bs_year, self._bs_month)
        except Exception:
            days = []

        if not days:
            self.lblMonthYear.setText(f"{self._bs_year}-{self._bs_month:02d} (no data)")
            self._fill_empty_grid()
            return

        self.lblMonthYear.setText(f"{days[0]['monthnameen']} {self._bs_year}")

        first_weekday = days[0]["weekdayno"]
        occupied_cells: set[tuple[int, int]] = set()
        for day_row in days:
            idx = day_row["bsday"] - 1
            col = (first_weekday + idx) % 7
            row = (first_weekday + idx) // 7
            btn = self._make_day_button(day_row, col)
            self.grid.addWidget(btn, row, col)
            occupied_cells.add((row, col))

        # Pad every remaining cell up to a fixed 6-row grid with an
        # invisible placeholder, so the popup's height never changes
        # between a 29-day month and a 32-day month.
        for row in range(_GRID_ROWS):
            for col in range(7):
                if (row, col) not in occupied_cells:
                    placeholder = QLabel("")
                    placeholder.setFixedSize(*_DAY_BUTTON_SIZE)
                    self.grid.addWidget(placeholder, row, col)

    def _fill_empty_grid(self) -> None:
        for row in range(_GRID_ROWS):
            for col in range(7):
                placeholder = QLabel("")
                placeholder.setFixedSize(*_DAY_BUTTON_SIZE)
                self.grid.addWidget(placeholder, row, col)

    def _make_day_button(self, day_row: dict, col: int) -> QPushButton:
        bs_date = day_row["bsdate"]
        btn = QPushButton(str(day_row["bsday"]))
        btn.setObjectName(f"btnBsCalendarDay{day_row['bsday']}")
        btn.setProperty("cssClass", "bsCalendarDayButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(*_DAY_BUTTON_SIZE)

        is_saturday = col == 6  # Nepal's weekly holiday column
        if bs_date == self._selected_bs_date:
            state = "selected"
        elif bs_date == self._today_bs_date:
            state = "today"
        elif day_row["isholiday"] or is_saturday:
            state = "holiday"
        else:
            state = "normal"
        btn.setProperty("dayState", state)

        btn.clicked.connect(lambda _checked, d=bs_date: self._pick(d))
        return btn

    def _pick(self, bs_date: str) -> None:
        self.date_selected.emit(bs_date)
        self.accept()

    def open_left_of(self, anchor_top_right: QPoint) -> None:
        """Opens the popup below the triggering field, with the popup's
        RIGHT edge aligned to ``anchor_top_right`` (the field's top-right
        corner in global coordinates) — so it always drops down-and-left,
        never off to the right, regardless of where inside the field the
        user clicked."""
        target = QPoint(anchor_top_right.x() - self.width(), anchor_top_right.y())

        screen = QGuiApplication.screenAt(anchor_top_right) or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            max_x = available.right() - self.width()
            max_y = available.bottom() - self.height()
            target.setX(min(max(target.x(), available.left()), max_x))
            target.setY(min(max(target.y(), available.top()), max_y))

        self.move(target)
        self.exec()


class BSCalendarDatePicker(QWidget):
    """Single-box BS date field with a calendar popup, backed by the
    bscalendar reference table (query-per-month, no in-code BS math).

    Reusable across modules: Sale Invoice uses it first; later modules
    should import this widget directly instead of duplicating it, the
    same way widgets/expiry_date_picker.py is reused for AD dates.
    """

    date_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("bsCalendarDatePicker")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.date_display = QLineEdit()
        self.date_display.setObjectName("txtBsDate")
        self.date_display.setProperty("cssClass", "dateFieldInput")
        self.date_display.setReadOnly(True)
        self.date_display.setPlaceholderText("Select date")
        self.date_display.setCursor(Qt.PointingHandCursor)

        self.calendar_button = QToolButton()
        self.calendar_button.setObjectName("btnBsCalendar")
        self.calendar_button.setProperty("cssClass", "dateFieldButton")
        self.calendar_button.setText("📅")
        self.calendar_button.setCursor(Qt.PointingHandCursor)
        self.calendar_button.setToolTip("Open BS Calendar")
        self.calendar_button.clicked.connect(self._open_calendar_popup)

        layout.addWidget(self.date_display, 1)
        layout.addWidget(self.calendar_button)

        self._selected_bs_date = ""
        try:
            self._set_bs_date(ad_to_bs(date.today()))
        except DateEngineError:
            pass

    def _set_bs_date(self, bs_date_text: str) -> None:
        self._selected_bs_date = bs_date_text
        self.date_display.setText(bs_date_text)
        self.date_changed.emit(bs_date_text)

    def get_bs_date_string(self) -> str:
        return self._selected_bs_date

    def set_bs_date_string(self, bs_date_text: str) -> None:
        """Loads an existing BS date into the picker (Edit mode)."""
        self._set_bs_date(bs_date_text)

    def _open_calendar_popup(self) -> None:
        if self._selected_bs_date:
            year, month, _day = (int(part) for part in self._selected_bs_date.split("-"))
        else:
            year, month = _DEFAULT_BS_YEAR, _DEFAULT_BS_MONTH

        popup = BSCalendarPopup(year, month, self._selected_bs_date, self)
        popup.date_selected.connect(self._set_bs_date)

        # Anchor = top-right corner of this whole field (input + button),
        # in global screen coordinates, so the popup drops down-left of it.
        anchor_top_right = self.mapToGlobal(QPoint(self.width(), self.height()))
        popup.open_left_of(anchor_top_right)


__all__ = ["BSCalendarDatePicker", "BSCalendarPopup"]