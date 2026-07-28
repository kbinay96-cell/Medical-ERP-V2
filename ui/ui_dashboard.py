# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'dashboard.ui'
## Hand-written to mirror pyside6-uic output style (see note in ui_login.py).
## Re-generate with: pyside6-uic ui\dashboard.ui -o ui\ui_dashboard.py
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QSplitter, QStatusBar, QTreeWidget,
    QVBoxLayout, QWidget,
)

ICON_DIR = "resources/icons"


def _kpi_card(parent, title_text, title_attr, value_attr, icon_path=None):
    """Small shared builder for the repeated KPI-card pattern."""
    card = QFrame(parent)
    card.setProperty("cssClass", "kpiCard")
    card.setMinimumSize(QSize(220, 90))

    outer = QHBoxLayout(card)
    outer.setContentsMargins(14, 12, 14, 12)
    outer.setSpacing(12)

    if icon_path:
        icon_label = QLabel(card)
        icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(28, 28)))
        icon_label.setFixedSize(QSize(32, 32))
        outer.addWidget(icon_label)

    text_col = QVBoxLayout()
    title_label = QLabel(card)
    title_label.setText(title_text)
    title_label.setProperty("cssClass", "kpiTitle")
    value_label = QLabel(card)
    value_label.setText("0")
    value_label.setProperty("cssClass", "kpiValue")
    text_col.addWidget(title_label)
    text_col.addWidget(value_label)
    outer.addLayout(text_col)

    return card, title_label, value_label


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1366, 800)
        MainWindow.setMinimumSize(QSize(1024, 640))
        MainWindow.setWindowTitle(u"Medical ERP Dashboard")

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainVerticalLayout = QVBoxLayout(self.centralwidget)

        # ================= TOP HEADER =================
        self.frmTopHeader = QFrame(self.centralwidget)
        self.frmTopHeader.setObjectName(u"frmTopHeader")
        self.topHeaderLayout = QHBoxLayout(self.frmTopHeader)

        self.lblCompanyLogoSmall = QLabel(self.frmTopHeader)
        self.lblCompanyLogoSmall.setObjectName(u"lblCompanyLogoSmall")
        self.topHeaderLayout.addWidget(self.lblCompanyLogoSmall)

        self.lblCompanyNameHeader = QLabel(self.frmTopHeader)
        self.lblCompanyNameHeader.setObjectName(u"lblCompanyNameHeader")
        self.topHeaderLayout.addWidget(self.lblCompanyNameHeader)

        self.topHeaderSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.topHeaderLayout.addItem(self.topHeaderSpacer)

        self.txtSearchMenu = QLineEdit(self.frmTopHeader)
        self.txtSearchMenu.setObjectName(u"txtSearchMenu")
        self.txtSearchMenu.setPlaceholderText(u"Search menu...")
        self.topHeaderLayout.addWidget(self.txtSearchMenu)

        self.lblLoggedInUser = QLabel(self.frmTopHeader)
        self.lblLoggedInUser.setObjectName(u"lblLoggedInUser")
        self.topHeaderLayout.addWidget(self.lblLoggedInUser)

        self.lblUserRole = QLabel(self.frmTopHeader)
        self.lblUserRole.setObjectName(u"lblUserRole")
        self.topHeaderLayout.addWidget(self.lblUserRole)

        self.lblCurrentFinancialYearHeader = QLabel(self.frmTopHeader)
        self.lblCurrentFinancialYearHeader.setObjectName(u"lblCurrentFinancialYearHeader")
        self.topHeaderLayout.addWidget(self.lblCurrentFinancialYearHeader)

        self.lblDashboardClock = QLabel(self.frmTopHeader)
        self.lblDashboardClock.setObjectName(u"lblDashboardClock")
        self.topHeaderLayout.addWidget(self.lblDashboardClock)

        self.btnNotifications = QPushButton(self.frmTopHeader)
        self.btnNotifications.setObjectName(u"btnNotifications")
        self.btnNotifications.setIcon(QIcon(f"{ICON_DIR}/bell.svg"))
        self.topHeaderLayout.addWidget(self.btnNotifications)

        self.btnTheme = QPushButton(self.frmTopHeader)
        self.btnTheme.setObjectName(u"btnTheme")
        self.btnTheme.setIcon(QIcon(f"{ICON_DIR}/sun.svg"))
        self.topHeaderLayout.addWidget(self.btnTheme)

        self.btnLogout = QPushButton(self.frmTopHeader)
        self.btnLogout.setObjectName(u"btnLogout")
        self.btnLogout.setIcon(QIcon(f"{ICON_DIR}/logout.svg"))
        self.topHeaderLayout.addWidget(self.btnLogout)

        self.mainVerticalLayout.addWidget(self.frmTopHeader)

        # ================= BODY: SPLITTER (Sidebar + Main) =================
        self.bodySplitter = QSplitter(self.centralwidget)
        self.bodySplitter.setObjectName(u"bodySplitter")
        self.bodySplitter.setOrientation(Qt.Orientation.Horizontal)

        # ---------- SIDEBAR ----------
        self.frmSidebar = QFrame(self.bodySplitter)
        self.frmSidebar.setObjectName(u"frmSidebar")
        self.sidebarLayout = QVBoxLayout(self.frmSidebar)

        self.lblFavoritesTitle = QLabel(self.frmSidebar)
        self.lblFavoritesTitle.setObjectName(u"lblFavoritesTitle")
        self.sidebarLayout.addWidget(self.lblFavoritesTitle)

        self.lstFavorites = QListWidget(self.frmSidebar)
        self.lstFavorites.setObjectName(u"lstFavorites")
        self.sidebarLayout.addWidget(self.lstFavorites)

        self.lblRecentTitle = QLabel(self.frmSidebar)
        self.lblRecentTitle.setObjectName(u"lblRecentTitle")
        self.sidebarLayout.addWidget(self.lblRecentTitle)

        self.lstRecentlyOpened = QListWidget(self.frmSidebar)
        self.lstRecentlyOpened.setObjectName(u"lstRecentlyOpened")
        self.sidebarLayout.addWidget(self.lstRecentlyOpened)

        self.lblMenuTitle = QLabel(self.frmSidebar)
        self.lblMenuTitle.setObjectName(u"lblMenuTitle")
        self.sidebarLayout.addWidget(self.lblMenuTitle)

        self.treeSidebarMenu = QTreeWidget(self.frmSidebar)
        self.treeSidebarMenu.setObjectName(u"treeSidebarMenu")
        self.treeSidebarMenu.setHeaderLabels(["Menu"])
        self.sidebarLayout.addWidget(self.treeSidebarMenu)

        # ---------- MAIN AREA ----------
        self.scrollMainArea = QScrollArea(self.bodySplitter)
        self.scrollMainArea.setObjectName(u"scrollMainArea")
        self.scrollMainArea.setWidgetResizable(True)

        self.scrollAreaContents = QWidget()
        self.scrollAreaContents.setObjectName(u"scrollAreaContents")
        self.mainAreaLayout = QVBoxLayout(self.scrollAreaContents)

        # KPI cards
        self.grpKpiCards = QGroupBox(self.scrollAreaContents)
        self.grpKpiCards.setObjectName(u"grpKpiCards")
        self.kpiGridLayout = QGridLayout(self.grpKpiCards)

        self.cardTodaySales, self.lblTodaySalesTitle, self.lblTodaySalesValue = _kpi_card(self.grpKpiCards, "Today's Sales", "lblTodaySalesTitle", "lblTodaySalesValue", f"{ICON_DIR}/money.svg")
        self.kpiGridLayout.addWidget(self.cardTodaySales, 0, 0)

        self.cardTodayPurchase, self.lblTodayPurchaseTitle, self.lblTodayPurchaseValue = _kpi_card(self.grpKpiCards, "Today's Purchase", "lblTodayPurchaseTitle", "lblTodayPurchaseValue", f"{ICON_DIR}/cart.svg")
        self.kpiGridLayout.addWidget(self.cardTodayPurchase, 0, 1)

        self.cardStockValue, self.lblStockValueTitle, self.lblStockValueValue = _kpi_card(self.grpKpiCards, "Stock Value", "lblStockValueTitle", "lblStockValueValue", f"{ICON_DIR}/box.svg")
        self.kpiGridLayout.addWidget(self.cardStockValue, 0, 2)

        self.cardLowStock, self.lblLowStockTitle, self.lblLowStockValue = _kpi_card(self.grpKpiCards, "Low Stock Items", "lblLowStockTitle", "lblLowStockValue", f"{ICON_DIR}/box.svg")
        self.kpiGridLayout.addWidget(self.cardLowStock, 0, 3)

        self.cardExpiring, self.lblExpiringTitle, self.lblExpiringValue = _kpi_card(self.grpKpiCards, "Expiring Medicines", "lblExpiringTitle", "lblExpiringValue", f"{ICON_DIR}/calendar.svg")
        self.kpiGridLayout.addWidget(self.cardExpiring, 1, 0)

        self.cardPendingPayments, self.lblPendingPaymentsTitle, self.lblPendingPaymentsValue = _kpi_card(self.grpKpiCards, "Pending Payments", "lblPendingPaymentsTitle", "lblPendingPaymentsValue", f"{ICON_DIR}/money.svg")
        self.kpiGridLayout.addWidget(self.cardPendingPayments, 1, 1)

        self.cardPendingReceipts, self.lblPendingReceiptsTitle, self.lblPendingReceiptsValue = _kpi_card(self.grpKpiCards, "Pending Receipts", "lblPendingReceiptsTitle", "lblPendingReceiptsValue", f"{ICON_DIR}/report.svg")
        self.kpiGridLayout.addWidget(self.cardPendingReceipts, 1, 2)

        self.cardActiveUsers, self.lblActiveUsersTitle, self.lblActiveUsersValue = _kpi_card(self.grpKpiCards, "Active Users", "lblActiveUsersTitle", "lblActiveUsersValue", f"{ICON_DIR}/user.svg")
        self.kpiGridLayout.addWidget(self.cardActiveUsers, 1, 3)

        self.mainAreaLayout.addWidget(self.grpKpiCards)

        # Quick actions
        self.grpQuickActions = QGroupBox(self.scrollAreaContents)
        self.grpQuickActions.setObjectName(u"grpQuickActions")
        self.quickActionsLayout = QHBoxLayout(self.grpQuickActions)

        self.btnNewSale = QPushButton(self.grpQuickActions); self.btnNewSale.setObjectName(u"btnNewSale")
        self.btnNewSale.setIcon(QIcon(f"{ICON_DIR}/plus.svg"))
        self.btnNewPurchase = QPushButton(self.grpQuickActions); self.btnNewPurchase.setObjectName(u"btnNewPurchase")
        self.btnNewPurchase.setIcon(QIcon(f"{ICON_DIR}/cart.svg"))
        self.btnAddCustomer = QPushButton(self.grpQuickActions); self.btnAddCustomer.setObjectName(u"btnAddCustomer")
        self.btnAddCustomer.setIcon(QIcon(f"{ICON_DIR}/customer.svg"))
        self.btnAddSupplier = QPushButton(self.grpQuickActions); self.btnAddSupplier.setObjectName(u"btnAddSupplier")
        self.btnAddSupplier.setIcon(QIcon(f"{ICON_DIR}/truck.svg"))
        self.btnAddItem = QPushButton(self.grpQuickActions); self.btnAddItem.setObjectName(u"btnAddItem")
        self.btnAddItem.setIcon(QIcon(f"{ICON_DIR}/box.svg"))
        self.btnBackupDatabase = QPushButton(self.grpQuickActions); self.btnBackupDatabase.setObjectName(u"btnBackupDatabase")
        self.btnBackupDatabase.setIcon(QIcon(f"{ICON_DIR}/backup.svg"))

        for b in (self.btnNewSale, self.btnNewPurchase, self.btnAddCustomer, self.btnAddSupplier, self.btnAddItem, self.btnBackupDatabase):
            self.quickActionsLayout.addWidget(b)

        self.mainAreaLayout.addWidget(self.grpQuickActions)

        # Alerts + Recent Activity
        self.lowerAreaLayout = QHBoxLayout()

        self.grpAlerts = QGroupBox(self.scrollAreaContents)
        self.grpAlerts.setObjectName(u"grpAlerts")
        self.alertsLayout = QVBoxLayout(self.grpAlerts)
        self.lstAlerts = QListWidget(self.grpAlerts)
        self.lstAlerts.setObjectName(u"lstAlerts")
        self.alertsLayout.addWidget(self.lstAlerts)
        self.lowerAreaLayout.addWidget(self.grpAlerts)

        self.grpRecentActivity = QGroupBox(self.scrollAreaContents)
        self.grpRecentActivity.setObjectName(u"grpRecentActivity")
        self.recentActivityLayout = QVBoxLayout(self.grpRecentActivity)
        self.lstRecentActivity = QListWidget(self.grpRecentActivity)
        self.lstRecentActivity.setObjectName(u"lstRecentActivity")
        self.recentActivityLayout.addWidget(self.lstRecentActivity)
        self.lowerAreaLayout.addWidget(self.grpRecentActivity)

        self.mainAreaLayout.addLayout(self.lowerAreaLayout)

        self.scrollMainArea.setWidget(self.scrollAreaContents)

        self.bodySplitter.addWidget(self.frmSidebar)
        self.bodySplitter.addWidget(self.scrollMainArea)
        self.bodySplitter.setStretchFactor(0, 0)
        self.bodySplitter.setStretchFactor(1, 1)

        self.mainVerticalLayout.addWidget(self.bodySplitter)

        MainWindow.setCentralWidget(self.centralwidget)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Medical ERP Dashboard", None))
        self.lblCompanyLogoSmall.setText(QCoreApplication.translate("MainWindow", u"[Logo]", None))
        self.lblCompanyNameHeader.setText(QCoreApplication.translate("MainWindow", u"Company Name", None))
        self.lblLoggedInUser.setText(QCoreApplication.translate("MainWindow", u"User", None))
        self.lblUserRole.setText(QCoreApplication.translate("MainWindow", u"Role", None))
        self.lblCurrentFinancialYearHeader.setText(QCoreApplication.translate("MainWindow", u"FY", None))
        self.lblDashboardClock.setText(QCoreApplication.translate("MainWindow", u"00:00:00", None))
        self.btnNotifications.setText(QCoreApplication.translate("MainWindow", u"Alerts (0)", None))
        self.btnTheme.setText(QCoreApplication.translate("MainWindow", u"Theme", None))
        self.btnLogout.setText(QCoreApplication.translate("MainWindow", u"Logout", None))
        self.lblFavoritesTitle.setText(QCoreApplication.translate("MainWindow", u"Favorites", None))
        self.lblRecentTitle.setText(QCoreApplication.translate("MainWindow", u"Recently Opened", None))
        self.lblMenuTitle.setText(QCoreApplication.translate("MainWindow", u"Modules", None))
        self.grpKpiCards.setTitle(QCoreApplication.translate("MainWindow", u"Overview", None))
        self.grpQuickActions.setTitle(QCoreApplication.translate("MainWindow", u"Quick Actions", None))
        self.btnNewSale.setText(QCoreApplication.translate("MainWindow", u"New Sale", None))
        self.btnNewPurchase.setText(QCoreApplication.translate("MainWindow", u"New Purchase", None))
        self.btnAddCustomer.setText(QCoreApplication.translate("MainWindow", u"Add Customer", None))
        self.btnAddSupplier.setText(QCoreApplication.translate("MainWindow", u"Add Supplier", None))
        self.btnAddItem.setText(QCoreApplication.translate("MainWindow", u"Add Item", None))
        self.btnBackupDatabase.setText(QCoreApplication.translate("MainWindow", u"Backup Database", None))
        self.grpAlerts.setTitle(QCoreApplication.translate("MainWindow", u"Alerts", None))
        self.grpRecentActivity.setTitle(QCoreApplication.translate("MainWindow", u"Recent Activities", None))
    # retranslateUi
