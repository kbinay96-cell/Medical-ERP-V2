# -*- coding: utf-8 -*-
"""
ui/ui_country_tax_form.py

Generated-style form module for ui/country_tax_form.ui.

NOTE (same honest limitation documented in ui/ui_manufacturer_form.py):
pyside6-uic is not runnable in the environment this file was authored in,
so it was hand-written to match the exact structure and object names
pyside6-uic would produce. Before shipping, regenerate for real with:

    pyside6-uic ui/country_tax_form.ui -o ui/ui_country_tax_form.py

Regenerating will not break screens/country_tax_form_screen.py -- every
widget name below matches the .ui file exactly, which is the only contract
the Screen layer relies on.
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


class Ui_CountryTaxFormDialog(object):
    def setupUi(self, CountryTaxFormDialog):
        CountryTaxFormDialog.setObjectName("CountryTaxFormDialog")
        CountryTaxFormDialog.resize(460, 360)
        CountryTaxFormDialog.setWindowTitle("Country Tax")
        CountryTaxFormDialog.setModal(True)

        self.verticalLayoutRoot = QVBoxLayout(CountryTaxFormDialog)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)

        self.lblFormTitle = QLabel(CountryTaxFormDialog)
        self.lblFormTitle.setObjectName("lblFormTitle")
        font = self.lblFormTitle.font()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)
        self.lblFormTitle.setText("Country Tax Details")
        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        # ---------------- Tax Rates ----------------
        self.grpBasicInfo = QGroupBox(CountryTaxFormDialog)
        self.grpBasicInfo.setObjectName("grpBasicInfo")
        self.grpBasicInfo.setTitle("Tax Rates")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName("formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblCountry = QLabel("Country: *", self.grpBasicInfo)
        self.cmbCountry = QComboBox(self.grpBasicInfo)
        self.cmbCountry.setObjectName("cmbCountry")
        self.cmbCountry.setEditable(True)
        self.cmbCountry.setToolTip(
            "Mandatory. Populated from Manufacturer countries -- you can also "
            "type a new country not yet used by any Manufacturer. Must be unique."
        )
        self.lblCountry.setBuddy(self.cmbCountry)
        self.formLayoutBasic.addRow(self.lblCountry, self.cmbCountry)

        self.lblVatPercent = QLabel("VAT %:", self.grpBasicInfo)
        self.txtVatPercent = QLineEdit(self.grpBasicInfo)
        self.txtVatPercent.setObjectName("txtVatPercent")
        self.txtVatPercent.setText("0.00")
        self.lblVatPercent.setBuddy(self.txtVatPercent)
        self.formLayoutBasic.addRow(self.lblVatPercent, self.txtVatPercent)

        self.lblCustomPercent = QLabel("Custom %:", self.grpBasicInfo)
        self.txtCustomPercent = QLineEdit(self.grpBasicInfo)
        self.txtCustomPercent.setObjectName("txtCustomPercent")
        self.txtCustomPercent.setText("0.00")
        self.lblCustomPercent.setBuddy(self.txtCustomPercent)
        self.formLayoutBasic.addRow(self.lblCustomPercent, self.txtCustomPercent)

        self.verticalLayoutRoot.addWidget(self.grpBasicInfo)

        # ---------------- Status ----------------
        self.grpStatus = QGroupBox(CountryTaxFormDialog)
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

        self.lblValidationMessage = QLabel(CountryTaxFormDialog)
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

        self.btnSave = QPushButton(CountryTaxFormDialog)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setText("Save")
        self.btnSave.setToolTip("Save this country tax (Ctrl+S)")
        self.btnSave.setDefault(True)
        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnUpdate = QPushButton(CountryTaxFormDialog)
        self.btnUpdate.setObjectName("btnUpdate")
        self.btnUpdate.setText("Update")
        self.btnUpdate.setToolTip("Save changes to this country tax")
        self.btnUpdate.setVisible(False)
        self.horizontalLayoutFormButtons.addWidget(self.btnUpdate)

        self.btnClear = QPushButton(CountryTaxFormDialog)
        self.btnClear.setObjectName("btnClear")
        self.btnClear.setText("Clear")
        self.btnClear.setToolTip("Clear the form")
        self.horizontalLayoutFormButtons.addWidget(self.btnClear)

        self.btnClose = QPushButton(CountryTaxFormDialog)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setText("Close")
        self.btnClose.setToolTip("Discard and close (Esc)")
        self.horizontalLayoutFormButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)

        CountryTaxFormDialog.setTabOrder(self.cmbCountry, self.txtVatPercent)
        CountryTaxFormDialog.setTabOrder(self.txtVatPercent, self.txtCustomPercent)
        CountryTaxFormDialog.setTabOrder(self.txtCustomPercent, self.cmbStatus)
        CountryTaxFormDialog.setTabOrder(self.cmbStatus, self.txtRemarks)
        CountryTaxFormDialog.setTabOrder(self.txtRemarks, self.btnSave)
        CountryTaxFormDialog.setTabOrder(self.btnSave, self.btnClear)
        CountryTaxFormDialog.setTabOrder(self.btnClear, self.btnClose)
