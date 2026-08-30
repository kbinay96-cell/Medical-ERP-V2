# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'company_form.ui'
## WARNING! All changes made in this file will be lost when recompiling.
## Regenerate with: pyside6-uic ui/company_form.ui -o ui/ui_company_form.py
################################################################################

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget
)


class Ui_CompanyFormDialog(object):
    def setupUi(self, CompanyFormDialog):
        if not CompanyFormDialog.objectName():
            CompanyFormDialog.setObjectName(u"CompanyFormDialog")
        CompanyFormDialog.resize(560, 560)

        self.verticalLayout_root = QVBoxLayout(CompanyFormDialog)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")

        self.lblFormTitle = QLabel(CompanyFormDialog)
        self.lblFormTitle.setObjectName(u"lblFormTitle")
        self.lblFormTitle.setStyleSheet(u"font-size: 16px; font-weight: 600;")
        self.verticalLayout_root.addWidget(self.lblFormTitle)

        self.lineTopSep = QFrame(CompanyFormDialog)
        self.lineTopSep.setObjectName(u"lineTopSep")
        self.lineTopSep.setFrameShape(QFrame.HLine)
        self.verticalLayout_root.addWidget(self.lineTopSep)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")

        self.lblCompanyCode = QLabel(CompanyFormDialog)
        self.lblCompanyCode.setObjectName(u"lblCompanyCode")
        self.txtCompanyCode = QLineEdit(CompanyFormDialog)
        self.txtCompanyCode.setObjectName(u"txtCompanyCode")
        self.txtCompanyCode.setReadOnly(True)
        self.txtCompanyCode.setPlaceholderText(u"(auto-generated)")
        self.formLayout.addRow(self.lblCompanyCode, self.txtCompanyCode)

        self.lblCompanyName = QLabel(CompanyFormDialog)
        self.lblCompanyName.setObjectName(u"lblCompanyName")
        self.txtCompanyName = QLineEdit(CompanyFormDialog)
        self.txtCompanyName.setObjectName(u"txtCompanyName")
        self.formLayout.addRow(self.lblCompanyName, self.txtCompanyName)

        self.lblAddress = QLabel(CompanyFormDialog)
        self.lblAddress.setObjectName(u"lblAddress")
        self.txtAddress = QLineEdit(CompanyFormDialog)
        self.txtAddress.setObjectName(u"txtAddress")
        self.formLayout.addRow(self.lblAddress, self.txtAddress)

        self.lblContactPerson = QLabel(CompanyFormDialog)
        self.lblContactPerson.setObjectName(u"lblContactPerson")
        self.txtContactPerson = QLineEdit(CompanyFormDialog)
        self.txtContactPerson.setObjectName(u"txtContactPerson")
        self.formLayout.addRow(self.lblContactPerson, self.txtContactPerson)

        self.lblMobileNo = QLabel(CompanyFormDialog)
        self.lblMobileNo.setObjectName(u"lblMobileNo")
        self.txtMobileNo = QLineEdit(CompanyFormDialog)
        self.txtMobileNo.setObjectName(u"txtMobileNo")
        self.formLayout.addRow(self.lblMobileNo, self.txtMobileNo)

        self.lblPhoneNo = QLabel(CompanyFormDialog)
        self.lblPhoneNo.setObjectName(u"lblPhoneNo")
        self.txtPhoneNo = QLineEdit(CompanyFormDialog)
        self.txtPhoneNo.setObjectName(u"txtPhoneNo")
        self.formLayout.addRow(self.lblPhoneNo, self.txtPhoneNo)

        self.lblEmail = QLabel(CompanyFormDialog)
        self.lblEmail.setObjectName(u"lblEmail")
        self.txtEmail = QLineEdit(CompanyFormDialog)
        self.txtEmail.setObjectName(u"txtEmail")
        self.formLayout.addRow(self.lblEmail, self.txtEmail)

        self.lblPanVatNo = QLabel(CompanyFormDialog)
        self.lblPanVatNo.setObjectName(u"lblPanVatNo")
        self.txtPanVatNo = QLineEdit(CompanyFormDialog)
        self.txtPanVatNo.setObjectName(u"txtPanVatNo")
        self.formLayout.addRow(self.lblPanVatNo, self.txtPanVatNo)

        self.lblRegistrationNo = QLabel(CompanyFormDialog)
        self.lblRegistrationNo.setObjectName(u"lblRegistrationNo")
        self.txtRegistrationNo = QLineEdit(CompanyFormDialog)
        self.txtRegistrationNo.setObjectName(u"txtRegistrationNo")
        self.formLayout.addRow(self.lblRegistrationNo, self.txtRegistrationNo)

        self.lblDdaNo = QLabel(CompanyFormDialog)
        self.lblDdaNo.setObjectName(u"lblDdaNo")
        self.txtDdaNo = QLineEdit(CompanyFormDialog)
        self.txtDdaNo.setObjectName(u"txtDdaNo")
        self.formLayout.addRow(self.lblDdaNo, self.txtDdaNo)

        self.lblLogo = QLabel(CompanyFormDialog)
        self.lblLogo.setObjectName(u"lblLogo")
        self.logoRowWidget = QWidget(CompanyFormDialog)
        self.logoRowWidget.setObjectName(u"logoRowWidget")
        self.logoRowLayout = QHBoxLayout(self.logoRowWidget)
        self.logoRowLayout.setObjectName(u"logoRowLayout")
        self.logoRowLayout.setContentsMargins(0, 0, 0, 0)
        self.txtLogoPath = QLineEdit(self.logoRowWidget)
        self.txtLogoPath.setObjectName(u"txtLogoPath")
        self.txtLogoPath.setReadOnly(True)
        self.logoRowLayout.addWidget(self.txtLogoPath)
        self.btnBrowseLogo = QPushButton(self.logoRowWidget)
        self.btnBrowseLogo.setObjectName(u"btnBrowseLogo")
        self.logoRowLayout.addWidget(self.btnBrowseLogo)
        self.formLayout.addRow(self.lblLogo, self.logoRowWidget)

        self.lblStatus = QLabel(CompanyFormDialog)
        self.lblStatus.setObjectName(u"lblStatus")
        self.cmbStatus = QComboBox(CompanyFormDialog)
        self.cmbStatus.addItem("")
        self.cmbStatus.addItem("")
        self.cmbStatus.setObjectName(u"cmbStatus")
        self.formLayout.addRow(self.lblStatus, self.cmbStatus)

        self.lblRemarks = QLabel(CompanyFormDialog)
        self.lblRemarks.setObjectName(u"lblRemarks")
        self.txtRemarks = QPlainTextEdit(CompanyFormDialog)
        self.txtRemarks.setObjectName(u"txtRemarks")
        self.txtRemarks.setMaximumHeight(60)
        self.formLayout.addRow(self.lblRemarks, self.txtRemarks)

        self.lblSmtpSectionTitle = QLabel(CompanyFormDialog)
        self.lblSmtpSectionTitle.setObjectName(u"lblSmtpSectionTitle")
        self.lblSmtpSectionTitle.setStyleSheet(u"font-weight: 600; margin-top: 8px;")
        self.formLayout.addRow(self.lblSmtpSectionTitle)

        self.lblSmtpHost = QLabel(CompanyFormDialog)
        self.lblSmtpHost.setObjectName(u"lblSmtpHost")
        self.txtSmtpHost = QLineEdit(CompanyFormDialog)
        self.txtSmtpHost.setObjectName(u"txtSmtpHost")
        self.txtSmtpHost.setPlaceholderText(u"e.g. smtp.gmail.com")
        self.formLayout.addRow(self.lblSmtpHost, self.txtSmtpHost)

        self.lblSmtpPort = QLabel(CompanyFormDialog)
        self.lblSmtpPort.setObjectName(u"lblSmtpPort")
        self.txtSmtpPort = QLineEdit(CompanyFormDialog)
        self.txtSmtpPort.setObjectName(u"txtSmtpPort")
        self.txtSmtpPort.setPlaceholderText(u"587")
        self.formLayout.addRow(self.lblSmtpPort, self.txtSmtpPort)

        self.lblSmtpEmail = QLabel(CompanyFormDialog)
        self.lblSmtpEmail.setObjectName(u"lblSmtpEmail")
        self.txtSmtpEmail = QLineEdit(CompanyFormDialog)
        self.txtSmtpEmail.setObjectName(u"txtSmtpEmail")
        self.txtSmtpEmail.setPlaceholderText(u"sender@example.com")
        self.formLayout.addRow(self.lblSmtpEmail, self.txtSmtpEmail)

        self.lblSmtpAppPassword = QLabel(CompanyFormDialog)
        self.lblSmtpAppPassword.setObjectName(u"lblSmtpAppPassword")
        self.txtSmtpAppPassword = QLineEdit(CompanyFormDialog)
        self.txtSmtpAppPassword.setObjectName(u"txtSmtpAppPassword")
        self.txtSmtpAppPassword.setEchoMode(QLineEdit.Password)
        self.formLayout.addRow(self.lblSmtpAppPassword, self.txtSmtpAppPassword)

        self.verticalLayout_root.addLayout(self.formLayout)

        self.lblValidationMessage = QLabel(CompanyFormDialog)
        self.lblValidationMessage.setObjectName(u"lblValidationMessage")
        self.lblValidationMessage.setStyleSheet(u"color: #C0392B;")
        self.lblValidationMessage.setWordWrap(True)
        self.verticalLayout_root.addWidget(self.lblValidationMessage)

        self.lineBottomSep = QFrame(CompanyFormDialog)
        self.lineBottomSep.setObjectName(u"lineBottomSep")
        self.lineBottomSep.setFrameShape(QFrame.HLine)
        self.verticalLayout_root.addWidget(self.lineBottomSep)

        self.frameButtons = QFrame(CompanyFormDialog)
        self.frameButtons.setObjectName(u"frameButtons")
        self.horizontalLayout_buttons = QHBoxLayout(self.frameButtons)
        self.horizontalLayout_buttons.setObjectName(u"horizontalLayout_buttons")

        self.horizontalSpacer_buttons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_buttons.addItem(self.horizontalSpacer_buttons)

        self.btnCancel = QPushButton(self.frameButtons)
        self.btnCancel.setObjectName(u"btnCancel")
        self.horizontalLayout_buttons.addWidget(self.btnCancel)

        self.btnSave = QPushButton(self.frameButtons)
        self.btnSave.setObjectName(u"btnSave")
        self.horizontalLayout_buttons.addWidget(self.btnSave)

        self.verticalLayout_root.addWidget(self.frameButtons)

        self.retranslateUi(CompanyFormDialog)

    def retranslateUi(self, CompanyFormDialog):
        CompanyFormDialog.setWindowTitle(QCoreApplication.translate("CompanyFormDialog", u"Company", None))
        self.lblFormTitle.setText(QCoreApplication.translate("CompanyFormDialog", u"Add Company", None))
        self.lblCompanyCode.setText(QCoreApplication.translate("CompanyFormDialog", u"Company ID", None))
        self.lblCompanyName.setText(QCoreApplication.translate("CompanyFormDialog", u"Company Name*", None))
        self.lblAddress.setText(QCoreApplication.translate("CompanyFormDialog", u"Address", None))
        self.lblContactPerson.setText(QCoreApplication.translate("CompanyFormDialog", u"Contact Person", None))
        self.lblMobileNo.setText(QCoreApplication.translate("CompanyFormDialog", u"Mobile No.", None))
        self.lblPhoneNo.setText(QCoreApplication.translate("CompanyFormDialog", u"Phone No.", None))
        self.lblEmail.setText(QCoreApplication.translate("CompanyFormDialog", u"Email", None))
        self.lblPanVatNo.setText(QCoreApplication.translate("CompanyFormDialog", u"PAN/VAT No.", None))
        self.lblRegistrationNo.setText(QCoreApplication.translate("CompanyFormDialog", u"Registration No.", None))
        self.lblDdaNo.setText(QCoreApplication.translate("CompanyFormDialog", u"DDA/Drug License No.", None))
        self.lblLogo.setText(QCoreApplication.translate("CompanyFormDialog", u"Logo", None))
        self.btnBrowseLogo.setText(QCoreApplication.translate("CompanyFormDialog", u"Browse...", None))
        self.lblStatus.setText(QCoreApplication.translate("CompanyFormDialog", u"Status", None))
        self.cmbStatus.setItemText(0, QCoreApplication.translate("CompanyFormDialog", u"Active", None))
        self.cmbStatus.setItemText(1, QCoreApplication.translate("CompanyFormDialog", u"Inactive", None))
        self.lblRemarks.setText(QCoreApplication.translate("CompanyFormDialog", u"Remarks", None))
        self.lblSmtpSectionTitle.setText(QCoreApplication.translate("CompanyFormDialog", u"Email Settings (SMTP) \u2014 used to send invoices", None))
        self.lblSmtpHost.setText(QCoreApplication.translate("CompanyFormDialog", u"SMTP Host", None))
        self.lblSmtpPort.setText(QCoreApplication.translate("CompanyFormDialog", u"SMTP Port", None))
        self.lblSmtpEmail.setText(QCoreApplication.translate("CompanyFormDialog", u"Sender Email", None))
        self.lblSmtpAppPassword.setText(QCoreApplication.translate("CompanyFormDialog", u"App Password", None))
        self.btnCancel.setText(QCoreApplication.translate("CompanyFormDialog", u"Cancel", None))
        self.btnSave.setText(QCoreApplication.translate("CompanyFormDialog", u"Save", None))
