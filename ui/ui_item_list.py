# -*- coding: utf-8 -*-
"""
ui/ui_item_list.py

Generated-style form module for ui/item_list.ui. Same honest limitation as
ui_supplier_list.py -- hand-written to match pyside6-uic's expected output;
regenerate for real with:

    pyside6-uic ui/item_list.ui -o ui/ui_item_list.py
"""

from PySide6.QtCore import Qt
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
    QWidget,
)


class Ui_ItemListWidget(object):
    def setupUi(self, ItemListWidget):
        ItemListWidget.setObjectName("ItemListWidget")
        ItemListWidget.resize(1150, 650)
        ItemListWidget.setWindowTitle("Item Master")

        self.verticalLayoutRoot = QVBoxLayout(ItemListWidget)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(12, 12, 12, 12)

        
        # ---- Row 1: Title + Filters (plain text, no box) ----
        self.frmToolbar = QFrame(ItemListWidget)
        self.frmToolbar.setObjectName("frmToolbar")
        self.frmToolbar.setFrameShape(QFrame.NoFrame)
        self.horizontalLayoutToolbar = QHBoxLayout(self.frmToolbar)
        self.horizontalLayoutToolbar.setObjectName("horizontalLayoutToolbar")

        self.lblTitle = QLabel(self.frmToolbar)
        self.lblTitle.setObjectName("lblTitle")
        font = self.lblTitle.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lblTitle.setFont(font)
        self.lblTitle.setText("Item Master")
        self.horizontalLayoutToolbar.addWidget(self.lblTitle)

        self.lblCategoryFilter = QLabel("Category:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblCategoryFilter)
        self.cmbCategoryFilter = QComboBox(self.frmToolbar)
        self.cmbCategoryFilter.setObjectName("cmbCategoryFilter")
        self.cmbCategoryFilter.setMinimumWidth(150)
        self.cmbCategoryFilter.setMinimumHeight(30)
        self.horizontalLayoutToolbar.addWidget(self.cmbCategoryFilter)

        self.lblManufacturerFilter = QLabel("Manufacturer:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblManufacturerFilter)
        self.cmbManufacturerFilter = QComboBox(self.frmToolbar)
        self.cmbManufacturerFilter.setObjectName("cmbManufacturerFilter")
        self.cmbManufacturerFilter.setMinimumWidth(150)
        self.cmbManufacturerFilter.setMinimumHeight(30)
        self.horizontalLayoutToolbar.addWidget(self.cmbManufacturerFilter)

        self.lblStatusFilter = QLabel("Status:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblStatusFilter)
        self.cmbStatusFilter = QComboBox(self.frmToolbar)
        self.cmbStatusFilter.setObjectName("cmbStatusFilter")
        self.cmbStatusFilter.addItems(["All", "Active", "Inactive"])
        self.cmbStatusFilter.setMinimumWidth(120)
        self.cmbStatusFilter.setMinimumHeight(30)
        self.horizontalLayoutToolbar.addWidget(self.cmbStatusFilter)

        self.chkShowDeleted = QCheckBox("Show Deleted", self.frmToolbar)
        self.chkShowDeleted.setObjectName("chkShowDeleted")
        self.horizontalLayoutToolbar.addWidget(self.chkShowDeleted)

        self.horizontalSpacerToolbar = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutToolbar.addItem(self.horizontalSpacerToolbar)

        self.btnRefresh = QPushButton("Refresh", self.frmToolbar)
        self.btnRefresh.setObjectName("btnRefresh")
        self.btnRefresh.setToolTip("Reload item list (F5)")
        self.horizontalLayoutToolbar.addWidget(self.btnRefresh)

        self.verticalLayoutRoot.addWidget(self.frmToolbar)

        # ---- Row 2: Search only (bigger, standalone) ----
        self.frmSearchBar = QFrame(ItemListWidget)
        self.frmSearchBar.setObjectName("frmSearchBar")
        self.frmSearchBar.setFrameShape(QFrame.NoFrame)
        self.horizontalLayoutSearchBar = QHBoxLayout(self.frmSearchBar)
        self.horizontalLayoutSearchBar.setObjectName("horizontalLayoutSearchBar")

        self.lblSearch = QLabel("Search:", self.frmSearchBar)
        self.horizontalLayoutSearchBar.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frmSearchBar)
        self.txtSearch.setObjectName("txtSearch")
        self.txtSearch.setPlaceholderText("Search by Code or Name...")
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip("Search Items (Ctrl+F)")
        self.txtSearch.setMinimumHeight(32)
        self.horizontalLayoutSearchBar.addWidget(self.txtSearch, 1)

        self.verticalLayoutRoot.addWidget(self.frmSearchBar)

        self.tblItem = QTableWidget(ItemListWidget)
        self.tblItem.setObjectName("tblItem")
        self.tblItem.setColumnCount(11)
        self.tblItem.setHorizontalHeaderLabels([
            "Code", "Item Name", "Expiry", "Batch", "Unit",
            "Purchase Rate", "Sale Rate", "MRP",
            "Total Stock", "Min. Stock", "Status",
        ])
        self.tblItem.setAlternatingRowColors(True)
        self.tblItem.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblItem.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblItem.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblItem.setSortingEnabled(True)
        self.tblItem.horizontalHeader().setStretchLastSection(True)
        self.tblItem.verticalHeader().setVisible(False)
        self.verticalLayoutRoot.addWidget(self.tblItem)

        self.lblRecordCount = QLabel("0 item(s) found", ItemListWidget)
        self.lblRecordCount.setObjectName("lblRecordCount")
        self.lblRecordCount.setStyleSheet("color: #666666;")
        self.verticalLayoutRoot.addWidget(self.lblRecordCount)

        self.horizontalLayoutButtons = QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")

        self.btnAdd = QPushButton("Add Item", ItemListWidget)
        self.btnAdd.setObjectName("btnAdd")
        self.btnAdd.setToolTip("Add a new item (Ctrl+N)")
        self.horizontalLayoutButtons.addWidget(self.btnAdd)

        self.btnEdit = QPushButton("Edit", ItemListWidget)
        self.btnEdit.setObjectName("btnEdit")
        self.btnEdit.setToolTip("Edit the selected item (Enter)")
        self.horizontalLayoutButtons.addWidget(self.btnEdit)

        self.btnDelete = QPushButton("Delete", ItemListWidget)
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setToolTip("Soft-delete the selected item (Del)")
        self.horizontalLayoutButtons.addWidget(self.btnDelete)

        self.btnRestore = QPushButton("Restore", ItemListWidget)
        self.btnRestore.setObjectName("btnRestore")
        self.btnRestore.setToolTip("Restore the selected deleted item")
        self.btnRestore.setEnabled(False)
        self.horizontalLayoutButtons.addWidget(self.btnRestore)

        self.horizontalSpacerButtons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutButtons.addItem(self.horizontalSpacerButtons)

        self.btnClose = QPushButton("Close", ItemListWidget)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setToolTip("Close this screen (Esc)")
        self.horizontalLayoutButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutButtons)

        ItemListWidget.setTabOrder(self.txtSearch, self.cmbCategoryFilter)
        ItemListWidget.setTabOrder(self.cmbCategoryFilter, self.cmbManufacturerFilter)
        ItemListWidget.setTabOrder(self.cmbManufacturerFilter, self.cmbStatusFilter)
        ItemListWidget.setTabOrder(self.cmbStatusFilter, self.chkShowDeleted)
        ItemListWidget.setTabOrder(self.chkShowDeleted, self.btnRefresh)
        ItemListWidget.setTabOrder(self.btnRefresh, self.tblItem)
        ItemListWidget.setTabOrder(self.tblItem, self.btnAdd)
        ItemListWidget.setTabOrder(self.btnAdd, self.btnEdit)
        ItemListWidget.setTabOrder(self.btnEdit, self.btnDelete)
        ItemListWidget.setTabOrder(self.btnDelete, self.btnRestore)
        ItemListWidget.setTabOrder(self.btnRestore, self.btnClose)
