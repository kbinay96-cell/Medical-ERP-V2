"""
Unified expiry date picker (month/year) with AD/BS toggle.

Conversion goes through engines.date_engine only. The database still stores
AD expiry_month + expiry_year (packaging convention).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from engines.date_engine import DateEngineError, ad_to_bs, get_month_name


def _qdate_to_date(qdate: QDate) -> date:
    return date(qdate.year(), qdate.month(), qdate.day())

AD_MONTHS = [
    "01 - January", "02 - February", "03 - March", "04 - April",
    "05 - May", "06 - June", "07 - July", "08 - August",
    "09 - September", "10 - October", "11 - November", "12 - December",
]


class ExpiryDatePicker(QFrame):
    """Single container: calendar popup + AD/BS mode, exposing AD month/year."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("expiryDatePicker")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Calendar:"))
        self.cmbMode = QComboBox()
        self.cmbMode.addItem("AD", "AD")
        self.cmbMode.addItem("BS", "BS")
        self.cmbMode.setToolTip("BS dates convert through the Date Engine; stored expiry is AD month/year.")
        mode_row.addWidget(self.cmbMode, 1)
        root.addLayout(mode_row)

        picker_row = QHBoxLayout()
        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDisplayFormat("MM/yyyy")
        self.dateEdit.setDate(QDate.currentDate().addYears(1))
        picker_row.addWidget(self.dateEdit, 1)
        root.addLayout(picker_row)

        self.lblConverted = QLabel("")
        self.lblConverted.setStyleSheet("color: #7A8599;")
        self.lblConverted.setWordWrap(True)
        root.addWidget(self.lblConverted)

        self.cmbMode.currentIndexChanged.connect(self._refresh_converted_label)
        self.dateEdit.dateChanged.connect(self._refresh_converted_label)
        self._refresh_converted_label()

    def _refresh_converted_label(self) -> None:
        ad_date = _qdate_to_date(self.dateEdit.date())
        mode = self.cmbMode.currentData()
        if mode == "BS":
            try:
                bs_text = ad_to_bs(ad_date)
                year, month, _day = (int(p) for p in bs_text.split("-"))
                self.lblConverted.setText(f"BS: {get_month_name(month)} {year}  ({bs_text[:7]})")
                self.dateEdit.setDisplayFormat("yyyy-MM-dd")
            except DateEngineError as exc:
                self.lblConverted.setText(f"BS conversion unavailable: {exc}")
                self.dateEdit.setDisplayFormat("MM/yyyy")
        else:
            self.dateEdit.setDisplayFormat("MM/yyyy")
            try:
                bs_text = ad_to_bs(ad_date)
                self.lblConverted.setText(f"AD {ad_date.strftime('%m/%Y')}  ·  BS {bs_text}")
            except DateEngineError:
                self.lblConverted.setText(f"AD {ad_date.strftime('%m/%Y')}")

    def set_month_year(self, month: int, year: int) -> None:
        day = min(self.dateEdit.date().day(), 28)
        self.dateEdit.setDate(QDate(int(year), int(month), day))
        self.cmbMode.setCurrentIndex(0)
        self._refresh_converted_label()

    def expiry_month_year_ad(self) -> tuple[int, int]:
        """Always returns AD (month, year) for ItemEngine.add_batch()."""
        qdate = self.dateEdit.date()
        return qdate.month(), qdate.year()

    def set_expiry_month_year_ad(self, month: int, year: int) -> None:
        """Loads an existing AD (month, year) into the picker (Edit mode)."""
        self.dateEdit.setDate(QDate(year, month, 1))
        self._refresh_converted_label()

    def expiry_month_text(self) -> str:
        month, _year = self.expiry_month_year_ad()
        return str(month)

    def expiry_year_text(self) -> str:
        _month, year = self.expiry_month_year_ad()
        return str(year)


__all__ = ["ExpiryDatePicker", "AD_MONTHS"]
