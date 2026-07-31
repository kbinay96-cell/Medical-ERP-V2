# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settings.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSplitter,
    QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget)

class Ui_SettingsScreen(object):
    def setupUi(self, SettingsScreen):
        if not SettingsScreen.objectName():
            SettingsScreen.setObjectName(u"SettingsScreen")
        SettingsScreen.resize(1100, 720)
        self.centralwidget = QWidget(SettingsScreen)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayoutMain = QVBoxLayout(self.centralwidget)
        self.verticalLayoutMain.setSpacing(0)
        self.verticalLayoutMain.setObjectName(u"verticalLayoutMain")
        self.verticalLayoutMain.setContentsMargins(0, 0, 0, 0)
        self.frmHeader = QFrame(self.centralwidget)
        self.frmHeader.setObjectName(u"frmHeader")
        self.frmHeader.setMinimumSize(QSize(0, 56))
        self.frmHeader.setMaximumHeight(56)
        self.frmHeader.setFrameShape(QFrame.NoFrame)
        self.horizontalLayoutHeader = QHBoxLayout(self.frmHeader)
        self.horizontalLayoutHeader.setObjectName(u"horizontalLayoutHeader")
        self.horizontalLayoutHeader.setContentsMargins(16, 8, 16, 8)
        self.lblSettingsIcon = QLabel(self.frmHeader)
        self.lblSettingsIcon.setObjectName(u"lblSettingsIcon")
        self.lblSettingsIcon.setMinimumSize(QSize(24, 24))
        self.lblSettingsIcon.setMaximumSize(QSize(24, 24))
        self.lblSettingsIcon.setPixmap(QPixmap(u"resources/icons/settings.svg"))
        self.lblSettingsIcon.setScaledContents(True)

        self.horizontalLayoutHeader.addWidget(self.lblSettingsIcon)

        self.lblSettingsTitle = QLabel(self.frmHeader)
        self.lblSettingsTitle.setObjectName(u"lblSettingsTitle")
        self.lblSettingsTitle.setStyleSheet(u"font-size: 18px; font-weight: 600;")

        self.horizontalLayoutHeader.addWidget(self.lblSettingsTitle)

        self.horizontalSpacerHeader = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayoutHeader.addItem(self.horizontalSpacerHeader)

        self.frmSearchBox = QFrame(self.frmHeader)
        self.frmSearchBox.setObjectName(u"frmSearchBox")
        self.frmSearchBox.setMinimumSize(QSize(260, 36))
        self.frmSearchBox.setMaximumSize(QSize(360, 36))
        self.frmSearchBox.setProperty(u"cssClass", u"searchBox")
        self.horizontalLayoutSearchBox = QHBoxLayout(self.frmSearchBox)
        self.horizontalLayoutSearchBox.setObjectName(u"horizontalLayoutSearchBox")
        self.horizontalLayoutSearchBox.setContentsMargins(10, 2, 10, 2)
        self.lblSearchIcon = QLabel(self.frmSearchBox)
        self.lblSearchIcon.setObjectName(u"lblSearchIcon")
        self.lblSearchIcon.setMinimumSize(QSize(16, 16))
        self.lblSearchIcon.setMaximumSize(QSize(16, 16))
        self.lblSearchIcon.setPixmap(QPixmap(u"resources/icons/search.svg"))
        self.lblSearchIcon.setScaledContents(True)

        self.horizontalLayoutSearchBox.addWidget(self.lblSearchIcon)

        self.txtSearch = QLineEdit(self.frmSearchBox)
        self.txtSearch.setObjectName(u"txtSearch")
        self.txtSearch.setFrame(False)

        self.horizontalLayoutSearchBox.addWidget(self.txtSearch)


        self.horizontalLayoutHeader.addWidget(self.frmSearchBox)


        self.verticalLayoutMain.addWidget(self.frmHeader)

        self.splitterMain = QSplitter(self.centralwidget)
        self.splitterMain.setObjectName(u"splitterMain")
        self.splitterMain.setOrientation(Qt.Horizontal)
        self.splitterMain.setChildrenCollapsible(False)
        self.frmCategoryPanel = QWidget(self.splitterMain)
        self.frmCategoryPanel.setObjectName(u"frmCategoryPanel")
        self.frmCategoryPanel.setMinimumSize(QSize(220, 0))
        self.frmCategoryPanel.setMaximumSize(QSize(320, 16777215))
        self.verticalLayoutCategoryPanel = QVBoxLayout(self.frmCategoryPanel)
        self.verticalLayoutCategoryPanel.setObjectName(u"verticalLayoutCategoryPanel")
        self.verticalLayoutCategoryPanel.setContentsMargins(0, 0, 0, 0)
        self.treeCategories = QTreeWidget(self.frmCategoryPanel)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(0, u"Category")
        self.treeCategories.setHeaderItem(__qtreewidgetitem)
        self.treeCategories.setObjectName(u"treeCategories")
        self.treeCategories.setHeaderHidden(True)
        self.treeCategories.setRootIsDecorated(False)
        self.treeCategories.setIndentation(14)

        self.verticalLayoutCategoryPanel.addWidget(self.treeCategories)

        self.splitterMain.addWidget(self.frmCategoryPanel)
        self.frmSettingsPanel = QWidget(self.splitterMain)
        self.frmSettingsPanel.setObjectName(u"frmSettingsPanel")
        self.verticalLayoutSettingsPanel = QVBoxLayout(self.frmSettingsPanel)
        self.verticalLayoutSettingsPanel.setObjectName(u"verticalLayoutSettingsPanel")
        self.verticalLayoutSettingsPanel.setContentsMargins(16, 12, 16, 12)
        self.horizontalLayoutCategoryTitle = QHBoxLayout()
        self.horizontalLayoutCategoryTitle.setObjectName(u"horizontalLayoutCategoryTitle")
        self.lblCategoryTitle = QLabel(self.frmSettingsPanel)
        self.lblCategoryTitle.setObjectName(u"lblCategoryTitle")
        self.lblCategoryTitle.setStyleSheet(u"font-size: 16px; font-weight: 600;")

        self.horizontalLayoutCategoryTitle.addWidget(self.lblCategoryTitle)

        self.horizontalSpacerCategoryTitle = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayoutCategoryTitle.addItem(self.horizontalSpacerCategoryTitle)

        self.btnRestoreDefault = QPushButton(self.frmSettingsPanel)
        self.btnRestoreDefault.setObjectName(u"btnRestoreDefault")
        self.btnRestoreDefault.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayoutCategoryTitle.addWidget(self.btnRestoreDefault)


        self.verticalLayoutSettingsPanel.addLayout(self.horizontalLayoutCategoryTitle)

        self.scrollAreaSettings = QScrollArea(self.frmSettingsPanel)
        self.scrollAreaSettings.setObjectName(u"scrollAreaSettings")
        self.scrollAreaSettings.setWidgetResizable(True)
        self.scrollAreaSettings.setFrameShape(QFrame.NoFrame)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 600, 500))
        self.dynamicSettingsLayout = QVBoxLayout(self.scrollAreaWidgetContents)
        self.dynamicSettingsLayout.setSpacing(4)
        self.dynamicSettingsLayout.setObjectName(u"dynamicSettingsLayout")
        self.scrollAreaSettings.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayoutSettingsPanel.addWidget(self.scrollAreaSettings)

        self.splitterMain.addWidget(self.frmSettingsPanel)

        self.verticalLayoutMain.addWidget(self.splitterMain, 1)

        self.frmFooter = QFrame(self.centralwidget)
        self.frmFooter.setObjectName(u"frmFooter")
        self.frmFooter.setMinimumSize(QSize(0, 52))
        self.frmFooter.setMaximumHeight(52)
        self.frmFooter.setFrameShape(QFrame.NoFrame)
        self.horizontalLayoutFooter = QHBoxLayout(self.frmFooter)
        self.horizontalLayoutFooter.setObjectName(u"horizontalLayoutFooter")
        self.horizontalLayoutFooter.setContentsMargins(16, 8, 16, 8)
        self.lblUnsavedIndicator = QLabel(self.frmFooter)
        self.lblUnsavedIndicator.setObjectName(u"lblUnsavedIndicator")
        self.lblUnsavedIndicator.setProperty(u"cssClass", u"unsavedIndicator")

        self.horizontalLayoutFooter.addWidget(self.lblUnsavedIndicator)

        self.horizontalSpacerFooter = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayoutFooter.addItem(self.horizontalSpacerFooter)

        self.btnImport = QPushButton(self.frmFooter)
        self.btnImport.setObjectName(u"btnImport")
        self.btnImport.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayoutFooter.addWidget(self.btnImport)

        self.btnExport = QPushButton(self.frmFooter)
        self.btnExport.setObjectName(u"btnExport")
        self.btnExport.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayoutFooter.addWidget(self.btnExport)

        self.btnApply = QPushButton(self.frmFooter)
        self.btnApply.setObjectName(u"btnApply")
        self.btnApply.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayoutFooter.addWidget(self.btnApply)

        self.btnSave = QPushButton(self.frmFooter)
        self.btnSave.setObjectName(u"btnSave")
        self.btnSave.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSave.setProperty(u"cssClass", u"primaryButton")

        self.horizontalLayoutFooter.addWidget(self.btnSave)

        self.btnClose = QPushButton(self.frmFooter)
        self.btnClose.setObjectName(u"btnClose")
        self.btnClose.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.horizontalLayoutFooter.addWidget(self.btnClose)


        self.verticalLayoutMain.addWidget(self.frmFooter)

        SettingsScreen.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(SettingsScreen)
        self.statusbar.setObjectName(u"statusbar")
        SettingsScreen.setStatusBar(self.statusbar)

        self.retranslateUi(SettingsScreen)

        QMetaObject.connectSlotsByName(SettingsScreen)
    # setupUi

    def retranslateUi(self, SettingsScreen):
        SettingsScreen.setWindowTitle(QCoreApplication.translate("SettingsScreen", u"Settings", None))
        self.lblSettingsTitle.setText(QCoreApplication.translate("SettingsScreen", u"Settings", None))
        self.txtSearch.setPlaceholderText(QCoreApplication.translate("SettingsScreen", u"Search settings...", None))
        self.lblCategoryTitle.setText(QCoreApplication.translate("SettingsScreen", u"General", None))
        self.btnRestoreDefault.setText(QCoreApplication.translate("SettingsScreen", u"Restore Default", None))
        self.lblUnsavedIndicator.setText("")
        self.btnImport.setText(QCoreApplication.translate("SettingsScreen", u"Import", None))
        self.btnExport.setText(QCoreApplication.translate("SettingsScreen", u"Export", None))
        self.btnApply.setText(QCoreApplication.translate("SettingsScreen", u"Apply", None))
        self.btnSave.setText(QCoreApplication.translate("SettingsScreen", u"Save", None))
        self.btnClose.setText(QCoreApplication.translate("SettingsScreen", u"Close", None))
    # retranslateUi

