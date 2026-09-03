# -*- coding: utf-8 -*-
"""
ui/ui_supplier_manufacturer_discount_list.py

Generated-style module for ui/supplier_manufacturer_discount_list.ui. Same
honest-limitation note as ui/ui_manufacturer_list.py -- regenerate for real
with:

    pyside6-uic ui/supplier_manufacturer_discount_list.ui -o ui/ui_supplier_manufacturer_discount_list.py
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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


class Ui_SupplierManufacturerDiscountListWidget(object):
    def setupUi(self, SupplierManufacturerDiscountListWidget):
        SupplierManufacturerDiscountListWidget.setObjectName("SupplierManufacturerDiscountListWidget")
        SupplierManufacturerDiscountListWidget.resize(950, 600)
        SupplierManufacturerDiscountListWidget.setWindowTitle("Supplier-Manufacturer Discount")

        self.verticalLayoutRoot = QVBoxLayout(SupplierManufacturerDiscountListWidget)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(12, 12, 12, 12)

        self.lblTitle = QLabel(SupplierManufacturerDiscountListWidget)
        self.lblTitle.setObjectName("lblTitle")
        font = self.lblTitle.font()
        font.setPointSize(14)
        font.setBold(True)
        self.lblTitle.setFont(font)
        self.lblTitle.setText("Supplier-Manufacturer Discount")
        self.verticalLayoutRoot.addWidget(self.lblTitle)

        # ---------------- Toolbar ----------------
        self.frmToolbar = QFrame(SupplierManufacturerDiscountListWidget)
        self.frmToolbar.setObjectName("frmToolbar")
        self.frmToolbar.setFrameShape(QFrame.StyledPanel)
        self.horizontalLayoutToolbar = QHBoxLayout(self.frmToolbar)
        self.horizontalLayoutToolbar.setObjectName("horizontalLayoutToolbar")

        self.lblSearch = QLabel("Search:", self.frmToolbar)
        self.horizontalLayoutToolbar.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frmToolbar)
        self.txtSearch.setObjectName("txtSearch")
        self.txtSearch.setPlaceholderText("Search by Supplier, Manufacturer, or Remarks...")
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip("Search Discount Mappings (Ctrl+F)")
        self.horizontalLayoutToolbar.addWidget(self.txtSearch)

        self.chkShowDeleted = QCheckBox("Show Deleted", self.frmToolbar)
        self.chkShowDeleted.setObjectName("chkShowDeleted")
        self.chkShowDeleted.setToolTip("Include soft-deleted mappings (needed to Restore one)")
        self.horizontalLayoutToolbar.addWidget(self.chkShowDeleted)

        self.horizontalSpacerToolbar = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutToolbar.addItem(self.horizontalSpacerToolbar)

        self.btnRefresh = QPushButton("Refresh", self.frmToolbar)
        self.btnRefresh.setObjectName("btnRefresh")
        self.btnRefresh.setToolTip("Reload discount list (F5)")
        self.horizontalLayoutToolbar.addWidget(self.btnRefresh)

        self.verticalLayoutRoot.addWidget(self.frmToolbar)

        # ---------------- Breadcrumb / Back ----------------
        self.horizontalLayoutBreadcrumb = QHBoxLayout()
        self.horizontalLayoutBreadcrumb.setObjectName("horizontalLayoutBreadcrumb")

        self.btnBack = QPushButton("< Back", SupplierManufacturerDiscountListWidget)
        self.btnBack.setObjectName("btnBack")
        self.btnBack.setVisible(False)
        self.horizontalLayoutBreadcrumb.addWidget(self.btnBack)

        self.lblBreadcrumb = QLabel("Suppliers", SupplierManufacturerDiscountListWidget)
        self.lblBreadcrumb.setObjectName("lblBreadcrumb")
        font_bc = self.lblBreadcrumb.font()
        font_bc.setBold(True)
        self.lblBreadcrumb.setFont(font_bc)
        self.horizontalLayoutBreadcrumb.addWidget(self.lblBreadcrumb)

        self.horizontalSpacerBreadcrumb = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutBreadcrumb.addItem(self.horizontalSpacerBreadcrumb)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutBreadcrumb)

        # ---------------- Table ----------------
        self.tblDiscount = QTableWidget(SupplierManufacturerDiscountListWidget)
        self.tblDiscount.setObjectName("tblDiscount")
        self.tblDiscount.setColumnCount(4)
        self.tblDiscount.setHorizontalHeaderLabels(
            ["Supplier Name", "Manufacturer Name", "Discount %", "Status"]
        )
        self.tblDiscount.setAlternatingRowColors(True)
        self.tblDiscount.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblDiscount.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblDiscount.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblDiscount.setSortingEnabled(True)
        self.tblDiscount.horizontalHeader().setStretchLastSection(True)
        self.verticalLayoutRoot.addWidget(self.tblDiscount)

        # ---------------- Pagination ----------------
        self.horizontalLayoutPagination = QHBoxLayout()
        self.horizontalLayoutPagination.setObjectName("horizontalLayoutPagination")

        self.btnPrev = QPushButton("< Prev", SupplierManufacturerDiscountListWidget)
        self.btnPrev.setObjectName("btnPrev")
        self.horizontalLayoutPagination.addWidget(self.btnPrev)

        self.lblPageInfo = QLabel("Page 1", SupplierManufacturerDiscountListWidget)
        self.lblPageInfo.setObjectName("lblPageInfo")
        self.horizontalLayoutPagination.addWidget(self.lblPageInfo)

        self.btnNext = QPushButton("Next >", SupplierManufacturerDiscountListWidget)
        self.btnNext.setObjectName("btnNext")
        self.horizontalLayoutPagination.addWidget(self.btnNext)

        self.horizontalSpacerPagination = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutPagination.addItem(self.horizontalSpacerPagination)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutPagination)

        self.lblRecordCount = QLabel("0 mapping(s) found", SupplierManufacturerDiscountListWidget)
        self.lblRecordCount.setObjectName("lblRecordCount")
        self.lblRecordCount.setStyleSheet("color: #666666;")
        self.verticalLayoutRoot.addWidget(self.lblRecordCount)

        # ---------------- Action buttons ----------------
        self.horizontalLayoutButtons = QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")

        self.btnAdd = QPushButton("Add Mapping", SupplierManufacturerDiscountListWidget)
        self.btnAdd.setObjectName("btnAdd")
        self.btnAdd.setToolTip("Add a new discount mapping (Ctrl+N)")
        self.horizontalLayoutButtons.addWidget(self.btnAdd)

        self.btnEdit = QPushButton("Edit", SupplierManufacturerDiscountListWidget)
        self.btnEdit.setObjectName("btnEdit")
        self.btnEdit.setToolTip("Edit the selected mapping (Enter)")
        self.horizontalLayoutButtons.addWidget(self.btnEdit)

        self.btnDelete = QPushButton("Delete", SupplierManufacturerDiscountListWidget)
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setToolTip("Soft-delete the selected mapping (Del)")
        self.horizontalLayoutButtons.addWidget(self.btnDelete)

        self.btnRestore = QPushButton("Restore", SupplierManufacturerDiscountListWidget)
        self.btnRestore.setObjectName("btnRestore")
        self.btnRestore.setToolTip("Restore the selected deleted mapping")
        self.btnRestore.setEnabled(False)
        self.horizontalLayoutButtons.addWidget(self.btnRestore)

        self.horizontalSpacerButtons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutButtons.addItem(self.horizontalSpacerButtons)

        self.btnClose = QPushButton("Close", SupplierManufacturerDiscountListWidget)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setToolTip("Close this screen (Esc)")
        self.horizontalLayoutButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutButtons)

        SupplierManufacturerDiscountListWidget.setTabOrder(self.txtSearch, self.chkShowDeleted)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.chkShowDeleted, self.btnRefresh)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.btnRefresh, self.tblDiscount)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.tblDiscount, self.btnAdd)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.btnAdd, self.btnEdit)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.btnEdit, self.btnDelete)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.btnDelete, self.btnRestore)
        SupplierManufacturerDiscountListWidget.setTabOrder(self.btnRestore, self.btnClose)
