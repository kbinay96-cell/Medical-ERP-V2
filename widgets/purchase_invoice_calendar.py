from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QHBoxLayout,
    QToolButton,
    QWidget,
)


class PurchaseInvoiceCalendar(QCalendarWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("purchaseInvoiceCalendar")
        self.setNavigationBarVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setGridVisible(True)
        self.setFixedSize(248, 210)

        navigation = QWidget(self)
        navigation.setObjectName("purchaseCalendarNavigation")
        layout = QHBoxLayout(navigation)
        layout.setContentsMargins(2, 3, 2, 4)
        layout.setSpacing(2)

        self.previous_month_button = self._make_navigation_button(
            "<", "Previous month", lambda: self._shift_page(months=-1)
        )
        self.month_combo = QComboBox(navigation)
        self.month_combo.setObjectName("purchaseCalendarMonth")
        self.month_combo.setFixedWidth(120)
        for month in range(1, 13):
            self.month_combo.addItem(QDate(2000, month, 1).toString("MMMM"), month)

        self.year_combo = QComboBox(navigation)
        self.year_combo.setObjectName("purchaseCalendarYear")
        self.year_combo.setFixedWidth(56)
        current_year = QDate.currentDate().year()
        self.year_combo.addItems(
            [str(year) for year in range(1900, max(2101, current_year + 21))]
        )

        self.next_month_button = self._make_navigation_button(
            ">", "Next month", lambda: self._shift_page(months=1)
        )
        for widget in (
            self.previous_month_button,
            self.month_combo,
            self.year_combo,
            self.next_month_button,
        ):
            layout.addWidget(widget)

        self.layout().insertWidget(0, navigation)
        self.month_combo.currentIndexChanged.connect(self._set_page_from_controls)
        self.year_combo.currentIndexChanged.connect(self._set_page_from_controls)
        self.currentPageChanged.connect(self._sync_page_controls)
        self._sync_page_controls(self.yearShown(), self.monthShown())

    def _make_navigation_button(
        self,
        text: str,
        tooltip: str,
        callback,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("purchaseCalendarNavigationButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(16, 24)
        button.clicked.connect(callback)
        return button

    def _set_page_from_controls(self) -> None:
        month = self.month_combo.currentData()
        year_text = self.year_combo.currentText()
        if month is not None and year_text.isdigit():
            self.setCurrentPage(int(year_text), int(month))

    def _sync_page_controls(self, year: int, month: int) -> None:
        month_index = self.month_combo.findData(month)
        if month_index >= 0 and self.month_combo.currentIndex() != month_index:
            self.month_combo.blockSignals(True)
            self.month_combo.setCurrentIndex(month_index)
            self.month_combo.blockSignals(False)

        year_text = str(year)
        year_index = self.year_combo.findText(year_text)
        if year_index < 0:
            self.year_combo.addItem(year_text)
            year_index = self.year_combo.findText(year_text)
        if self.year_combo.currentIndex() != year_index:
            self.year_combo.blockSignals(True)
            self.year_combo.setCurrentIndex(year_index)
            self.year_combo.blockSignals(False)

    def _shift_page(self, months: int = 0, years: int = 0) -> None:
        page = QDate(self.yearShown(), self.monthShown(), 1)
        target_page = page.addMonths(months).addYears(years)
        self.setCurrentPage(target_page.year(), target_page.month())


__all__ = ["PurchaseInvoiceCalendar"]
