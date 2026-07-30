# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'company_list.ui'
## WARNING! All changes made in this file will be lost when recompiling.
## Regenerate with: pyside6-uic ui/company_list.ui -o ui/ui_company_list.py
################################################################################

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QTableWidget, QVBoxLayout
)


class Ui_CompanyListWidget(object):
    def setupUi(self, CompanyListWidget):
        if not CompanyListWidget.objectName():
            CompanyListWidget.setObjectName(u"CompanyListWidget")
        CompanyListWidget.resize(1000, 650)

        self.verticalLayout_root = QVBoxLayout(CompanyListWidget)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")

        self.lblTitle = QLabel(CompanyListWidget)
        self.lblTitle.setObjectName(u"lblTitle")
        self.lblTitle.setStyleSheet(u"font-size: 18px; font-weight: 600;")
        self.verticalLayout_root.addWidget(self.lblTitle)

        # ---------------- Filters ----------------
        self.frameFilters = QFrame(CompanyListWidget)
        self.frameFilters.setObjectName(u"frameFilters")
        self.horizontalLayout_filters = QHBoxLayout(self.frameFilters)
        self.horizontalLayout_filters.setObjectName(u"horizontalLayout_filters")

        self.lblSearch = QLabel(self.frameFilters)
        self.lblSearch.setObjectName(u"lblSearch")
        self.horizontalLayout_filters.addWidget(self.lblSearch)

        self.txtSearch = QLineEdit(self.frameFilters)
        self.txtSearch.setObjectName(u"txtSearch")
        self.horizontalLayout_filters.addWidget(self.txtSearch)

        self.lblStatusFilter = QLabel(self.frameFilters)
        self.lblStatusFilter.setObjectName(u"lblStatusFilter")
        self.horizontalLayout_filters.addWidget(self.lblStatusFilter)

        self.cmbStatusFilter = QComboBox(self.frameFilters)
        self.cmbStatusFilter.addItem("")
        self.cmbStatusFilter.addItem("")
        self.cmbStatusFilter.addItem("")
        self.cmbStatusFilter.setObjectName(u"cmbStatusFilter")
        self.horizontalLayout_filters.addWidget(self.cmbStatusFilter)

        self.chkShowDeleted = QCheckBox(self.frameFilters)
        self.chkShowDeleted.setObjectName(u"chkShowDeleted")
        self.horizontalLayout_filters.addWidget(self.chkShowDeleted)

        self.horizontalSpacer_filters = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_filters.addItem(self.horizontalSpacer_filters)

        self.btnRefresh = QPushButton(self.frameFilters)
        self.btnRefresh.setObjectName(u"btnRefresh")
        self.horizontalLayout_filters.addWidget(self.btnRefresh)

        self.verticalLayout_root.addWidget(self.frameFilters)

        # ---------------- Actions ----------------
        self.frameActions = QFrame(CompanyListWidget)
        self.frameActions.setObjectName(u"frameActions")
        self.horizontalLayout_actions = QHBoxLayout(self.frameActions)
        self.horizontalLayout_actions.setObjectName(u"horizontalLayout_actions")

        self.btnAdd = QPushButton(self.frameActions)
        self.btnAdd.setObjectName(u"btnAdd")
        self.horizontalLayout_actions.addWidget(self.btnAdd)

        self.btnEdit = QPushButton(self.frameActions)
        self.btnEdit.setObjectName(u"btnEdit")
        self.horizontalLayout_actions.addWidget(self.btnEdit)

        self.btnDelete = QPushButton(self.frameActions)
        self.btnDelete.setObjectName(u"btnDelete")
        self.horizontalLayout_actions.addWidget(self.btnDelete)

        self.btnRestore = QPushButton(self.frameActions)
        self.btnRestore.setObjectName(u"btnRestore")
        self.horizontalLayout_actions.addWidget(self.btnRestore)

        self.lineActionsSep = QFrame(self.frameActions)
        self.lineActionsSep.setObjectName(u"lineActionsSep")
        self.lineActionsSep.setFrameShape(QFrame.VLine)
        self.horizontalLayout_actions.addWidget(self.lineActionsSep)

        self.btnExport = QPushButton(self.frameActions)
        self.btnExport.setObjectName(u"btnExport")
        self.horizontalLayout_actions.addWidget(self.btnExport)

        self.btnPrint = QPushButton(self.frameActions)
        self.btnPrint.setObjectName(u"btnPrint")
        self.horizontalLayout_actions.addWidget(self.btnPrint)

        self.horizontalSpacer_actions = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_actions.addItem(self.horizontalSpacer_actions)

        self.btnClose = QPushButton(self.frameActions)
        self.btnClose.setObjectName(u"btnClose")
        self.horizontalLayout_actions.addWidget(self.btnClose)

        self.verticalLayout_root.addWidget(self.frameActions)

        # ---------------- Table ----------------
        self.tblCompany = QTableWidget(CompanyListWidget)
        if self.tblCompany.columnCount() < 7:
            self.tblCompany.setColumnCount(7)
        self.tblCompany.setObjectName(u"tblCompany")
        self.tblCompany.setColumnCount(7)
        self.tblCompany.setHorizontalHeaderLabels([
            "Company ID", "Company Name", "Contact Person", "Mobile No.",
            "Phone No.", "Email", "Status",
        ])
        self.tblCompany.setSortingEnabled(True)
        self.tblCompany.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tblCompany.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tblCompany.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tblCompany.setAlternatingRowColors(True)
        self.tblCompany.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalLayout_root.addWidget(self.tblCompany)

        # ---------------- Status bar / record count ----------------
        self.statusBar = QStatusBar(CompanyListWidget)
        self.statusBar.setObjectName(u"statusBar")
        self.statusBar.setSizeGripEnabled(False)
        self.verticalLayout_root.addWidget(self.statusBar)

        self.lblRecordCount = QLabel(CompanyListWidget)
        self.lblRecordCount.setObjectName(u"lblRecordCount")
        self.verticalLayout_root.addWidget(self.lblRecordCount)

        self.retranslateUi(CompanyListWidget)

    def retranslateUi(self, CompanyListWidget):
        CompanyListWidget.setWindowTitle(QCoreApplication.translate("CompanyListWidget", u"Company Master", None))
        self.lblTitle.setText(QCoreApplication.translate("CompanyListWidget", u"Company Master", None))
        self.lblSearch.setText(QCoreApplication.translate("CompanyListWidget", u"Search:", None))
        self.txtSearch.setPlaceholderText(QCoreApplication.translate(
            "CompanyListWidget", u"Search by name, contact person, mobile, or email...", None))
        self.lblStatusFilter.setText(QCoreApplication.translate("CompanyListWidget", u"Status:", None))
        self.cmbStatusFilter.setItemText(0, QCoreApplication.translate("CompanyListWidget", u"All", None))
        self.cmbStatusFilter.setItemText(1, QCoreApplication.translate("CompanyListWidget", u"Active", None))
        self.cmbStatusFilter.setItemText(2, QCoreApplication.translate("CompanyListWidget", u"Inactive", None))
        self.chkShowDeleted.setText(QCoreApplication.translate("CompanyListWidget", u"Show Deleted", None))
        self.btnRefresh.setText(QCoreApplication.translate("CompanyListWidget", u"Refresh", None))
        self.btnAdd.setText(QCoreApplication.translate("CompanyListWidget", u"Add", None))
        self.btnEdit.setText(QCoreApplication.translate("CompanyListWidget", u"Edit", None))
        self.btnDelete.setText(QCoreApplication.translate("CompanyListWidget", u"Delete", None))
        self.btnRestore.setText(QCoreApplication.translate("CompanyListWidget", u"Restore", None))
        self.btnExport.setText(QCoreApplication.translate("CompanyListWidget", u"Export Excel", None))
        self.btnPrint.setText(QCoreApplication.translate("CompanyListWidget", u"Print", None))
        self.btnClose.setText(QCoreApplication.translate("CompanyListWidget", u"Close", None))
        self.lblRecordCount.setText(QCoreApplication.translate("CompanyListWidget", u"0 company(s) found", None))
