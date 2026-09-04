# -*- coding: utf-8 -*-
"""
ui/ui_manufacturer_list.py

Generated-style module for ui/manufacturer_list.ui. Same honest-limitation
note as ui/ui_manufacturer_form.py -- regenerate for real with:

    pyside6-uic ui/manufacturer_list.ui -o ui/ui_manufacturer_list.py
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


class Ui_ManufacturerListWidget(object):
    def setupUi(self, ManufacturerListWidget):
        ManufacturerListWidget.setObjectName("ManufacturerListWidget")
        ManufacturerListWidget.resize(900, 600)
        ManufacturerListWidget.setWindowTitle("Manufacturer Master")

        self.verticalLayoutRoot = QVBoxLayout(ManufacturerListWidget)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(12, 12, 12, 12)

        self.lblTitle = QLabel(ManufacturerListWidget)
        self.lblTitle.setObjectName("lblTitle")
        font = self.lblTitle.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lblTitle.setFont(font)
        self.lblTitle.setText("Manufacturer Master")
        self.verticalLayoutRoot.addWidget(self.lblTitle)

        # ---------------- Toolbar ----------------
        self.frmToolbar = QFrame(ManufacturerListWidget)
        self.frmToolbar.setObjectName("frmToolbar")
        self.frmToolbar.setFrameShape(QFrame.StyledPanel)
        self.horizontalLayoutToolbar = QHBoxLayout(self.frmToolbar)
        self.horizontalLayoutToolbar.setObjectName("horizontalLayoutToolbar")

        self.lblSearch = QLabel("Search:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frmToolbar)
        self.txtSearch.setObjectName("txtSearch")
        self.txtSearch.setPlaceholderText("Search by Code, Name, Short Name or Country...")
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip("Search Manufacturers (Ctrl+F)")
        self.horizontalLayoutToolbar.addWidget(self.txtSearch)

        self.lblStatusFilter = QLabel("Status:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblStatusFilter)

        self.cmbStatusFilter = QComboBox(self.frmToolbar)
        self.cmbStatusFilter.setObjectName("cmbStatusFilter")
        self.cmbStatusFilter.setToolTip("Filter manufacturers by status")
        self.cmbStatusFilter.addItems(["All", "Active", "Inactive"])
        self.horizontalLayoutToolbar.addWidget(self.cmbStatusFilter)

        self.chkShowDeleted = QCheckBox("Show Deleted", self.frmToolbar)
        self.chkShowDeleted.setObjectName("chkShowDeleted")
        self.chkShowDeleted.setToolTip("Include soft-deleted manufacturers (needed to Restore one)")
        self.horizontalLayoutToolbar.addWidget(self.chkShowDeleted)

        self.horizontalSpacerToolbar = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutToolbar.addItem(self.horizontalSpacerToolbar)

        self.btnRefresh = QPushButton("Refresh", self.frmToolbar)
        self.btnRefresh.setObjectName("btnRefresh")
        self.btnRefresh.setToolTip("Reload manufacturer list (F5)")
        self.horizontalLayoutToolbar.addWidget(self.btnRefresh)

        self.verticalLayoutRoot.addWidget(self.frmToolbar)

        # ---------------- Table ----------------
        self.tblManufacturer = QTableWidget(ManufacturerListWidget)
        self.tblManufacturer.setObjectName("tblManufacturer")
        self.tblManufacturer.setColumnCount(4)
        self.tblManufacturer.setHorizontalHeaderLabels(
            ["Code", "Manufacturer Name", "Country", "Status"]
        )
        self.tblManufacturer.setAlternatingRowColors(True)
        self.tblManufacturer.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblManufacturer.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblManufacturer.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblManufacturer.setSortingEnabled(True)
        self.tblManufacturer.horizontalHeader().setStretchLastSection(True)
        self.verticalLayoutRoot.addWidget(self.tblManufacturer)

        self.lblRecordCount = QLabel("0 manufacturer(s) found", ManufacturerListWidget)
        self.lblRecordCount.setObjectName("lblRecordCount")
        self.lblRecordCount.setStyleSheet("color: #666666;")
        self.verticalLayoutRoot.addWidget(self.lblRecordCount)

        # ---------------- Action buttons ----------------
        self.horizontalLayoutButtons = QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")

        self.btnAdd = QPushButton("Add Manufacturer", ManufacturerListWidget)
        self.btnAdd.setObjectName("btnAdd")
        self.btnAdd.setToolTip("Add a new manufacturer (Ctrl+N)")
        self.horizontalLayoutButtons.addWidget(self.btnAdd)

        self.btnEdit = QPushButton("Edit", ManufacturerListWidget)
        self.btnEdit.setObjectName("btnEdit")
        self.btnEdit.setToolTip("Edit the selected manufacturer (Enter)")
        self.horizontalLayoutButtons.addWidget(self.btnEdit)

        self.btnDelete = QPushButton("Delete", ManufacturerListWidget)
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setToolTip("Soft-delete the selected manufacturer (Del)")
        self.horizontalLayoutButtons.addWidget(self.btnDelete)

        self.btnRestore = QPushButton("Restore", ManufacturerListWidget)
        self.btnRestore.setObjectName("btnRestore")
        self.btnRestore.setToolTip("Restore the selected deleted manufacturer")
        self.btnRestore.setEnabled(False)
        self.horizontalLayoutButtons.addWidget(self.btnRestore)

        self.horizontalSpacerButtons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutButtons.addItem(self.horizontalSpacerButtons)

        self.btnClose = QPushButton("Close", ManufacturerListWidget)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setToolTip("Close this screen (Esc)")
        self.horizontalLayoutButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutButtons)
