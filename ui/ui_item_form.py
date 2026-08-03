# -*- coding: utf-8 -*-
"""
ui/ui_item_form.py

Generated-style form module for ui/item_form.ui.

NOTE (same honest limitation as ui_supplier_form.py): Qt Designer /
pyside6-uic is not runnable in the environment this file was authored in,
so this file was hand-written to match the exact structure and object
names pyside6-uic would produce from item_form.ui. Before shipping,
regenerate it for real with:

    pyside6-uic ui/item_form.ui -o ui/ui_item_form.py

Regenerating will not break screens/item_form_screen.py -- every widget
name below matches what the .ui file would produce, which is the only
contract the Screen layer relies on.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_ItemFormDialog(object):
    def setupUi(self, ItemFormDialog):
        ItemFormDialog.setObjectName("ItemFormDialog")
        ItemFormDialog.resize(680, 760)
        ItemFormDialog.setWindowTitle("Item")
        ItemFormDialog.setModal(True)

        self.verticalLayoutRoot = QVBoxLayout(ItemFormDialog)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)

        self.lblFormTitle = QLabel(ItemFormDialog)
        self.lblFormTitle.setObjectName("lblFormTitle")
        font = self.lblFormTitle.font()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)
        self.lblFormTitle.setText("Item Details")
        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        # ---------------- Scroll Area (wraps all form groups) ----------------
        self.scrollArea = QScrollArea(ItemFormDialog)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaContents = QWidget()
        self.scrollAreaContents.setObjectName("scrollAreaContents")
        self.verticalLayoutScroll = QVBoxLayout(self.scrollAreaContents)
        self.verticalLayoutScroll.setObjectName("verticalLayoutScroll")

        # ---------------- Basic Information ----------------
        self.grpBasicInfo = QGroupBox(self.scrollAreaContents)
        self.grpBasicInfo.setObjectName("grpBasicInfo")
        self.grpBasicInfo.setTitle("Basic Information")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName("formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblItemCode = QLabel("Item Code:", self.grpBasicInfo)
        self.txtItemCode = QLineEdit(self.grpBasicInfo)
        self.txtItemCode.setObjectName("txtItemCode")
        self.txtItemCode.setToolTip("Leave blank to auto-generate (e.g. ITM-0001)")
        self.txtItemCode.setPlaceholderText("Auto-generated if left blank")
        self.formLayoutBasic.addRow(self.lblItemCode, self.txtItemCode)

        self.lblItemName = QLabel("Item Name: *", self.grpBasicInfo)
        self.txtItemName = QLineEdit(self.grpBasicInfo)
        self.txtItemName.setObjectName("txtItemName")
        self.txtItemName.setMaxLength(200)
        self.formLayoutBasic.addRow(self.lblItemName, self.txtItemName)

        self.verticalLayoutScroll.addWidget(self.grpBasicInfo)

        # ---------------- Classification ----------------
        self.grpClassification = QGroupBox(self.scrollAreaContents)
        self.grpClassification.setObjectName("grpClassification")
        self.grpClassification.setTitle("Classification")
        self.formLayoutClassification = QFormLayout(self.grpClassification)
        self.formLayoutClassification.setObjectName("formLayoutClassification")
        self.formLayoutClassification.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblCategory = QLabel("Category:", self.grpClassification)
        self.cmbCategory = QComboBox(self.grpClassification)
        self.cmbCategory.setObjectName("cmbCategory")
        self.formLayoutClassification.addRow(self.lblCategory, self.cmbCategory)

        self.lblSubCategory = QLabel("Sub Category:", self.grpClassification)
        self.cmbSubCategory = QComboBox(self.grpClassification)
        self.cmbSubCategory.setObjectName("cmbSubCategory")
        self.formLayoutClassification.addRow(self.lblSubCategory, self.cmbSubCategory)

        self.lblItemGroup = QLabel("Item Type:", self.grpClassification)
        self.cmbItemGroup = QComboBox(self.grpClassification)
        self.cmbItemGroup.setObjectName("cmbItemGroup")
        self.formLayoutClassification.addRow(self.lblItemGroup, self.cmbItemGroup)

        self.lblManufacturer = QLabel("Manufacturer:", self.grpClassification)
        self.cmbManufacturer = QComboBox(self.grpClassification)
        self.cmbManufacturer.setObjectName("cmbManufacturer")
        self.formLayoutClassification.addRow(self.lblManufacturer, self.cmbManufacturer)

        self.lblGeneric = QLabel("Generic Name:", self.grpClassification)
        self.cmbGeneric = QComboBox(self.grpClassification)
        self.cmbGeneric.setObjectName("cmbGeneric")
        self.formLayoutClassification.addRow(self.lblGeneric, self.cmbGeneric)

        self.verticalLayoutScroll.addWidget(self.grpClassification)

        # ---------------- Units ----------------
        self.grpUnits = QGroupBox(self.scrollAreaContents)
        self.grpUnits.setObjectName("grpUnits")
        self.grpUnits.setTitle("Units")
        self.formLayoutUnits = QFormLayout(self.grpUnits)
        self.formLayoutUnits.setObjectName("formLayoutUnits")
        self.formLayoutUnits.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblUnit = QLabel("Unit: *", self.grpUnits)
        self.cmbUnit = QComboBox(self.grpUnits)
        self.cmbUnit.setObjectName("cmbUnit")
        self.formLayoutUnits.addRow(self.lblUnit, self.cmbUnit)

        self.lblPurchaseUnit = QLabel("Purchase Unit:", self.grpUnits)
        self.cmbPurchaseUnit = QComboBox(self.grpUnits)
        self.cmbPurchaseUnit.setObjectName("cmbPurchaseUnit")
        self.cmbPurchaseUnit.setToolTip("Leave same as Unit if this item is purchased and sold in the same unit.")
        self.formLayoutUnits.addRow(self.lblPurchaseUnit, self.cmbPurchaseUnit)

        self.verticalLayoutScroll.addWidget(self.grpUnits)

        # ---------------- Pricing ----------------
        self.grpPricing = QGroupBox(self.scrollAreaContents)
        self.grpPricing.setObjectName("grpPricing")
        self.grpPricing.setTitle("Pricing && Stock")
        self.formLayoutPricing = QFormLayout(self.grpPricing)
        self.formLayoutPricing.setObjectName("formLayoutPricing")
        self.formLayoutPricing.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblPurchaseRate = QLabel("Purchase Rate:", self.grpPricing)
        self.txtPurchaseRate = QLineEdit(self.grpPricing)
        self.txtPurchaseRate.setObjectName("txtPurchaseRate")
        self.txtPurchaseRate.setText("0.00")
        self.formLayoutPricing.addRow(self.lblPurchaseRate, self.txtPurchaseRate)

        self.lblSaleRate = QLabel("Sale Rate:", self.grpPricing)
        self.txtSaleRate = QLineEdit(self.grpPricing)
        self.txtSaleRate.setObjectName("txtSaleRate")
        self.txtSaleRate.setText("0.00")
        self.formLayoutPricing.addRow(self.lblSaleRate, self.txtSaleRate)

        self.lblMrp = QLabel("MRP:", self.grpPricing)
        self.txtMrp = QLineEdit(self.grpPricing)
        self.txtMrp.setObjectName("txtMrp")
        self.txtMrp.setText("0.00")
        self.formLayoutPricing.addRow(self.lblMrp, self.txtMrp)

        self.lblMinimumStock = QLabel("Minimum Stock:", self.grpPricing)
        self.txtMinimumStock = QLineEdit(self.grpPricing)
        self.txtMinimumStock.setObjectName("txtMinimumStock")
        self.txtMinimumStock.setText("0")
        self.txtMinimumStock.setToolTip("Reorder level -- can be changed anytime, no lock.")
        self.formLayoutPricing.addRow(self.lblMinimumStock, self.txtMinimumStock)

        self.lblCurrentStockDisplay = QLabel("Current Total Stock:", self.grpPricing)
        self.lblCurrentStockValue = QLabel("0", self.grpPricing)
        self.lblCurrentStockValue.setObjectName("lblCurrentStockValue")
        self.lblCurrentStockValue.setToolTip("Read-only -- sum of all batch quantities. Add stock via 'Add Batch'.")
        self.formLayoutPricing.addRow(self.lblCurrentStockDisplay, self.lblCurrentStockValue)

        self.btnAddBatch = QPushButton("Add Batch (Opening Stock)", self.grpPricing)
        self.btnAddBatch.setObjectName("btnAddBatch")
        self.btnAddBatch.setToolTip("Add a batch with quantity + expiry. An item can also be saved with zero stock.")
        self.formLayoutPricing.addRow(QLabel(""), self.btnAddBatch)

        self.verticalLayoutScroll.addWidget(self.grpPricing)

        # ---------------- Tax Mode ----------------
        self.grpTax = QGroupBox(self.scrollAreaContents)
        self.grpTax.setObjectName("grpTax")
        self.grpTax.setTitle("Tax")
        self.verticalLayoutTax = QVBoxLayout(self.grpTax)
        self.verticalLayoutTax.setObjectName("verticalLayoutTax")

        self.horizontalLayoutTaxMode = QHBoxLayout()
        self.horizontalLayoutTaxMode.setObjectName("horizontalLayoutTaxMode")
        self.radioCountryDefault = QRadioButton("Use Country Default", self.grpTax)
        self.radioCountryDefault.setObjectName("radioCountryDefault")
        self.radioCountryDefault.setChecked(True)
        self.radioIndividual = QRadioButton("Individual Tax", self.grpTax)
        self.radioIndividual.setObjectName("radioIndividual")
        self.horizontalLayoutTaxMode.addWidget(self.radioCountryDefault)
        self.horizontalLayoutTaxMode.addWidget(self.radioIndividual)
        self.horizontalLayoutTaxMode.addStretch(1)
        self.verticalLayoutTax.addLayout(self.horizontalLayoutTaxMode)

        self.lblCountryDefaultPreview = QLabel(
            "Effective VAT/Custom % will be resolved from the selected Manufacturer's Country.",
            self.grpTax,
        )
        self.lblCountryDefaultPreview.setObjectName("lblCountryDefaultPreview")
        self.lblCountryDefaultPreview.setWordWrap(True)
        self.lblCountryDefaultPreview.setStyleSheet("color: #666666;")
        self.verticalLayoutTax.addWidget(self.lblCountryDefaultPreview)

        self.frameIndividualTax = QFrame(self.grpTax)
        self.frameIndividualTax.setObjectName("frameIndividualTax")
        self.formLayoutIndividualTax = QFormLayout(self.frameIndividualTax)
        self.formLayoutIndividualTax.setObjectName("formLayoutIndividualTax")
        self.formLayoutIndividualTax.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.chkVat = QCheckBox("VAT %", self.frameIndividualTax)
        self.chkVat.setObjectName("chkVat")
        self.txtVatPercent = QLineEdit(self.frameIndividualTax)
        self.txtVatPercent.setObjectName("txtVatPercent")
        self.txtVatPercent.setEnabled(False)
        self.formLayoutIndividualTax.addRow(self.chkVat, self.txtVatPercent)

        self.chkCustom = QCheckBox("Custom %", self.frameIndividualTax)
        self.chkCustom.setObjectName("chkCustom")
        self.txtCustomPercent = QLineEdit(self.frameIndividualTax)
        self.txtCustomPercent.setObjectName("txtCustomPercent")
        self.txtCustomPercent.setEnabled(False)
        self.formLayoutIndividualTax.addRow(self.chkCustom, self.txtCustomPercent)

        self.frameIndividualTax.setVisible(False)
        self.verticalLayoutTax.addWidget(self.frameIndividualTax)

        self.verticalLayoutScroll.addWidget(self.grpTax)

        # ---------------- Status ----------------
        self.grpStatus = QGroupBox(self.scrollAreaContents)
        self.grpStatus.setObjectName("grpStatus")
        self.grpStatus.setTitle("Status")
        self.formLayoutStatus = QFormLayout(self.grpStatus)
        self.formLayoutStatus.setObjectName("formLayoutStatus")
        self.formLayoutStatus.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lblStatus = QLabel("Status:", self.grpStatus)
        self.cmbStatus = QComboBox(self.grpStatus)
        self.cmbStatus.setObjectName("cmbStatus")
        self.cmbStatus.addItems(["Active", "Inactive"])
        self.formLayoutStatus.addRow(self.lblStatus, self.cmbStatus)

        self.lblRemarks = QLabel("Remarks:", self.grpStatus)
        self.txtRemarks = QPlainTextEdit(self.grpStatus)
        self.txtRemarks.setObjectName("txtRemarks")
        self.txtRemarks.setMaximumHeight(70)
        self.formLayoutStatus.addRow(self.lblRemarks, self.txtRemarks)

        self.verticalLayoutScroll.addWidget(self.grpStatus)

        self.scrollArea.setWidget(self.scrollAreaContents)
        self.verticalLayoutRoot.addWidget(self.scrollArea)

        self.lblValidationMessage = QLabel(ItemFormDialog)
        self.lblValidationMessage.setObjectName("lblValidationMessage")
        self.lblValidationMessage.setStyleSheet("color: #c0392b;")
        self.lblValidationMessage.setWordWrap(True)
        self.verticalLayoutRoot.addWidget(self.lblValidationMessage)

        self.horizontalLayoutFormButtons = QHBoxLayout()
        self.horizontalLayoutFormButtons.setObjectName("horizontalLayoutFormButtons")
        self.horizontalSpacerFormButtons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayoutFormButtons.addItem(self.horizontalSpacerFormButtons)

        self.btnSave = QPushButton("Save", ItemFormDialog)
        self.btnSave.setObjectName("btnSave")
        self.btnSave.setToolTip("Save this item (Ctrl+S)")
        self.btnSave.setDefault(True)
        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnCancel = QPushButton("Cancel", ItemFormDialog)
        self.btnCancel.setObjectName("btnCancel")
        self.btnCancel.setToolTip("Discard changes (Esc)")
        self.horizontalLayoutFormButtons.addWidget(self.btnCancel)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)
