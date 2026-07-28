# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'login.ui'
## Hand-written to mirror pyside6-uic output style (Qt Designer/pyside6-uic
## are not available in Claude's sandbox - see README "Known limitations").
## Re-generate with: pyside6-uic ui\login.ui -o ui\ui_login.py
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget,
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1200, 720)
        MainWindow.setMinimumSize(QSize(1024, 640))
        MainWindow.setWindowTitle(u"Medical ERP Login")

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")

        self.mainVerticalLayout = QVBoxLayout(self.centralwidget)
        self.mainVerticalLayout.setObjectName(u"mainVerticalLayout")
        self.mainVerticalLayout.setSpacing(0)
        self.mainVerticalLayout.setContentsMargins(0, 0, 0, 0)

        # ================= HEADER =================
        self.frmHeader = QFrame(self.centralwidget)
        self.frmHeader.setObjectName(u"frmHeader")
        self.frmHeader.setMinimumSize(QSize(0, 42))
        self.headerLayout = QHBoxLayout(self.frmHeader)
        self.headerLayout.setObjectName(u"headerLayout")
        self.headerLayout.setContentsMargins(16, 6, 16, 6)

        self.lblERPName = QLabel(self.frmHeader); self.lblERPName.setObjectName(u"lblERPName")
        self.headerLayout.addWidget(self.lblERPName)
        self.lblVersion = QLabel(self.frmHeader); self.lblVersion.setObjectName(u"lblVersion")
        self.headerLayout.addWidget(self.lblVersion)
        self.lblLicense = QLabel(self.frmHeader); self.lblLicense.setObjectName(u"lblLicense")
        self.headerLayout.addWidget(self.lblLicense)
        self.lblDatabase = QLabel(self.frmHeader); self.lblDatabase.setObjectName(u"lblDatabase")
        self.headerLayout.addWidget(self.lblDatabase)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.headerLayout.addItem(self.headerSpacer)

        self.lblCurrentTime = QLabel(self.frmHeader); self.lblCurrentTime.setObjectName(u"lblCurrentTime")
        self.headerLayout.addWidget(self.lblCurrentTime)

        self.mainVerticalLayout.addWidget(self.frmHeader)

        # ================= BODY =================
        self.bodyLayout = QHBoxLayout()
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.bodyLayout.setSpacing(0)

        # ---------- LEFT BRANDING PANEL ----------
        self.frmLeftPanel = QFrame(self.centralwidget)
        self.frmLeftPanel.setObjectName(u"frmLeftPanel")
        self.frmLeftPanel.setMinimumSize(QSize(360, 0))
        left_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_policy.setHorizontalStretch(4)
        self.frmLeftPanel.setSizePolicy(left_policy)

        self.leftPanelLayout = QVBoxLayout(self.frmLeftPanel)
        self.leftPanelLayout.setObjectName(u"leftPanelLayout")
        self.leftPanelLayout.setContentsMargins(40, 50, 40, 30)
        self.leftPanelLayout.setSpacing(6)

        self.lblCompanyLogo = QLabel(self.frmLeftPanel); self.lblCompanyLogo.setObjectName(u"lblCompanyLogo")
        self.lblCompanyLogo.setMinimumSize(QSize(64, 64))
        self.leftPanelLayout.addWidget(self.lblCompanyLogo)

        self.lblErpLogo = QLabel(self.frmLeftPanel); self.lblErpLogo.setObjectName(u"lblErpLogo")
        self.leftPanelLayout.addWidget(self.lblErpLogo)

        self.lblWelcomeMessage = QLabel(self.frmLeftPanel); self.lblWelcomeMessage.setObjectName(u"lblWelcomeMessage")
        self.leftPanelLayout.addWidget(self.lblWelcomeMessage)

        self.lblOrganizationName = QLabel(self.frmLeftPanel); self.lblOrganizationName.setObjectName(u"lblOrganizationName")
        self.leftPanelLayout.addWidget(self.lblOrganizationName)

        self.lblBranchName = QLabel(self.frmLeftPanel); self.lblBranchName.setObjectName(u"lblBranchName")
        self.leftPanelLayout.addWidget(self.lblBranchName)

        self.lblErpVersionInfo = QLabel(self.frmLeftPanel); self.lblErpVersionInfo.setObjectName(u"lblErpVersionInfo")
        self.leftPanelLayout.addWidget(self.lblErpVersionInfo)

        self.lblTagline = QLabel(self.frmLeftPanel); self.lblTagline.setObjectName(u"lblTagline")
        self.leftPanelLayout.addWidget(self.lblTagline)

        self.leftPanelSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.leftPanelLayout.addItem(self.leftPanelSpacer)

        self.lblQuickInfoTitle = QLabel(self.frmLeftPanel); self.lblQuickInfoTitle.setObjectName(u"lblQuickInfoTitle")
        self.leftPanelLayout.addWidget(self.lblQuickInfoTitle)
        self.lblDatabaseStatus = QLabel(self.frmLeftPanel); self.lblDatabaseStatus.setObjectName(u"lblDatabaseStatus")
        self.leftPanelLayout.addWidget(self.lblDatabaseStatus)
        self.lblLicenseStatus = QLabel(self.frmLeftPanel); self.lblLicenseStatus.setObjectName(u"lblLicenseStatus")
        self.leftPanelLayout.addWidget(self.lblLicenseStatus)
        self.lblSubscriptionStatus = QLabel(self.frmLeftPanel); self.lblSubscriptionStatus.setObjectName(u"lblSubscriptionStatus")
        self.leftPanelLayout.addWidget(self.lblSubscriptionStatus)
        self.lblTodayDate = QLabel(self.frmLeftPanel); self.lblTodayDate.setObjectName(u"lblTodayDate")
        self.leftPanelLayout.addWidget(self.lblTodayDate)
        self.lblCurrentFinancialYear = QLabel(self.frmLeftPanel); self.lblCurrentFinancialYear.setObjectName(u"lblCurrentFinancialYear")
        self.leftPanelLayout.addWidget(self.lblCurrentFinancialYear)
        self.lblCopyright = QLabel(self.frmLeftPanel); self.lblCopyright.setObjectName(u"lblCopyright")
        self.leftPanelLayout.addWidget(self.lblCopyright)

        self.bodyLayout.addWidget(self.frmLeftPanel)

        # ---------- RIGHT CONTAINER (centers the login card) ----------
        self.loginRightContainer = QWidget(self.centralwidget)
        self.loginRightContainer.setObjectName(u"loginRightContainer")
        right_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_policy.setHorizontalStretch(6)
        self.loginRightContainer.setSizePolicy(right_policy)

        self.loginRightVLayout = QVBoxLayout(self.loginRightContainer)
        self.loginRightVLayout.setObjectName(u"loginRightVLayout")

        self.loginCardTopSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.loginRightVLayout.addItem(self.loginCardTopSpacer)

        self.loginCardHLayout = QHBoxLayout()
        self.loginCardHLayout.setObjectName(u"loginCardHLayout")

        self.loginCardLeftSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.loginCardHLayout.addItem(self.loginCardLeftSpacer)

        # ---------- LOGIN CARD ----------
        self.frmLoginPanel = QFrame(self.loginRightContainer)
        self.frmLoginPanel.setObjectName(u"frmLoginPanel")
        self.frmLoginPanel.setMinimumSize(QSize(420, 0))
        self.frmLoginPanel.setMaximumSize(QSize(460, 16777215))

        self.loginPanelLayout = QVBoxLayout(self.frmLoginPanel)
        self.loginPanelLayout.setObjectName(u"loginPanelLayout")
        self.loginPanelLayout.setContentsMargins(36, 36, 36, 28)
        self.loginPanelLayout.setSpacing(14)

        self.lblLoginIcon = QLabel(self.frmLoginPanel)
        self.lblLoginIcon.setObjectName(u"lblLoginIcon")
        self.lblLoginIcon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lblLoginIcon.setMinimumSize(QSize(0, 48))
        self.loginPanelLayout.addWidget(self.lblLoginIcon)

        self.lblLoginTitle = QLabel(self.frmLoginPanel)
        self.lblLoginTitle.setObjectName(u"lblLoginTitle")
        self.lblLoginTitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.loginPanelLayout.addWidget(self.lblLoginTitle)

        self.loginFormLayout = QFormLayout()
        self.loginFormLayout.setObjectName(u"loginFormLayout")
        self.loginFormLayout.setVerticalSpacing(14)
        self.loginFormLayout.setHorizontalSpacing(10)

        self.lblUsername = QLabel(self.frmLoginPanel); self.lblUsername.setObjectName(u"lblUsername")
        self.txtUsername = QLineEdit(self.frmLoginPanel); self.txtUsername.setObjectName(u"txtUsername")
        self.txtUsername.setMinimumSize(QSize(0, 36))
        self.lblUsername.setBuddy(self.txtUsername)
        self.loginFormLayout.addRow(self.lblUsername, self.txtUsername)

        self.lblPassword = QLabel(self.frmLoginPanel); self.lblPassword.setObjectName(u"lblPassword")
        self.txtPassword = QLineEdit(self.frmLoginPanel); self.txtPassword.setObjectName(u"txtPassword")
        self.txtPassword.setMinimumSize(QSize(0, 36))
        self.txtPassword.setEchoMode(QLineEdit.EchoMode.Password)
        self.lblPassword.setBuddy(self.txtPassword)
        self.loginFormLayout.addRow(self.lblPassword, self.txtPassword)

        self.lblCompany = QLabel(self.frmLoginPanel); self.lblCompany.setObjectName(u"lblCompany")
        self.cmbCompany = QComboBox(self.frmLoginPanel); self.cmbCompany.setObjectName(u"cmbCompany")
        self.cmbCompany.setMinimumSize(QSize(0, 36))
        self.lblCompany.setBuddy(self.cmbCompany)
        self.loginFormLayout.addRow(self.lblCompany, self.cmbCompany)

        self.lblFinancialYear = QLabel(self.frmLoginPanel); self.lblFinancialYear.setObjectName(u"lblFinancialYear")
        self.cmbFinancialYear = QComboBox(self.frmLoginPanel); self.cmbFinancialYear.setObjectName(u"cmbFinancialYear")
        self.cmbFinancialYear.setMinimumSize(QSize(0, 36))
        self.lblFinancialYear.setBuddy(self.cmbFinancialYear)
        self.loginFormLayout.addRow(self.lblFinancialYear, self.cmbFinancialYear)

        self.loginPanelLayout.addLayout(self.loginFormLayout)

        self.checkboxRowLayout = QHBoxLayout()
        self.checkboxRowLayout.setObjectName(u"checkboxRowLayout")
        self.chkRememberMe = QCheckBox(self.frmLoginPanel); self.chkRememberMe.setObjectName(u"chkRememberMe")
        self.checkboxRowLayout.addWidget(self.chkRememberMe)
        self.checkboxRowSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.checkboxRowLayout.addItem(self.checkboxRowSpacer)
        self.chkShowPassword = QCheckBox(self.frmLoginPanel); self.chkShowPassword.setObjectName(u"chkShowPassword")
        self.checkboxRowLayout.addWidget(self.chkShowPassword)
        self.loginPanelLayout.addLayout(self.checkboxRowLayout)

        self.lblCapsLock = QLabel(self.frmLoginPanel); self.lblCapsLock.setObjectName(u"lblCapsLock")
        self.loginPanelLayout.addWidget(self.lblCapsLock)
        self.lblConnectionStatus = QLabel(self.frmLoginPanel); self.lblConnectionStatus.setObjectName(u"lblConnectionStatus")
        self.loginPanelLayout.addWidget(self.lblConnectionStatus)
        self.lblLoginMessage = QLabel(self.frmLoginPanel); self.lblLoginMessage.setObjectName(u"lblLoginMessage")
        self.lblLoginMessage.setWordWrap(True)
        self.loginPanelLayout.addWidget(self.lblLoginMessage)

        self.loginButtonRowLayout = QHBoxLayout()
        self.loginButtonRowLayout.setObjectName(u"loginButtonRowLayout")
        self.btnLogin = QPushButton(self.frmLoginPanel); self.btnLogin.setObjectName(u"btnLogin")
        self.btnLogin.setMinimumSize(QSize(0, 40))
        self.btnLogin.setDefault(True)
        self.loginButtonRowLayout.addWidget(self.btnLogin)
        self.btnExit = QPushButton(self.frmLoginPanel); self.btnExit.setObjectName(u"btnExit")
        self.btnExit.setMinimumSize(QSize(0, 40))
        self.loginButtonRowLayout.addWidget(self.btnExit)
        self.loginPanelLayout.addLayout(self.loginButtonRowLayout)

        self.loginExtraButtonRowLayout = QHBoxLayout()
        self.loginExtraButtonRowLayout.setObjectName(u"loginExtraButtonRowLayout")
        self.btnForgotPassword = QPushButton(self.frmLoginPanel); self.btnForgotPassword.setObjectName(u"btnForgotPassword")
        self.btnForgotPassword.setFlat(True)
        self.loginExtraButtonRowLayout.addWidget(self.btnForgotPassword)
        self.extraButtonSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.loginExtraButtonRowLayout.addItem(self.extraButtonSpacer)
        self.btnChangeLanguage = QPushButton(self.frmLoginPanel); self.btnChangeLanguage.setObjectName(u"btnChangeLanguage")
        self.btnChangeLanguage.setFlat(True)
        self.loginExtraButtonRowLayout.addWidget(self.btnChangeLanguage)
        self.btnTheme = QPushButton(self.frmLoginPanel); self.btnTheme.setObjectName(u"btnTheme")
        self.btnTheme.setFlat(True)
        self.loginExtraButtonRowLayout.addWidget(self.btnTheme)
        self.loginPanelLayout.addLayout(self.loginExtraButtonRowLayout)

        self.loginCardHLayout.addWidget(self.frmLoginPanel)

        self.loginCardRightSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.loginCardHLayout.addItem(self.loginCardRightSpacer)

        self.loginRightVLayout.addLayout(self.loginCardHLayout)

        self.loginCardBottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.loginRightVLayout.addItem(self.loginCardBottomSpacer)

        self.bodyLayout.addWidget(self.loginRightContainer)

        self.mainVerticalLayout.addLayout(self.bodyLayout)

        # ================= FOOTER =================
        self.frmFooter = QFrame(self.centralwidget)
        self.frmFooter.setObjectName(u"frmFooter")
        self.frmFooter.setMinimumSize(QSize(0, 34))
        self.footerLayout = QHBoxLayout(self.frmFooter)
        self.footerLayout.setObjectName(u"footerLayout")
        self.footerLayout.setContentsMargins(16, 4, 16, 4)

        self.lblFooterVersion = QLabel(self.frmFooter); self.lblFooterVersion.setObjectName(u"lblFooterVersion")
        self.footerLayout.addWidget(self.lblFooterVersion)
        self.lblFooterBuild = QLabel(self.frmFooter); self.lblFooterBuild.setObjectName(u"lblFooterBuild")
        self.footerLayout.addWidget(self.lblFooterBuild)
        self.lblFooterDbVersion = QLabel(self.frmFooter); self.lblFooterDbVersion.setObjectName(u"lblFooterDbVersion")
        self.footerLayout.addWidget(self.lblFooterDbVersion)
        self.lblFooterServer = QLabel(self.frmFooter); self.lblFooterServer.setObjectName(u"lblFooterServer")
        self.footerLayout.addWidget(self.lblFooterServer)

        self.footerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.footerLayout.addItem(self.footerSpacer)

        self.lblFooterDeveloper = QLabel(self.frmFooter); self.lblFooterDeveloper.setObjectName(u"lblFooterDeveloper")
        self.footerLayout.addWidget(self.lblFooterDeveloper)
        self.lblFooterSupport = QLabel(self.frmFooter); self.lblFooterSupport.setObjectName(u"lblFooterSupport")
        self.footerLayout.addWidget(self.lblFooterSupport)
        self.lblFooterWebsite = QLabel(self.frmFooter); self.lblFooterWebsite.setObjectName(u"lblFooterWebsite")
        self.footerLayout.addWidget(self.lblFooterWebsite)
        self.lblFooterCopyright = QLabel(self.frmFooter); self.lblFooterCopyright.setObjectName(u"lblFooterCopyright")
        self.footerLayout.addWidget(self.lblFooterCopyright)

        self.mainVerticalLayout.addWidget(self.frmFooter)

        MainWindow.setCentralWidget(self.centralwidget)

        MainWindow.setTabOrder(self.txtUsername, self.txtPassword)
        MainWindow.setTabOrder(self.txtPassword, self.cmbCompany)
        MainWindow.setTabOrder(self.cmbCompany, self.cmbFinancialYear)
        MainWindow.setTabOrder(self.cmbFinancialYear, self.chkRememberMe)
        MainWindow.setTabOrder(self.chkRememberMe, self.chkShowPassword)
        MainWindow.setTabOrder(self.chkShowPassword, self.btnLogin)
        MainWindow.setTabOrder(self.btnLogin, self.btnExit)

        self.retranslateUi(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Medical ERP Login", None))
        self.lblERPName.setText(QCoreApplication.translate("MainWindow", u"Medical ERP", None))
        self.lblVersion.setText(QCoreApplication.translate("MainWindow", u"v2.0.0", None))
        self.lblLicense.setText(QCoreApplication.translate("MainWindow", u"License: --", None))
        self.lblDatabase.setText(QCoreApplication.translate("MainWindow", u"Database: --", None))
        self.lblCurrentTime.setText(QCoreApplication.translate("MainWindow", u"00:00:00", None))

        self.lblCompanyLogo.setText(QCoreApplication.translate("MainWindow", u"[Logo]", None))
        self.lblErpLogo.setText(QCoreApplication.translate("MainWindow", u"[ERP Logo]", None))
        self.lblWelcomeMessage.setText(QCoreApplication.translate("MainWindow", u"Welcome to Medical ERP", None))
        self.lblOrganizationName.setText(QCoreApplication.translate("MainWindow", u"Organization Name", None))
        self.lblBranchName.setText(QCoreApplication.translate("MainWindow", u"Branch Name", None))
        self.lblErpVersionInfo.setText(QCoreApplication.translate("MainWindow", u"ERP Version 2.0.0", None))
        self.lblTagline.setText(QCoreApplication.translate("MainWindow", u"Design Once, Build Forever", None))
        self.lblQuickInfoTitle.setText(QCoreApplication.translate("MainWindow", u"QUICK INFORMATION", None))
        self.lblDatabaseStatus.setText(QCoreApplication.translate("MainWindow", u"Database: Connected", None))
        self.lblLicenseStatus.setText(QCoreApplication.translate("MainWindow", u"License: Active", None))
        self.lblSubscriptionStatus.setText(QCoreApplication.translate("MainWindow", u"Subscription: -- Days Left", None))
        self.lblTodayDate.setText(QCoreApplication.translate("MainWindow", u"Today: --", None))
        self.lblCurrentFinancialYear.setText(QCoreApplication.translate("MainWindow", u"Financial Year: --", None))
        self.lblCopyright.setText(QCoreApplication.translate("MainWindow", u"\u00a9 Medical ERP", None))

        self.lblLoginIcon.setText("")
        self.lblLoginTitle.setText(QCoreApplication.translate("MainWindow", u"Sign in to your account", None))
        self.lblUsername.setText(QCoreApplication.translate("MainWindow", u"&Username", None))
        self.lblPassword.setText(QCoreApplication.translate("MainWindow", u"&Password", None))
        self.lblCompany.setText(QCoreApplication.translate("MainWindow", u"&Company", None))
        self.lblFinancialYear.setText(QCoreApplication.translate("MainWindow", u"Financial &Year", None))
        self.chkRememberMe.setText(QCoreApplication.translate("MainWindow", u"Remember Me", None))
        self.chkShowPassword.setText(QCoreApplication.translate("MainWindow", u"Show Password", None))
        self.lblCapsLock.setText("")
        self.lblConnectionStatus.setText("")
        self.lblLoginMessage.setText("")
        self.btnLogin.setText(QCoreApplication.translate("MainWindow", u"Login", None))
        self.btnExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
        self.btnForgotPassword.setText(QCoreApplication.translate("MainWindow", u"Forgot Password?", None))
        self.btnChangeLanguage.setText(QCoreApplication.translate("MainWindow", u"Language", None))
        self.btnTheme.setText(QCoreApplication.translate("MainWindow", u"Theme", None))

        self.lblFooterVersion.setText(QCoreApplication.translate("MainWindow", u"Version 2.0.0", None))
        self.lblFooterBuild.setText(QCoreApplication.translate("MainWindow", u"Build 1", None))
        self.lblFooterDbVersion.setText(QCoreApplication.translate("MainWindow", u"DB v1", None))
        self.lblFooterServer.setText(QCoreApplication.translate("MainWindow", u"Server: localhost", None))
        self.lblFooterDeveloper.setText(QCoreApplication.translate("MainWindow", u"Developer", None))
        self.lblFooterSupport.setText(QCoreApplication.translate("MainWindow", u"support@example.com", None))
        self.lblFooterWebsite.setText(QCoreApplication.translate("MainWindow", u"www.example.com", None))
        self.lblFooterCopyright.setText(QCoreApplication.translate("MainWindow", u"\u00a9 Medical ERP", None))
    # retranslateUi
