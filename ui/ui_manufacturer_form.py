# -*- coding: utf-8 -*-
"""
ui/ui_manufacturer_form.py

Generated-style form module for ui/manufacturer_form.ui.

NOTE (same honest limitation documented in ui/ui_supplier_form.py):
pyside6-uic is not runnable in the environment this file was authored in,
so it was hand-written to match the exact structure and object names
pyside6-uic would produce. Before shipping, regenerate for real with:

    pyside6-uic ui/manufacturer_form.ui -o ui/ui_manufacturer_form.py

Regenerating will not break screens/manufacturer_form_screen.py -- every
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
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)


class Ui_ManufacturerFormDialog(object):
    def setupUi(self, ManufacturerFormDialog):
        ManufacturerFormDialog.setObjectName("ManufacturerFormDialog")
        ManufacturerFormDialog.resize(480, 360)
        ManufacturerFormDialog.setWindowTitle("Manufacturer")
        ManufacturerFormDialog.setModal(True)

        self.verticalLayoutRoot = QVBoxLayout(ManufacturerFormDialog)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)

        self.lblFormTitle = QLabel(ManufacturerFormDialog)
        self.lblFormTitle.setObjectName("lblFormTitle")
        font = self.lblFormTitle.font()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)
        self.lblFormTitle.setText("Manufacturer Details")
        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        # ---------------- Basic Information ----------------
        self.grpBasicInfo = QGroupBox(ManufacturerFormDialog)
        self.grpBasicInfo.setObjectName("grpBasicInfo")
        self.grpBasicInfo.setTitle("Basic Information")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName("formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblManufacturerCode = QLabel("Manufacturer Code:", self.grpBasicInfo)
        self.txtManufacturerCode = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerCode.setObjectName("txtManufacturerCode")
        self.txtManufacturerCode.setToolTip("Leave blank to auto-generate (e.g. MFG-0001)")
        self.txtManufacturerCode.setPlaceholderText("Auto-generated if left blank")
        self.lblManufacturerCode.setBuddy(self.txtManufacturerCode)
        self.formLayoutBasic.addRow(self.lblManufacturerCode, self.txtManufacturerCode)

        self.lblManufacturerName = QLabel("Manufacturer Name: *", self.grpBasicInfo)
        self.txtManufacturerName = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerName.setObjectName("txtManufacturerName")
        self.txtManufacturerName.setToolTip("Mandatory. Must be unique.")
        self.txtManufacturerName.setMaxLength(150)
        self.lblManufacturerName.setBuddy(self.txtManufacturerName)
        self.formLayoutBasic.addRow(self.lblManufacturerName, self.txtManufacturerName)

        self.lblManufacturerShortName = QLabel("Short Name:", self.grpBasicInfo)
        self.txtManufacturerShortName = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerShortName.setObjectName("txtManufacturerShortName")
        self.txtManufacturerShortName.setReadOnly(True)
        self.txtManufacturerShortName.setToolTip(
            "Auto-generated from the first word of the Manufacturer Name. Not editable."
        )
        self.formLayoutBasic.addRow(self.lblManufacturerShortName, self.txtManufacturerShortName)

        self.lblCountry = QLabel("Country:", self.grpBasicInfo)
        self.txtCountry = QLineEdit(self.grpBasicInfo)
        self.txtCountry.setObjectName("txtCountry")
        self.txtCountry.setMaxLength(100)
        self.lblCountry.setBuddy(self.txtCountry)
        self.formLayoutBasic.addRow(self.lblCountry, self.txtCountry)

        self.verticalLayoutRoot.addWidget(self.grpBasicInfo)

        # ---------------- Status ----------------
        self.grpStatus = QGroupBox(ManufacturerFormDialog)
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

        self.verticalLayoutRoot.addWidget(self.grpStatus)

        self.lblValidationMessage = QLabel(ManufacturerFormDialog)
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

        self.btnSave = QPushButton(ManufacturerFormDialog)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setText("Save")
        self.btnSave.setToolTip("Save this manufacturer (Ctrl+S)")
        self.btnSave.setDefault(True)
        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnUpdate = QPushButton(ManufacturerFormDialog)
        self.btnUpdate.setObjectName("btnUpdate")
        self.btnUpdate.setText("Update")
        self.btnUpdate.setToolTip("Save changes to this manufacturer")
        self.btnUpdate.setVisible(False)
        self.horizontalLayoutFormButtons.addWidget(self.btnUpdate)

        self.btnClear = QPushButton(ManufacturerFormDialog)
        self.btnClear.setObjectName("btnClear")
        self.btnClear.setText("Clear")
        self.btnClear.setToolTip("Clear the form")
        self.horizontalLayoutFormButtons.addWidget(self.btnClear)

        self.btnClose = QPushButton(ManufacturerFormDialog)
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setText("Close")
        self.btnClose.setToolTip("Discard and close (Esc)")
        self.horizontalLayoutFormButtons.addWidget(self.btnClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)

        ManufacturerFormDialog.setTabOrder(self.txtManufacturerCode, self.txtManufacturerName)
        ManufacturerFormDialog.setTabOrder(self.txtManufacturerName, self.txtCountry)
        ManufacturerFormDialog.setTabOrder(self.txtCountry, self.cmbStatus)
        ManufacturerFormDialog.setTabOrder(self.cmbStatus, self.btnSave)
        ManufacturerFormDialog.setTabOrder(self.btnSave, self.btnClear)
        ManufacturerFormDialog.setTabOrder(self.btnClear, self.btnClose)
