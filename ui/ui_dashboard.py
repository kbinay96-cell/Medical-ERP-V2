# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dashboard.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSplitter,
    QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1366, 800)
        MainWindow.setMinimumSize(QSize(1024, 640))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.mainVerticalLayout = QVBoxLayout(self.centralwidget)
        self.mainVerticalLayout.setObjectName(u"mainVerticalLayout")
        self.frmTopHeader = QFrame(self.centralwidget)
        self.frmTopHeader.setObjectName(u"frmTopHeader")
        self.frmTopHeader.setMaximumSize(QSize(16777215, 64))
        self.topHeaderLayout = QHBoxLayout(self.frmTopHeader)
        self.topHeaderLayout.setObjectName(u"topHeaderLayout")
        self.lblCompanyLogoSmall = QLabel(self.frmTopHeader)
        self.lblCompanyLogoSmall.setObjectName(u"lblCompanyLogoSmall")

        self.topHeaderLayout.addWidget(self.lblCompanyLogoSmall)

        self.lblCompanyNameHeader = QLabel(self.frmTopHeader)
        self.lblCompanyNameHeader.setObjectName(u"lblCompanyNameHeader")

        self.topHeaderLayout.addWidget(self.lblCompanyNameHeader)

        self.topHeaderSpacerLeft = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.topHeaderLayout.addItem(self.topHeaderSpacerLeft)

        self.txtSearchMenu = QLineEdit(self.frmTopHeader)
        self.txtSearchMenu.setObjectName(u"txtSearchMenu")
        self.txtSearchMenu.setMinimumWidth(320)
        self.txtSearchMenu.setMaximumHeight(36)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.txtSearchMenu.sizePolicy().hasHeightForWidth())
        self.txtSearchMenu.setSizePolicy(sizePolicy)

        self.topHeaderLayout.addWidget(self.txtSearchMenu)

        self.frmUserInfo = QFrame(self.frmTopHeader)
        self.frmUserInfo.setObjectName(u"frmUserInfo")
        self.frmUserInfo.setMaximumSize(QSize(16777215, 40))
        self.userInfoLayout = QHBoxLayout(self.frmUserInfo)
        self.userInfoLayout.setSpacing(6)
        self.userInfoLayout.setObjectName(u"userInfoLayout")
        self.lblLoggedInUser = QLabel(self.frmUserInfo)
        self.lblLoggedInUser.setObjectName(u"lblLoggedInUser")

        self.userInfoLayout.addWidget(self.lblLoggedInUser)

        self.lblUserRole = QLabel(self.frmUserInfo)
        self.lblUserRole.setObjectName(u"lblUserRole")

        self.userInfoLayout.addWidget(self.lblUserRole)

        self.lblCurrentFinancialYearHeader = QLabel(self.frmUserInfo)
        self.lblCurrentFinancialYearHeader.setObjectName(u"lblCurrentFinancialYearHeader")

        self.userInfoLayout.addWidget(self.lblCurrentFinancialYearHeader)


        self.topHeaderLayout.addWidget(self.frmUserInfo)

        self.btnNotifications = QPushButton(self.frmTopHeader)
        self.btnNotifications.setObjectName(u"btnNotifications")

        self.topHeaderLayout.addWidget(self.btnNotifications)

        self.btnTheme = QPushButton(self.frmTopHeader)
        self.btnTheme.setObjectName(u"btnTheme")

        self.topHeaderLayout.addWidget(self.btnTheme)

        self.btnLogout = QPushButton(self.frmTopHeader)
        self.btnLogout.setObjectName(u"btnLogout")

        self.topHeaderLayout.addWidget(self.btnLogout)


        self.mainVerticalLayout.addWidget(self.frmTopHeader)

        self.bodySplitter = QSplitter(self.centralwidget)
        self.bodySplitter.setObjectName(u"bodySplitter")
        self.bodySplitter.setOrientation(Qt.Horizontal)
        self.frmSidebar = QFrame(self.bodySplitter)
        self.frmSidebar.setObjectName(u"frmSidebar")
        self.sidebarLayout = QVBoxLayout(self.frmSidebar)
        self.sidebarLayout.setObjectName(u"sidebarLayout")
        self.lblMenuTitle = QLabel(self.frmSidebar)
        self.lblMenuTitle.setObjectName(u"lblMenuTitle")

        self.sidebarLayout.addWidget(self.lblMenuTitle)

        self.treeSidebarMenu = QTreeWidget(self.frmSidebar)
        self.treeSidebarMenu.setObjectName(u"treeSidebarMenu")

        self.sidebarLayout.addWidget(self.treeSidebarMenu)

        self.bodySplitter.addWidget(self.frmSidebar)
        self.scrollMainArea = QScrollArea(self.bodySplitter)
        self.scrollMainArea.setObjectName(u"scrollMainArea")
        self.scrollMainArea.setWidgetResizable(True)
        self.scrollAreaContents = QWidget()
        self.scrollAreaContents.setObjectName(u"scrollAreaContents")
        self.mainAreaLayout = QVBoxLayout(self.scrollAreaContents)
        self.mainAreaLayout.setObjectName(u"mainAreaLayout")
        self.grpKpiCards = QGroupBox(self.scrollAreaContents)
        self.grpKpiCards.setObjectName(u"grpKpiCards")
        self.kpiGridLayout = QGridLayout(self.grpKpiCards)
        self.kpiGridLayout.setObjectName(u"kpiGridLayout")
        self.cardTodaySales = QFrame(self.grpKpiCards)
        self.cardTodaySales.setObjectName(u"cardTodaySales")
        self.cardTodaySalesLayout = QVBoxLayout(self.cardTodaySales)
        self.cardTodaySalesLayout.setObjectName(u"cardTodaySalesLayout")
        self.lblTodaySalesTitle = QLabel(self.cardTodaySales)
        self.lblTodaySalesTitle.setObjectName(u"lblTodaySalesTitle")

        self.cardTodaySalesLayout.addWidget(self.lblTodaySalesTitle)

        self.lblTodaySalesValue = QLabel(self.cardTodaySales)
        self.lblTodaySalesValue.setObjectName(u"lblTodaySalesValue")

        self.cardTodaySalesLayout.addWidget(self.lblTodaySalesValue)


        self.kpiGridLayout.addWidget(self.cardTodaySales, 0, 0, 1, 1)

        self.cardTodayPurchase = QFrame(self.grpKpiCards)
        self.cardTodayPurchase.setObjectName(u"cardTodayPurchase")
        self.cardTodayPurchaseLayout = QVBoxLayout(self.cardTodayPurchase)
        self.cardTodayPurchaseLayout.setObjectName(u"cardTodayPurchaseLayout")
        self.lblTodayPurchaseTitle = QLabel(self.cardTodayPurchase)
        self.lblTodayPurchaseTitle.setObjectName(u"lblTodayPurchaseTitle")

        self.cardTodayPurchaseLayout.addWidget(self.lblTodayPurchaseTitle)

        self.lblTodayPurchaseValue = QLabel(self.cardTodayPurchase)
        self.lblTodayPurchaseValue.setObjectName(u"lblTodayPurchaseValue")

        self.cardTodayPurchaseLayout.addWidget(self.lblTodayPurchaseValue)


        self.kpiGridLayout.addWidget(self.cardTodayPurchase, 0, 1, 1, 1)

        self.cardStockValue = QFrame(self.grpKpiCards)
        self.cardStockValue.setObjectName(u"cardStockValue")
        self.cardStockValueLayout = QVBoxLayout(self.cardStockValue)
        self.cardStockValueLayout.setObjectName(u"cardStockValueLayout")
        self.lblStockValueTitle = QLabel(self.cardStockValue)
        self.lblStockValueTitle.setObjectName(u"lblStockValueTitle")

        self.cardStockValueLayout.addWidget(self.lblStockValueTitle)

        self.lblStockValueValue = QLabel(self.cardStockValue)
        self.lblStockValueValue.setObjectName(u"lblStockValueValue")

        self.cardStockValueLayout.addWidget(self.lblStockValueValue)


        self.kpiGridLayout.addWidget(self.cardStockValue, 0, 2, 1, 1)

        self.cardLowStock = QFrame(self.grpKpiCards)
        self.cardLowStock.setObjectName(u"cardLowStock")
        self.cardLowStockLayout = QVBoxLayout(self.cardLowStock)
        self.cardLowStockLayout.setObjectName(u"cardLowStockLayout")
        self.lblLowStockTitle = QLabel(self.cardLowStock)
        self.lblLowStockTitle.setObjectName(u"lblLowStockTitle")

        self.cardLowStockLayout.addWidget(self.lblLowStockTitle)

        self.lblLowStockValue = QLabel(self.cardLowStock)
        self.lblLowStockValue.setObjectName(u"lblLowStockValue")

        self.cardLowStockLayout.addWidget(self.lblLowStockValue)


        self.kpiGridLayout.addWidget(self.cardLowStock, 0, 3, 1, 1)

        self.cardExpiring = QFrame(self.grpKpiCards)
        self.cardExpiring.setObjectName(u"cardExpiring")
        self.cardExpiringLayout = QVBoxLayout(self.cardExpiring)
        self.cardExpiringLayout.setObjectName(u"cardExpiringLayout")
        self.lblExpiringTitle = QLabel(self.cardExpiring)
        self.lblExpiringTitle.setObjectName(u"lblExpiringTitle")

        self.cardExpiringLayout.addWidget(self.lblExpiringTitle)

        self.lblExpiringValue = QLabel(self.cardExpiring)
        self.lblExpiringValue.setObjectName(u"lblExpiringValue")

        self.cardExpiringLayout.addWidget(self.lblExpiringValue)


        self.kpiGridLayout.addWidget(self.cardExpiring, 1, 0, 1, 1)

        self.cardPendingPayments = QFrame(self.grpKpiCards)
        self.cardPendingPayments.setObjectName(u"cardPendingPayments")
        self.cardPendingPaymentsLayout = QVBoxLayout(self.cardPendingPayments)
        self.cardPendingPaymentsLayout.setObjectName(u"cardPendingPaymentsLayout")
        self.lblPendingPaymentsTitle = QLabel(self.cardPendingPayments)
        self.lblPendingPaymentsTitle.setObjectName(u"lblPendingPaymentsTitle")

        self.cardPendingPaymentsLayout.addWidget(self.lblPendingPaymentsTitle)

        self.lblPendingPaymentsValue = QLabel(self.cardPendingPayments)
        self.lblPendingPaymentsValue.setObjectName(u"lblPendingPaymentsValue")

        self.cardPendingPaymentsLayout.addWidget(self.lblPendingPaymentsValue)


        self.kpiGridLayout.addWidget(self.cardPendingPayments, 1, 1, 1, 1)

        self.cardPendingReceipts = QFrame(self.grpKpiCards)
        self.cardPendingReceipts.setObjectName(u"cardPendingReceipts")
        self.cardPendingReceiptsLayout = QVBoxLayout(self.cardPendingReceipts)
        self.cardPendingReceiptsLayout.setObjectName(u"cardPendingReceiptsLayout")
        self.lblPendingReceiptsTitle = QLabel(self.cardPendingReceipts)
        self.lblPendingReceiptsTitle.setObjectName(u"lblPendingReceiptsTitle")

        self.cardPendingReceiptsLayout.addWidget(self.lblPendingReceiptsTitle)

        self.lblPendingReceiptsValue = QLabel(self.cardPendingReceipts)
        self.lblPendingReceiptsValue.setObjectName(u"lblPendingReceiptsValue")

        self.cardPendingReceiptsLayout.addWidget(self.lblPendingReceiptsValue)


        self.kpiGridLayout.addWidget(self.cardPendingReceipts, 1, 2, 1, 1)

        self.cardActiveUsers = QFrame(self.grpKpiCards)
        self.cardActiveUsers.setObjectName(u"cardActiveUsers")
        self.cardActiveUsersLayout = QVBoxLayout(self.cardActiveUsers)
        self.cardActiveUsersLayout.setObjectName(u"cardActiveUsersLayout")
        self.lblActiveUsersTitle = QLabel(self.cardActiveUsers)
        self.lblActiveUsersTitle.setObjectName(u"lblActiveUsersTitle")

        self.cardActiveUsersLayout.addWidget(self.lblActiveUsersTitle)

        self.lblActiveUsersValue = QLabel(self.cardActiveUsers)
        self.lblActiveUsersValue.setObjectName(u"lblActiveUsersValue")

        self.cardActiveUsersLayout.addWidget(self.lblActiveUsersValue)


        self.kpiGridLayout.addWidget(self.cardActiveUsers, 1, 3, 1, 1)


        self.mainAreaLayout.addWidget(self.grpKpiCards)

        self.grpQuickActions = QGroupBox(self.scrollAreaContents)
        self.grpQuickActions.setObjectName(u"grpQuickActions")
        self.quickActionsLayout = QHBoxLayout(self.grpQuickActions)
        self.quickActionsLayout.setObjectName(u"quickActionsLayout")
        self.btnNewSale = QPushButton(self.grpQuickActions)
        self.btnNewSale.setObjectName(u"btnNewSale")

        self.quickActionsLayout.addWidget(self.btnNewSale)

        self.btnNewPurchase = QPushButton(self.grpQuickActions)
        self.btnNewPurchase.setObjectName(u"btnNewPurchase")

        self.quickActionsLayout.addWidget(self.btnNewPurchase)

        self.btnAddCustomer = QPushButton(self.grpQuickActions)
        self.btnAddCustomer.setObjectName(u"btnAddCustomer")

        self.quickActionsLayout.addWidget(self.btnAddCustomer)

        self.btnAddSupplier = QPushButton(self.grpQuickActions)
        self.btnAddSupplier.setObjectName(u"btnAddSupplier")

        self.quickActionsLayout.addWidget(self.btnAddSupplier)

        self.btnAddItem = QPushButton(self.grpQuickActions)
        self.btnAddItem.setObjectName(u"btnAddItem")

        self.quickActionsLayout.addWidget(self.btnAddItem)

        self.btnBackupDatabase = QPushButton(self.grpQuickActions)
        self.btnBackupDatabase.setObjectName(u"btnBackupDatabase")

        self.quickActionsLayout.addWidget(self.btnBackupDatabase)


        self.mainAreaLayout.addWidget(self.grpQuickActions)

        self.grpActivityArea = QGroupBox(self.scrollAreaContents)
        self.grpActivityArea.setObjectName(u"grpActivityArea")
        self.activityAreaGridLayout = QGridLayout(self.grpActivityArea)
        self.activityAreaGridLayout.setObjectName(u"activityAreaGridLayout")
        self.grpAlerts = QGroupBox(self.grpActivityArea)
        self.grpAlerts.setObjectName(u"grpAlerts")
        self.alertsLayout = QVBoxLayout(self.grpAlerts)
        self.alertsLayout.setObjectName(u"alertsLayout")
        self.lstAlerts = QListWidget(self.grpAlerts)
        self.lstAlerts.setObjectName(u"lstAlerts")

        self.alertsLayout.addWidget(self.lstAlerts)


        self.activityAreaGridLayout.addWidget(self.grpAlerts, 0, 0, 1, 1)

        self.grpRecentActivity = QGroupBox(self.grpActivityArea)
        self.grpRecentActivity.setObjectName(u"grpRecentActivity")
        self.recentActivityLayout = QVBoxLayout(self.grpRecentActivity)
        self.recentActivityLayout.setObjectName(u"recentActivityLayout")
        self.lstRecentActivity = QListWidget(self.grpRecentActivity)
        self.lstRecentActivity.setObjectName(u"lstRecentActivity")

        self.recentActivityLayout.addWidget(self.lstRecentActivity)


        self.activityAreaGridLayout.addWidget(self.grpRecentActivity, 0, 1, 1, 1)

        self.grpFavorites = QGroupBox(self.grpActivityArea)
        self.grpFavorites.setObjectName(u"grpFavorites")
        self.favoritesLayout = QVBoxLayout(self.grpFavorites)
        self.favoritesLayout.setObjectName(u"favoritesLayout")
        self.lstFavorites = QListWidget(self.grpFavorites)
        self.lstFavorites.setObjectName(u"lstFavorites")

        self.favoritesLayout.addWidget(self.lstFavorites)


        self.activityAreaGridLayout.addWidget(self.grpFavorites, 1, 0, 1, 1)

        self.grpRecentlyOpened = QGroupBox(self.grpActivityArea)
        self.grpRecentlyOpened.setObjectName(u"grpRecentlyOpened")
        self.recentlyOpenedLayout = QVBoxLayout(self.grpRecentlyOpened)
        self.recentlyOpenedLayout.setObjectName(u"recentlyOpenedLayout")
        self.lstRecentlyOpened = QListWidget(self.grpRecentlyOpened)
        self.lstRecentlyOpened.setObjectName(u"lstRecentlyOpened")

        self.recentlyOpenedLayout.addWidget(self.lstRecentlyOpened)


        self.activityAreaGridLayout.addWidget(self.grpRecentlyOpened, 1, 1, 1, 1)


        self.mainAreaLayout.addWidget(self.grpActivityArea)

        self.scrollMainArea.setWidget(self.scrollAreaContents)
        self.bodySplitter.addWidget(self.scrollMainArea)

        self.mainVerticalLayout.addWidget(self.bodySplitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.lblDashboardClock = QLabel(self.statusbar)
        self.lblDashboardClock.setObjectName(u"lblDashboardClock")
        self.lblDashboardClock.setMinimumWidth(260)
        self.lblDashboardClock.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Medical ERP Dashboard", None))
        self.lblCompanyLogoSmall.setText(QCoreApplication.translate("MainWindow", u"[Logo]", None))
        self.lblCompanyNameHeader.setText(QCoreApplication.translate("MainWindow", u"Company Name", None))
        self.txtSearchMenu.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Search menu...", None))
        self.lblLoggedInUser.setText(QCoreApplication.translate("MainWindow", u"User", None))
        self.lblUserRole.setText(QCoreApplication.translate("MainWindow", u"Role", None))
        self.lblCurrentFinancialYearHeader.setText(QCoreApplication.translate("MainWindow", u"FY", None))
        self.btnNotifications.setText(QCoreApplication.translate("MainWindow", u"Alerts (0)", None))
        self.btnTheme.setText(QCoreApplication.translate("MainWindow", u"Theme", None))
        self.btnLogout.setText(QCoreApplication.translate("MainWindow", u"Logout", None))
        self.lblMenuTitle.setText(QCoreApplication.translate("MainWindow", u"Modules", None))
        ___qtreewidgetitem = self.treeSidebarMenu.headerItem()
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("MainWindow", u"Menu", None))
        self.grpKpiCards.setTitle(QCoreApplication.translate("MainWindow", u"Overview", None))
        self.lblTodaySalesTitle.setText(QCoreApplication.translate("MainWindow", u"Today's Sales", None))
        self.lblTodaySalesValue.setText(QCoreApplication.translate("MainWindow", u"0.00", None))
        self.lblTodayPurchaseTitle.setText(QCoreApplication.translate("MainWindow", u"Today's Purchase", None))
        self.lblTodayPurchaseValue.setText(QCoreApplication.translate("MainWindow", u"0.00", None))
        self.lblStockValueTitle.setText(QCoreApplication.translate("MainWindow", u"Stock Value", None))
        self.lblStockValueValue.setText(QCoreApplication.translate("MainWindow", u"0.00", None))
        self.lblLowStockTitle.setText(QCoreApplication.translate("MainWindow", u"Low Stock Items", None))
        self.lblLowStockValue.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.lblExpiringTitle.setText(QCoreApplication.translate("MainWindow", u"Expiring Medicines", None))
        self.lblExpiringValue.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.lblPendingPaymentsTitle.setText(QCoreApplication.translate("MainWindow", u"Pending Payments", None))
        self.lblPendingPaymentsValue.setText(QCoreApplication.translate("MainWindow", u"0.00", None))
        self.lblPendingReceiptsTitle.setText(QCoreApplication.translate("MainWindow", u"Pending Receipts", None))
        self.lblPendingReceiptsValue.setText(QCoreApplication.translate("MainWindow", u"0.00", None))
        self.lblActiveUsersTitle.setText(QCoreApplication.translate("MainWindow", u"Active Users", None))
        self.lblActiveUsersValue.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.grpQuickActions.setTitle(QCoreApplication.translate("MainWindow", u"Quick Actions", None))
        self.btnNewSale.setText(QCoreApplication.translate("MainWindow", u"New Sale", None))
        self.btnNewPurchase.setText(QCoreApplication.translate("MainWindow", u"New Purchase", None))
        self.btnAddCustomer.setText(QCoreApplication.translate("MainWindow", u"Add Customer", None))
        self.btnAddSupplier.setText(QCoreApplication.translate("MainWindow", u"Add Supplier", None))
        self.btnAddItem.setText(QCoreApplication.translate("MainWindow", u"Add Item", None))
        self.btnBackupDatabase.setText(QCoreApplication.translate("MainWindow", u"Backup Database", None))
        self.grpActivityArea.setTitle(QCoreApplication.translate("MainWindow", u"Favorites & Activity", None))
        self.grpAlerts.setTitle(QCoreApplication.translate("MainWindow", u"Alerts", None))
        self.grpRecentActivity.setTitle(QCoreApplication.translate("MainWindow", u"Recent Activities", None))
        self.grpFavorites.setTitle(QCoreApplication.translate("MainWindow", u"Favorites", None))
        self.grpRecentlyOpened.setTitle(QCoreApplication.translate("MainWindow", u"Recently Opened", None))
        self.lblDashboardClock.setText(QCoreApplication.translate("MainWindow", u"00:00:00", None))
    # retranslateUi

