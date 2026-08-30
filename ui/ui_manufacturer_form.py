# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'manufacturer_form.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

class Ui_ManufacturerFormDialog(object):
    def setupUi(self, ManufacturerFormDialog):
        if not ManufacturerFormDialog.objectName():
            ManufacturerFormDialog.setObjectName(u"ManufacturerFormDialog")
        ManufacturerFormDialog.resize(480, 360)
        ManufacturerFormDialog.setModal(True)
        self.verticalLayoutRoot = QVBoxLayout(ManufacturerFormDialog)
        self.verticalLayoutRoot.setSpacing(10)
        self.verticalLayoutRoot.setObjectName(u"verticalLayoutRoot")
        self.verticalLayoutRoot.setContentsMargins(14, 14, 14, 14)
        self.lblFormTitle = QLabel(ManufacturerFormDialog)
        self.lblFormTitle.setObjectName(u"lblFormTitle")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.lblFormTitle.setFont(font)

        self.verticalLayoutRoot.addWidget(self.lblFormTitle)

        self.grpBasicInfo = QGroupBox(ManufacturerFormDialog)
        self.grpBasicInfo.setObjectName(u"grpBasicInfo")
        self.formLayoutBasic = QFormLayout(self.grpBasicInfo)
        self.formLayoutBasic.setObjectName(u"formLayoutBasic")
        self.formLayoutBasic.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.lblManufacturerCode = QLabel(self.grpBasicInfo)
        self.lblManufacturerCode.setObjectName(u"lblManufacturerCode")

        self.formLayoutBasic.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblManufacturerCode)

        self.txtManufacturerCode = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerCode.setObjectName(u"txtManufacturerCode")

        self.formLayoutBasic.setWidget(0, QFormLayout.ItemRole.FieldRole, self.txtManufacturerCode)

        self.lblManufacturerName = QLabel(self.grpBasicInfo)
        self.lblManufacturerName.setObjectName(u"lblManufacturerName")

        self.formLayoutBasic.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lblManufacturerName)

        self.txtManufacturerName = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerName.setObjectName(u"txtManufacturerName")
        self.txtManufacturerName.setMaxLength(150)

        self.formLayoutBasic.setWidget(1, QFormLayout.ItemRole.FieldRole, self.txtManufacturerName)

        self.lblManufacturerShortName = QLabel(self.grpBasicInfo)
        self.lblManufacturerShortName.setObjectName(u"lblManufacturerShortName")

        self.formLayoutBasic.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lblManufacturerShortName)

        self.txtManufacturerShortName = QLineEdit(self.grpBasicInfo)
        self.txtManufacturerShortName.setObjectName(u"txtManufacturerShortName")
        self.txtManufacturerShortName.setReadOnly(True)

        self.formLayoutBasic.setWidget(2, QFormLayout.ItemRole.FieldRole, self.txtManufacturerShortName)

        self.lblCountry = QLabel(self.grpBasicInfo)
        self.lblCountry.setObjectName(u"lblCountry")

        self.formLayoutBasic.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lblCountry)

        self.txtCountry = QLineEdit(self.grpBasicInfo)
        self.txtCountry.setObjectName(u"txtCountry")
        self.txtCountry.setMaxLength(100)

        self.formLayoutBasic.setWidget(3, QFormLayout.ItemRole.FieldRole, self.txtCountry)

        self.lblDefaultMarginPercent = QLabel(self.grpBasicInfo)
        self.lblDefaultMarginPercent.setObjectName(u"lblDefaultMarginPercent")

        self.formLayoutBasic.setWidget(4, QFormLayout.ItemRole.LabelRole, self.lblDefaultMarginPercent)

        self.txtDefaultMarginPercent = QLineEdit(self.grpBasicInfo)
        self.txtDefaultMarginPercent.setObjectName(u"txtDefaultMarginPercent")

        self.formLayoutBasic.setWidget(4, QFormLayout.ItemRole.FieldRole, self.txtDefaultMarginPercent)


        self.verticalLayoutRoot.addWidget(self.grpBasicInfo)

        self.grpStatus = QGroupBox(ManufacturerFormDialog)
        self.grpStatus.setObjectName(u"grpStatus")
        self.formLayoutStatus = QFormLayout(self.grpStatus)
        self.formLayoutStatus.setObjectName(u"formLayoutStatus")
        self.formLayoutStatus.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.lblStatus = QLabel(self.grpStatus)
        self.lblStatus.setObjectName(u"lblStatus")

        self.formLayoutStatus.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lblStatus)

        self.cmbStatus = QComboBox(self.grpStatus)
        self.cmbStatus.addItem("")
        self.cmbStatus.addItem("")
        self.cmbStatus.setObjectName(u"cmbStatus")

        self.formLayoutStatus.setWidget(0, QFormLayout.ItemRole.FieldRole, self.cmbStatus)


        self.verticalLayoutRoot.addWidget(self.grpStatus)

        self.lblValidationMessage = QLabel(ManufacturerFormDialog)
        self.lblValidationMessage.setObjectName(u"lblValidationMessage")
        self.lblValidationMessage.setStyleSheet(u"color: #c0392b;")
        self.lblValidationMessage.setWordWrap(True)

        self.verticalLayoutRoot.addWidget(self.lblValidationMessage)

        self.horizontalLayoutFormButtons = QHBoxLayout()
        self.horizontalLayoutFormButtons.setObjectName(u"horizontalLayoutFormButtons")
        self.horizontalSpacerFormButtons = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayoutFormButtons.addItem(self.horizontalSpacerFormButtons)

        self.btnSave = QPushButton(ManufacturerFormDialog)
        self.btnSave.setObjectName(u"btnSave")

        self.horizontalLayoutFormButtons.addWidget(self.btnSave)

        self.btnUpdate = QPushButton(ManufacturerFormDialog)
        self.btnUpdate.setObjectName(u"btnUpdate")
        self.btnUpdate.setVisible(False)

        self.horizontalLayoutFormButtons.addWidget(self.btnUpdate)

        self.btnClear = QPushButton(ManufacturerFormDialog)
        self.btnClear.setObjectName(u"btnClear")

        self.horizontalLayoutFormButtons.addWidget(self.btnClear)

        self.btnClose = QPushButton(ManufacturerFormDialog)
        self.btnClose.setObjectName(u"btnClose")

        self.horizontalLayoutFormButtons.addWidget(self.btnClose)


        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFormButtons)

