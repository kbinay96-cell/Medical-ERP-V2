# -*- coding: utf-8 -*-
"""
ui/ui_supplier_list.py

Generated-style form module for ui/supplier_list.ui.

NOTE (honest limitation, same as the Login/Dashboard module): Qt Designer /
pyside6-uic is not runnable in the environment this file was authored in, so
this file was hand-written to match the exact structure and object names
pyside6-uic would produce from supplier_list.ui. Before shipping, regenerate
it for real with:

    pyside6-uic ui/supplier_list.ui -o ui/ui_supplier_list.py

Regenerating will not break screens/supplier_list_screen.py -- every widget
name below matches the .ui file exactly, which is the only contract the
Screen layer relies on.
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
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class Ui_SupplierListWidget(object):
    def setupUi(self, SupplierListWidget):
        SupplierListWidget.setObjectName("SupplierListWidget")
        SupplierListWidget.resize(1100, 650)
        SupplierListWidget.setWindowTitle("Supplier Master")

        self.verticalLayoutRoot = QVBoxLayout(SupplierListWidget)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(12, 12, 12, 12)

        self.lblTitle = QLabel(SupplierListWidget)
        self.lblTitle.setObjectName("lblTitle")
        font = self.lblTitle.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lblTitle.setFont(font)
        self.lblTitle.setText("Supplier Master")
        self.verticalLayoutRoot.addWidget(self.lblTitle)

        self.frmToolbar = QFrame(SupplierListWidget)
        self.frmToolbar.setObjectName("frmToolbar")
        self.frmToolbar.setFrameShape(QFrame.StyledPanel)
        self.horizontalLayoutToolbar = QHBoxLayout(self.frmToolbar)
        self.horizontalLayoutToolbar.setObjectName("horizontalLayoutToolbar")

        self.lblSearch = QLabel(self.frmToolbar)
        self.lblSearch.setObjectName("lblSearch")
        self.lblSearch.setText("Search:")
        self.horizontalLayoutToolbar.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frmToolbar)
        self.txtSearch.setObjectName("txtSearch")
        self.txtSearch.setPlaceholderText("Search by Code, Name, Mobile or PAN/VAT...")
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip("Search Suppliers (Ctrl+F)")
        self.horizontalLayoutToolbar.addWidget(self.txtSearch)

        self.lblStatusFilter = QLabel(self.frmToolbar)
        self.lblStatusFilter.setObjectName("lblStatusFilter")
        self.lblStatusFilter.setText("Status:")
        self.horizontalLayoutToolbar.addWidget(self.lblStatusFilter)

        self.cmbStatusFilter = QComboBox(self.frmToolbar)
        self.cmbStatusFilter.setObjectName("cmbStatusFilter")
        self.cmbStatusFilter.addItems(["All", "Active", "Inactive"])
        self.cmbStatusFilter.setToolTip("Filter suppliers by status")
        self.horizontalLayoutToolbar.addWidget(self.cmbStatusFilter)

        self.chkShowDeleted = QCheckBox(self.frmToolbar)
        self.chkShowDeleted.setObjectName("chkShowDeleted")
        self.chkShowDeleted.setText("Show Deleted")
        self.chkShowDeleted.setToolTip("Include soft-deleted suppliers (needed to Restore one)")
        self.horizontalLayoutToolbar.addWidget(self.chkShowDeleted)

        self.horizontalSpacerToolbar = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        self.horizontalLayoutToolbar.addItem(self.horizontalSpacerToolbar)

        self.btnRefresh = QPushButton(self.frmToolbar)
        self.btnRefresh.setObjectName("btnRefresh")
        self.btnRefresh.setText("Refresh")
        self.btnRefresh.setToolTip("Reload supplier list (F5)")
        self.horizontalLayoutToolbar.addWidget(self.btnRefresh)

        self.verticalLayoutRoot.addWidget(self.frmToolbar)

        self.tblSupplier = QTableWidget(SupplierListWidget)
        self.tblSupplier.setObjectName("tblSupplier")
        self.tblSupplier.setColumnCount(11)
        self.tblSupplier.setHorizontalHeaderLabels([
            "Code", "Supplier Name", "Contact Person", "Mobile No.", "City",
            "PAN/VAT No.", "Opening Balance", "Type", "Credit Limit",
            "Credit Days", "Status",
        ])
        self.tblSupplier.setAlternatingRowColors(True)
        self.tblSupplier.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblSupplier.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblSupplier.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblSupplier.setSortingEnabled(True)
        self.tblSupplier.horizontalHeader().setStretchLastSection(True)
        self.tblSupplier.verticalHeader().setVisible(False)
        self.verticalLayoutRoot.addWidget(self.tblSupplier)

        self.lblRecordCount = QLabel(SupplierListWidget)
        self.lblRecordCount.setObjectName("lblRecordCount")
        self.lblRecordCount.setText("0 supplier(s) found")
        self.lblRecordCount.setStyleSheet("color: #666666;")
        self.verticalLayoutRoot.addWidget(self.lblRecordCount)

        self.horizontalLayoutButtons = QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")

        self.btnAdd = QPushButton(SupplierListWidget)
        self.btnAdd.setObjectName("btnAdd")
        self.btnAdd.setText("Add Supplier")
        self.btnAdd.setToolTip("Add a new supplier (Ctrl+N)")
        self.horizontalLayoutButtons.addWidget(self.btnAdd)

        self.btnEdit = QPushButton(SupplierListWidget)
        self.btnEdit.setObjectName("btnEdit")
        self.btnEdit.setText("Edit")
        self.btnEdit.setToolTip("Edit the selected supplier (Enter)")
        self.horizontalLayoutButtons.addWidget(self.btnEdit)

        self.btnDelete = QPushButton(SupplierListWidget)
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setText("Delete")
        self.btnDelete.setToolTip("Soft-delete the selected supplier (Del)")
        self.horizontalLayoutButtons.addWidget(self.btnDelete)

        self.btnRestore = QPushButton(SupplierListWidget)
        self.btnRestore.setObjectName("btnRestore")
        self.btnRestore.setText("Restore")
        self.btnRestore.setToolTip("Restore the selected deleted supplier")
        self.btnRestore.setEnabled(False)
        self.horizontalLayoutButtons.addWidget(self.btnRestore)

        self.horizontalSpacerButtons = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        self.horizontalLayoutButtons.addItem(self.horizontalSpacerButtons)

        self.btnClose = QPushButton(SupplierListWidget)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setText("Close")
        self.btnClose.setToolTip("Close this screen (Esc)")
        self.horizontalLayoutButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutButtons)

        SupplierListWidget.setTabOrder(self.txtSearch, self.cmbStatusFilter)
        SupplierListWidget.setTabOrder(self.cmbStatusFilter, self.chkShowDeleted)
        SupplierListWidget.setTabOrder(self.chkShowDeleted, self.btnRefresh)
        SupplierListWidget.setTabOrder(self.btnRefresh, self.tblSupplier)
        SupplierListWidget.setTabOrder(self.tblSupplier, self.btnAdd)
        SupplierListWidget.setTabOrder(self.btnAdd, self.btnEdit)
        SupplierListWidget.setTabOrder(self.btnEdit, self.btnDelete)
        SupplierListWidget.setTabOrder(self.btnDelete, self.btnRestore)
        SupplierListWidget.setTabOrder(self.btnRestore, self.btnClose)
