# -*- coding: utf-8 -*-
"""
ui/ui_supplier_form.py

Generated-style form module for ui/supplier_form.ui.

NOTE (honest limitation, same as the Login/Dashboard module): Qt Designer /
pyside6-uic is not runnable in the environment this file was authored in, so
this file was hand-written to match the exact structure and object names
pyside6-uic would produce from supplier_form.ui. Before shipping, regenerate
it for real with:

    pyside6-uic ui/supplier_form.ui -o ui/ui_supplier_form.py

Regenerating will not break screens/supplier_form_screen.py -- every widget
name below matches the .ui file exactly, which is the only contract the
Screen layer relies on.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)


class Ui_SupplierFormDialog(object):
    def setupUi(self, SupplierFormDialog):
        SupplierFormDialog.setObjectName("SupplierFormDialog")
        SupplierFormDialog.resize(560, 640)
        SupplierFormDialog.setWindowTitle("Supplier")
        SupplierFormDialog.setModal(True)

        self.verticalLayoutRoot = QVBoxLayout(SupplierFormDialog)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)

        self.lblFormTitle = QLabel(SupplierFormDialog)
        self.lblFormTitle.setObjectName("lblFormTitle")
        font = self.lblFormTitle.font()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)
        self.lblFormTitle.setText("Supplier Details")
        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        # ---------------- Basic Information ----------------
        self.grpBasicInfo = QGroupBox(SupplierFormDialog)
        self.grpBasicInfo.setObjectName("grpBasicInfo")
        self.grpBasicInfo.setTitle("Basic Information")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName("formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblSupplierCode = QLabel("Supplier Code:", self.grpBasicInfo)
        self.txtSupplierCode = QLineEdit(self.grpBasicInfo)
        self.txtSupplierCode.setObjectName("txtSupplierCode")
        self.txtSupplierCode.setToolTip("Leave blank to auto-generate (e.g. SUP-0001)")
        self.txtSupplierCode.setPlaceholderText("Auto-generated if left blank")
        self.lblSupplierCode.setBuddy(self.txtSupplierCode)
        self.formLayoutBasic.addRow(self.lblSupplierCode, self.txtSupplierCode)

        self.lblSupplierName = QLabel("Supplier Name: *", self.grpBasicInfo)
        self.txtSupplierName = QLineEdit(self.grpBasicInfo)
        self.txtSupplierName.setObjectName("txtSupplierName")
        self.txtSupplierName.setToolTip("Mandatory. Must be unique.")
        self.txtSupplierName.setMaxLength(150)
        self.lblSupplierName.setBuddy(self.txtSupplierName)
        self.formLayoutBasic.addRow(self.lblSupplierName, self.txtSupplierName)

        self.lblContactPerson = QLabel("Contact Person:", self.grpBasicInfo)
        self.txtContactPerson = QLineEdit(self.grpBasicInfo)
        self.txtContactPerson.setObjectName("txtContactPerson")
        self.txtContactPerson.setMaxLength(100)
        self.lblContactPerson.setBuddy(self.txtContactPerson)
        self.formLayoutBasic.addRow(self.lblContactPerson, self.txtContactPerson)

        self.lblMobileNo = QLabel("Mobile No.:", self.grpBasicInfo)
        self.txtMobileNo = QLineEdit(self.grpBasicInfo)
        self.txtMobileNo.setObjectName("txtMobileNo")
        self.txtMobileNo.setMaxLength(20)
        self.lblMobileNo.setBuddy(self.txtMobileNo)
        self.formLayoutBasic.addRow(self.lblMobileNo, self.txtMobileNo)

        self.lblPhoneNo = QLabel("Phone No.:", self.grpBasicInfo)
        self.txtPhoneNo = QLineEdit(self.grpBasicInfo)
        self.txtPhoneNo.setObjectName("txtPhoneNo")
        self.txtPhoneNo.setMaxLength(20)
        self.lblPhoneNo.setBuddy(self.txtPhoneNo)
        self.formLayoutBasic.addRow(self.lblPhoneNo, self.txtPhoneNo)

        self.lblEmail = QLabel("Email:", self.grpBasicInfo)
        self.txtEmail = QLineEdit(self.grpBasicInfo)
        self.txtEmail.setObjectName("txtEmail")
        self.txtEmail.setMaxLength(150)
        self.lblEmail.setBuddy(self.txtEmail)
        self.formLayoutBasic.addRow(self.lblEmail, self.txtEmail)

        self.lblAddress = QLabel("Address:", self.grpBasicInfo)
        self.txtAddress = QLineEdit(self.grpBasicInfo)
        self.txtAddress.setObjectName("txtAddress")
        self.txtAddress.setMaxLength(255)
        self.lblAddress.setBuddy(self.txtAddress)
        self.formLayoutBasic.addRow(self.lblAddress, self.txtAddress)

        self.lblCity = QLabel("City:", self.grpBasicInfo)
        self.txtCity = QLineEdit(self.grpBasicInfo)
        self.txtCity.setObjectName("txtCity")
        self.txtCity.setMaxLength(100)
        self.lblCity.setBuddy(self.txtCity)
        self.formLayoutBasic.addRow(self.lblCity, self.txtCity)

        self.lblPanVatNo = QLabel("PAN / VAT No.:", self.grpBasicInfo)
        self.txtPanVatNo = QLineEdit(self.grpBasicInfo)
        self.txtPanVatNo.setObjectName("txtPanVatNo")
        self.txtPanVatNo.setMaxLength(30)
        self.lblPanVatNo.setBuddy(self.txtPanVatNo)
        self.formLayoutBasic.addRow(self.lblPanVatNo, self.txtPanVatNo)

        self.verticalLayoutRoot.addWidget(self.grpBasicInfo)

        # ---------------- Financial Information ----------------
        self.grpFinancial = QGroupBox(SupplierFormDialog)
        self.grpFinancial.setObjectName("grpFinancial")
        self.grpFinancial.setTitle("Financial Information")
        self.formLayoutFinancial = QFormLayout(self.grpFinancial)
        self.formLayoutFinancial.setObjectName("formLayoutFinancial")
        self.formLayoutFinancial.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblOpeningBalance = QLabel("Opening Balance:", self.grpFinancial)
        self.txtOpeningBalance = QLineEdit(self.grpFinancial)
        self.txtOpeningBalance.setObjectName("txtOpeningBalance")
        self.txtOpeningBalance.setToolTip("Must be zero or positive. Default 0.")
        self.txtOpeningBalance.setText("0.00")
        self.lblOpeningBalance.setBuddy(self.txtOpeningBalance)
        self.formLayoutFinancial.addRow(self.lblOpeningBalance, self.txtOpeningBalance)

        self.lblBalanceType = QLabel("Balance Type:", self.grpFinancial)
        self.cmbBalanceType = QComboBox(self.grpFinancial)
        self.cmbBalanceType.setObjectName("cmbBalanceType")
        self.cmbBalanceType.addItems(["Dr", "Cr"])
        self.lblBalanceType.setBuddy(self.cmbBalanceType)
        self.formLayoutFinancial.addRow(self.lblBalanceType, self.cmbBalanceType)

        self.lblCreditLimit = QLabel("Credit Limit:", self.grpFinancial)
        self.txtCreditLimit = QLineEdit(self.grpFinancial)
        self.txtCreditLimit.setObjectName("txtCreditLimit")
        self.txtCreditLimit.setText("0.00")
        self.lblCreditLimit.setBuddy(self.txtCreditLimit)
        self.formLayoutFinancial.addRow(self.lblCreditLimit, self.txtCreditLimit)

        self.lblCreditDays = QLabel("Credit Days:", self.grpFinancial)
        self.txtCreditDays = QLineEdit(self.grpFinancial)
        self.txtCreditDays.setObjectName("txtCreditDays")
        self.txtCreditDays.setText("0")
        self.lblCreditDays.setBuddy(self.txtCreditDays)
        self.formLayoutFinancial.addRow(self.lblCreditDays, self.txtCreditDays)

        self.verticalLayoutRoot.addWidget(self.grpFinancial)

        # ---------------- Status ----------------
        self.grpStatus = QGroupBox(SupplierFormDialog)
        self.grpStatus.setObjectName("grpStatus")
        self.grpStatus.setTitle("Status")
        self.formLayoutStatus = QFormLayout(self.grpStatus)
        self.formLayoutStatus.setObjectName("formLayoutStatus")
        self.formLayoutStatus.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblStatus = QLabel("Status:", self.grpStatus)
        self.cmbStatus = QComboBox(self.grpStatus)
        self.cmbStatus.setObjectName("cmbStatus")
        self.cmbStatus.addItems(["Active", "Inactive"])
        self.lblStatus.setBuddy(self.cmbStatus)
        self.formLayoutStatus.addRow(self.lblStatus, self.cmbStatus)

        self.lblRemarks = QLabel("Remarks:", self.grpStatus)
        self.txtRemarks = QPlainTextEdit(self.grpStatus)
        self.txtRemarks.setObjectName("txtRemarks")
        self.txtRemarks.setMaximumHeight(70)
        self.lblRemarks.setBuddy(self.txtRemarks)
        self.formLayoutStatus.addRow(self.lblRemarks, self.txtRemarks)

        self.verticalLayoutRoot.addWidget(self.grpStatus)

        self.lblValidationMessage = QLabel(SupplierFormDialog)
        self.lblValidationMessage.setObjectName("lblValidationMessage")
        self.lblValidationMessage.setText("")
        self.lblValidationMessage.setStyleSheet("color: #c0392b;")
        self.lblValidationMessage.setWordWrap(True)
        self.verticalLayoutRoot.addWidget(self.lblValidationMessage)

        self.horizontalLayoutFormButtons = QHBoxLayout()
        self.horizontalLayoutFormButtons.setObjectName("horizontalLayoutFormButtons")
        self.horizontalSpacerFormButtons = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        self.horizontalLayoutFormButtons.addItem(self.horizontalSpacerFormButtons)

        self.btnSave = QPushButton(SupplierFormDialog)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setText("Save")
        self.btnSave.setToolTip("Save this supplier (Ctrl+S)")
        self.btnSave.setDefault(True)
        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnCancel = QPushButton(SupplierFormDialog)
        self.btnCancel.setObjectName("btnCancel")
        self.btnCancel.setText("Cancel")
        self.btnCancel.setToolTip("Discard changes (Esc)")
        self.horizontalLayoutFormButtons.addWidget(self.btnCancel)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)

        SupplierFormDialog.setTabOrder(self.txtSupplierCode, self.txtSupplierName)
        SupplierFormDialog.setTabOrder(self.txtSupplierName, self.txtContactPerson)
        SupplierFormDialog.setTabOrder(self.txtContactPerson, self.txtMobileNo)
        SupplierFormDialog.setTabOrder(self.txtMobileNo, self.txtPhoneNo)
        SupplierFormDialog.setTabOrder(self.txtPhoneNo, self.txtEmail)
        SupplierFormDialog.setTabOrder(self.txtEmail, self.txtAddress)
        SupplierFormDialog.setTabOrder(self.txtAddress, self.txtCity)
        SupplierFormDialog.setTabOrder(self.txtCity, self.txtPanVatNo)
        SupplierFormDialog.setTabOrder(self.txtPanVatNo, self.txtOpeningBalance)
        SupplierFormDialog.setTabOrder(self.txtOpeningBalance, self.cmbBalanceType)
        SupplierFormDialog.setTabOrder(self.cmbBalanceType, self.txtCreditLimit)
        SupplierFormDialog.setTabOrder(self.txtCreditLimit, self.txtCreditDays)
        SupplierFormDialog.setTabOrder(self.txtCreditDays, self.cmbStatus)
        SupplierFormDialog.setTabOrder(self.cmbStatus, self.txtRemarks)
        SupplierFormDialog.setTabOrder(self.txtRemarks, self.btnSave)
        SupplierFormDialog.setTabOrder(self.btnSave, self.btnCancel)
