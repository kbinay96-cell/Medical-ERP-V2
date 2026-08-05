# -*- coding: utf-8 -*-
"""
ui/ui_country_tax_list.py

Generated-style module for ui/country_tax_list.ui. Same honest-limitation
note as ui/ui_manufacturer_list.py -- regenerate for real with:

    pyside6-uic ui/country_tax_list.ui -o ui/ui_country_tax_list.py
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QVBoxLayout,
)


class Ui_CountryTaxListWidget(object):
    def setupUi(self, CountryTaxListWidget):
        CountryTaxListWidget.setObjectName("CountryTaxListWidget")
        CountryTaxListWidget.resize(900, 600)
        CountryTaxListWidget.setWindowTitle("Country Tax Settings")

        self.verticalLayoutRoot = QVBoxLayout(CountryTaxListWidget)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(12, 12, 12, 12)

        self.lblTitle = QLabel(CountryTaxListWidget)
        self.lblTitle.setObjectName("lblTitle")
        font = self.lblTitle.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lblTitle.setFont(font)
        self.lblTitle.setText("Country Tax Settings")
        self.verticalLayoutRoot.addWidget(self.lblTitle)

        # ---------------- Toolbar ----------------
        self.frmToolbar = QFrame(CountryTaxListWidget)
        self.frmToolbar.setObjectName("frmToolbar")
        self.frmToolbar.setFrameShape(QFrame.StyledPanel)
        self.horizontalLayoutToolbar = QHBoxLayout(self.frmToolbar)
        self.horizontalLayoutToolbar.setObjectName("horizontalLayoutToolbar")

        self.lblSearch = QLabel("Search:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frmToolbar)
        self.txtSearch.setObjectName("txtSearch")
        self.txtSearch.setPlaceholderText("Search by Country or Remarks...")
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip("Search Country Tax Settings (Ctrl+F)")
        self.horizontalLayoutToolbar.addWidget(self.txtSearch)

        self.lblStatusFilter = QLabel("Status:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblStatusFilter)

        self.cmbStatusFilter = QComboBox(self.frmToolbar)
        self.cmbStatusFilter.setObjectName("cmbStatusFilter")
        self.cmbStatusFilter.setToolTip("Filter by status")
        self.cmbStatusFilter.addItems(["All", "Active", "Inactive"])
        self.horizontalLayoutToolbar.addWidget(self.cmbStatusFilter)

        self.chkShowDeleted = QCheckBox("Show Deleted", self.frmToolbar)
        self.chkShowDeleted.setObjectName("chkShowDeleted")
        self.chkShowDeleted.setToolTip("Include soft-deleted rows (needed to Restore one)")
        self.horizontalLayoutToolbar.addWidget(self.chkShowDeleted)

        self.horizontalSpacerToolbar = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutToolbar.addItem(self.horizontalSpacerToolbar)

        self.btnRefresh = QPushButton("Refresh", self.frmToolbar)
        self.btnRefresh.setObjectName("btnRefresh")
        self.btnRefresh.setToolTip("Reload list (F5)")
        self.horizontalLayoutToolbar.addWidget(self.btnRefresh)

        self.verticalLayoutRoot.addWidget(self.frmToolbar)

        # ---------------- Table ----------------
        self.tblCountryTax = QTableWidget(CountryTaxListWidget)
        self.tblCountryTax.setObjectName("tblCountryTax")
        self.tblCountryTax.setColumnCount(4)
        self.tblCountryTax.setHorizontalHeaderLabels(
            ["Country", "VAT %", "Custom %", "Status"]
        )
        self.tblCountryTax.setAlternatingRowColors(True)
        self.tblCountryTax.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblCountryTax.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblCountryTax.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblCountryTax.setSortingEnabled(True)
        self.tblCountryTax.horizontalHeader().setStretchLastSection(True)
        self.verticalLayoutRoot.addWidget(self.tblCountryTax)

        self.lblRecordCount = QLabel("0 record(s) found", CountryTaxListWidget)
        self.lblRecordCount.setObjectName("lblRecordCount")
        self.lblRecordCount.setStyleSheet("color: #666666;")
        self.verticalLayoutRoot.addWidget(self.lblRecordCount)

        # ---------------- Action buttons ----------------
        self.horizontalLayoutButtons = QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")

        self.btnAdd = QPushButton("Add Country Tax", CountryTaxListWidget)
        self.btnAdd.setObjectName("btnAdd")
        self.btnAdd.setToolTip("Add a new country tax setting (Ctrl+N)")
        self.horizontalLayoutButtons.addWidget(self.btnAdd)

        self.btnEdit = QPushButton("Edit", CountryTaxListWidget)
        self.btnEdit.setObjectName("btnEdit")
        self.btnEdit.setToolTip("Edit the selected row (Enter)")
        self.horizontalLayoutButtons.addWidget(self.btnEdit)

        self.btnDelete = QPushButton("Delete", CountryTaxListWidget)
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setToolTip("Soft-delete the selected row (Del)")
        self.horizontalLayoutButtons.addWidget(self.btnDelete)

        self.btnRestore = QPushButton("Restore", CountryTaxListWidget)
        self.btnRestore.setObjectName("btnRestore")
        self.btnRestore.setToolTip("Restore the selected deleted row")
        self.btnRestore.setEnabled(False)
        self.horizontalLayoutButtons.addWidget(self.btnRestore)

        self.horizontalSpacerButtons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutButtons.addItem(self.horizontalSpacerButtons)

        self.btnClose = QPushButton("Close", CountryTaxListWidget)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setToolTip("Close this screen (Esc)")
        self.horizontalLayoutButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutButtons)