#if QT_CONFIG(shortcut)
        self.lblManufacturerCode.setBuddy(self.txtManufacturerCode)
        self.lblManufacturerName.setBuddy(self.txtManufacturerName)
        self.lblCountry.setBuddy(self.txtCountry)
        self.lblDefaultMarginPercent.setBuddy(self.txtDefaultMarginPercent)
        self.lblStatus.setBuddy(self.cmbStatus)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.txtManufacturerCode, self.txtManufacturerName)
        QWidget.setTabOrder(self.txtManufacturerName, self.txtCountry)
        QWidget.setTabOrder(self.txtCountry, self.cmbStatus)
        QWidget.setTabOrder(self.cmbStatus, self.btnSave)
        QWidget.setTabOrder(self.btnSave, self.btnUpdate)
        QWidget.setTabOrder(self.btnUpdate, self.btnClear)
        QWidget.setTabOrder(self.btnClear, self.btnClose)

        self.retranslateUi(ManufacturerFormDialog)

        self.btnSave.setDefault(True)


        QMetaObject.connectSlotsByName(ManufacturerFormDialog)
    # setupUi

    def retranslateUi(self, ManufacturerFormDialog):
        ManufacturerFormDialog.setWindowTitle(QCoreApplication.translate("ManufacturerFormDialog", u"Manufacturer", None))
        self.lblFormTitle.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Manufacturer Details", None))
        self.grpBasicInfo.setTitle(QCoreApplication.translate("ManufacturerFormDialog", u"Basic Information", None))
        self.lblManufacturerCode.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Manufacturer Code:", None))
#if QT_CONFIG(tooltip)
        self.txtManufacturerCode.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Leave blank to auto-generate (e.g. MFG-0001)", None))
#endif // QT_CONFIG(tooltip)
        self.txtManufacturerCode.setPlaceholderText(QCoreApplication.translate("ManufacturerFormDialog", u"Auto-generated if left blank", None))
        self.lblManufacturerName.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Manufacturer Name: *", None))
#if QT_CONFIG(tooltip)
        self.txtManufacturerName.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Mandatory. Must be unique.", None))
#endif // QT_CONFIG(tooltip)
        self.lblManufacturerShortName.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Short Name:", None))
#if QT_CONFIG(tooltip)
        self.txtManufacturerShortName.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Auto-generated from the first word of the Manufacturer Name. Not editable.", None))
#endif // QT_CONFIG(tooltip)
        self.lblCountry.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Country:", None))
        self.lblDefaultMarginPercent.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Default Purchase Margin %:", None))
#if QT_CONFIG(tooltip)
        self.txtDefaultMarginPercent.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Used only to ESTIMATE Purchase Rate from MRP during Opening Stock entry (e.g. 20 means MRP - 20%). Leave blank if unknown -- rate stays fully manual then.", None))
#endif // QT_CONFIG(tooltip)
        self.grpStatus.setTitle(QCoreApplication.translate("ManufacturerFormDialog", u"Status", None))
        self.lblStatus.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Status:", None))
        self.cmbStatus.setItemText(0, QCoreApplication.translate("ManufacturerFormDialog", u"Active", None))
        self.cmbStatus.setItemText(1, QCoreApplication.translate("ManufacturerFormDialog", u"Inactive", None))

        self.lblValidationMessage.setText("")
        self.btnSave.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Save", None))
#if QT_CONFIG(tooltip)
        self.btnSave.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Save this manufacturer (Ctrl+S)", None))
#endif // QT_CONFIG(tooltip)
        self.btnUpdate.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Update", None))
#if QT_CONFIG(tooltip)
        self.btnUpdate.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Save changes to this manufacturer", None))
#endif // QT_CONFIG(tooltip)
        self.btnClear.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.btnClear.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Clear the form", None))
#endif // QT_CONFIG(tooltip)
        self.btnClose.setText(QCoreApplication.translate("ManufacturerFormDialog", u"Close", None))
#if QT_CONFIG(tooltip)
        self.btnClose.setToolTip(QCoreApplication.translate("ManufacturerFormDialog", u"Discard and close (Esc)", None))
#endif // QT_CONFIG(tooltip)
    # retranslateUi

