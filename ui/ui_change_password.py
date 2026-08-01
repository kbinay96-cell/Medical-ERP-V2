# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'change_password.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtGui import (QIcon, QFont)
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout)


class Ui_ChangePasswordDialog(object):
    def setupUi(self, ChangePasswordDialog):
        if not ChangePasswordDialog.objectName():
            ChangePasswordDialog.setObjectName(u"ChangePasswordDialog")
        ChangePasswordDialog.resize(420, 340)
        ChangePasswordDialog.setMinimumSize(QSize(400, 320))
        ChangePasswordDialog.setModal(True)

        self.verticalLayout_root = QVBoxLayout(ChangePasswordDialog)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")
        self.verticalLayout_root.setSpacing(12)
        self.verticalLayout_root.setContentsMargins(20, 20, 20, 16)

        self.lbl_form_title = QLabel(ChangePasswordDialog)
        self.lbl_form_title.setObjectName(u"lbl_form_title")
        font = self.lbl_form_title.font()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(QFont.Weight.Bold)
        self.lbl_form_title.setFont(font)
        self.verticalLayout_root.addWidget(self.lbl_form_title)

        self.line_top_sep = QFrame(ChangePasswordDialog)
        self.line_top_sep.setObjectName(u"line_top_sep")
        self.line_top_sep.setFrameShape(QFrame.HLine)
        self.line_top_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_top_sep)

        self.frame_fields = QFrame(ChangePasswordDialog)
        self.frame_fields.setObjectName(u"frame_fields")
        self.frame_fields.setFrameShape(QFrame.NoFrame)
        self.gridLayout_fields = QGridLayout(self.frame_fields)
        self.gridLayout_fields.setObjectName(u"gridLayout_fields")
        self.gridLayout_fields.setHorizontalSpacing(12)
        self.gridLayout_fields.setVerticalSpacing(10)
        self.gridLayout_fields.setContentsMargins(0, 0, 0, 0)

        self.lbl_old_password = QLabel(self.frame_fields)
        self.lbl_old_password.setObjectName(u"lbl_old_password")
        self.gridLayout_fields.addWidget(self.lbl_old_password, 0, 0, 1, 1)

        self.input_old_password = QLineEdit(self.frame_fields)
        self.input_old_password.setObjectName(u"input_old_password")
        self.input_old_password.setMinimumSize(QSize(0, 30))
        self.input_old_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_fields.addWidget(self.input_old_password, 0, 1, 1, 1)

        self.lbl_new_password = QLabel(self.frame_fields)
        self.lbl_new_password.setObjectName(u"lbl_new_password")
        self.gridLayout_fields.addWidget(self.lbl_new_password, 1, 0, 1, 1)

        self.input_new_password = QLineEdit(self.frame_fields)
        self.input_new_password.setObjectName(u"input_new_password")
        self.input_new_password.setMinimumSize(QSize(0, 30))
        self.input_new_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_fields.addWidget(self.input_new_password, 1, 1, 1, 1)

        self.lbl_confirm_password = QLabel(self.frame_fields)
        self.lbl_confirm_password.setObjectName(u"lbl_confirm_password")
        self.gridLayout_fields.addWidget(self.lbl_confirm_password, 2, 0, 1, 1)

        self.input_confirm_password = QLineEdit(self.frame_fields)
        self.input_confirm_password.setObjectName(u"input_confirm_password")
        self.input_confirm_password.setMinimumSize(QSize(0, 30))
        self.input_confirm_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_fields.addWidget(self.input_confirm_password, 2, 1, 1, 1)

        self.verticalLayout_root.addWidget(self.frame_fields)

        self.lbl_validation_message = QLabel(ChangePasswordDialog)
        self.lbl_validation_message.setObjectName(u"lbl_validation_message")
        self.lbl_validation_message.setStyleSheet(u"color: #C62828;")
        self.lbl_validation_message.setWordWrap(True)
        self.lbl_validation_message.setVisible(False)
        self.verticalLayout_root.addWidget(self.lbl_validation_message)

        self.verticalSpacer_fields = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.verticalLayout_root.addItem(self.verticalSpacer_fields)

        self.line_bottom_sep = QFrame(ChangePasswordDialog)
        self.line_bottom_sep.setObjectName(u"line_bottom_sep")
        self.line_bottom_sep.setFrameShape(QFrame.HLine)
        self.line_bottom_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_bottom_sep)

        self.frame_buttons = QFrame(ChangePasswordDialog)
        self.frame_buttons.setObjectName(u"frame_buttons")
        self.frame_buttons.setFrameShape(QFrame.NoFrame)
        self.horizontalLayout_buttons = QHBoxLayout(self.frame_buttons)
        self.horizontalLayout_buttons.setObjectName(u"horizontalLayout_buttons")
        self.horizontalLayout_buttons.setSpacing(10)
        self.horizontalLayout_buttons.setContentsMargins(0, 0, 0, 0)

        self.horizontalSpacer_buttons = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_buttons.addItem(self.horizontalSpacer_buttons)

        self.btn_cancel = QPushButton(self.frame_buttons)
        self.btn_cancel.setObjectName(u"btn_cancel")
        self.btn_cancel.setMinimumSize(QSize(100, 34))
        icon_cancel = QIcon()
        icon_cancel.addFile(u"resources/icons/cancel.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_cancel.setIcon(icon_cancel)
        self.horizontalLayout_buttons.addWidget(self.btn_cancel)

        self.btn_change = QPushButton(self.frame_buttons)
        self.btn_change.setObjectName(u"btn_change")
        self.btn_change.setMinimumSize(QSize(120, 34))
        self.btn_change.setDefault(True)
        icon_save = QIcon()
        icon_save.addFile(u"resources/icons/save.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_change.setIcon(icon_save)
        self.horizontalLayout_buttons.addWidget(self.btn_change)

        self.verticalLayout_root.addWidget(self.frame_buttons)

        self.retranslateUi(ChangePasswordDialog)

        QMetaObject.connectSlotsByName(ChangePasswordDialog)
    # setupUi

    def retranslateUi(self, ChangePasswordDialog):
        ChangePasswordDialog.setWindowTitle(QCoreApplication.translate("ChangePasswordDialog", u"Change Password", None))
        self.lbl_form_title.setText(QCoreApplication.translate("ChangePasswordDialog", u"Change Password", None))
        self.lbl_old_password.setText(QCoreApplication.translate("ChangePasswordDialog", u"Current Password *", None))
        self.input_old_password.setPlaceholderText(QCoreApplication.translate("ChangePasswordDialog", u"Enter current password", None))
        self.lbl_new_password.setText(QCoreApplication.translate("ChangePasswordDialog", u"New Password *", None))
        self.input_new_password.setPlaceholderText(QCoreApplication.translate("ChangePasswordDialog", u"Minimum 8 characters", None))
        self.lbl_confirm_password.setText(QCoreApplication.translate("ChangePasswordDialog", u"Confirm New Password *", None))
        self.input_confirm_password.setPlaceholderText(QCoreApplication.translate("ChangePasswordDialog", u"Re-enter new password", None))
        self.lbl_validation_message.setText("")
        self.btn_cancel.setText(QCoreApplication.translate("ChangePasswordDialog", u"Cancel", None))
        self.btn_change.setText(QCoreApplication.translate("ChangePasswordDialog", u" Change Password", None))
    # retranslateUi
