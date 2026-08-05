# -*- coding: utf-8 -*-
"""
ui/ui_supplier_manufacturer_discount_form.py

Generated-style form module for ui/supplier_manufacturer_discount_form.ui.

NOTE (same honest limitation documented in ui/ui_manufacturer_form.py):
pyside6-uic is not runnable in the environment this file was authored in,
so it was hand-written to match the exact structure and object names
pyside6-uic would produce. Before shipping, regenerate for real with:

    pyside6-uic ui/supplier_manufacturer_discount_form.ui -o ui/ui_supplier_manufacturer_discount_form.py

Regenerating will not break screens/supplier_manufacturer_discount_form_screen.py
-- every widget name below matches the .ui file exactly, which is the only
contract the Screen layer relies on.
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


class Ui_SupplierManufacturerDiscountFormDialog(object):
    def setupUi(self, SupplierManufacturerDiscountFormDialog):
        SupplierManufacturerDiscountFormDialog.setObjectName("SupplierManufacturerDiscountFormDialog")
        SupplierManufacturerDiscountFormDialog.resize(480, 380)
        SupplierManufacturerDiscountFormDialog.setWindowTitle("Supplier-Manufacturer Discount")
        SupplierManufacturerDiscountFormDialog.setModal(True)

        self.verticalLayoutRoot = QVBoxLayout(SupplierManufacturerDiscountFormDialog)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)

        self.lblFormTitle = QLabel(SupplierManufacturerDiscountFormDialog)
        self.lblFormTitle.setObjectName("lblFormTitle")
        font = self.lblFormTitle.font()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)
        self.lblFormTitle.setText("Discount Mapping Details")
        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        # ---------------- Mapping ----------------
        self.grpBasicInfo = QGroupBox(SupplierManufacturerDiscountFormDialog)
        self.grpBasicInfo.setObjectName("grpBasicInfo")
        self.grpBasicInfo.setTitle("Mapping")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName("formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblSupplier = QLabel("Supplier: *", self.grpBasicInfo)
        self.cmbSupplier = QComboBox(self.grpBasicInfo)
        self.cmbSupplier.setObjectName("cmbSupplier")
        self.cmbSupplier.setToolTip("Start typing to search suppliers.")
        self.lblSupplier.setBuddy(self.cmbSupplier)
        self.formLayoutBasic.addRow(self.lblSupplier, self.cmbSupplier)

        self.lblManufacturer = QLabel("Manufacturer: *", self.grpBasicInfo)
        self.cmbManufacturer = QComboBox(self.grpBasicInfo)
        self.cmbManufacturer.setObjectName("cmbManufacturer")
        self.cmbManufacturer.setToolTip("Start typing to search manufacturers.")
        self.lblManufacturer.setBuddy(self.cmbManufacturer)
        self.formLayoutBasic.addRow(self.lblManufacturer, self.cmbManufacturer)

        self.lblDiscountPercent = QLabel("Discount %: *", self.grpBasicInfo)
        self.txtDiscountPercent = QLineEdit(self.grpBasicInfo)
        self.txtDiscountPercent.setObjectName("txtDiscountPercent")
        self.txtDiscountPercent.setToolTip("Value between 0 and 100.")
        self.txtDiscountPercent.setText("0.00")
        self.lblDiscountPercent.setBuddy(self.txtDiscountPercent)
        self.formLayoutBasic.addRow(self.lblDiscountPercent, self.txtDiscountPercent)

        self.verticalLayoutRoot.addWidget(self.grpBasicInfo)

        # ---------------- Remarks ----------------
        self.grpRemarks = QGroupBox(SupplierManufacturerDiscountFormDialog)
        self.grpRemarks.setObjectName("grpRemarks")
        self.grpRemarks.setTitle("Remarks")
        self.verticalLayoutRemarks = QVBoxLayout(self.grpRemarks)
        self.verticalLayoutRemarks.setObjectName("verticalLayoutRemarks")

        self.txtRemarks = QPlainTextEdit(self.grpRemarks)
        self.txtRemarks.setObjectName("txtRemarks")
        self.txtRemarks.setMaximumHeight(70)
        self.verticalLayoutRemarks.addWidget(self.txtRemarks)

        self.verticalLayoutRoot.addWidget(self.grpRemarks)

        self.lblValidationMessage = QLabel(SupplierManufacturerDiscountFormDialog)
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

        self.btnSave = QPushButton(SupplierManufacturerDiscountFormDialog)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setText("Save")
        self.btnSave.setToolTip("Save this mapping (Ctrl+S)")
        self.btnSave.setDefault(True)
        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnCancel = QPushButton(SupplierManufacturerDiscountFormDialog)
        self.btnCancel.setObjectName("btnCancel")
        self.btnCancel.setText("Cancel")
        self.btnCancel.setToolTip("Discard changes (Esc)")
        self.horizontalLayoutFormButtons.addWidget(self.btnCancel)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)

        SupplierManufacturerDiscountFormDialog.setTabOrder(self.cmbSupplier, self.cmbManufacturer)
        SupplierManufacturerDiscountFormDialog.setTabOrder(self.cmbManufacturer, self.txtDiscountPercent)
        SupplierManufacturerDiscountFormDialog.setTabOrder(self.txtDiscountPercent, self.txtRemarks)
        SupplierManufacturerDiscountFormDialog.setTabOrder(self.txtRemarks, self.btnSave)
        SupplierManufacturerDiscountFormDialog.setTabOrder(self.btnSave, self.btnCancel)
