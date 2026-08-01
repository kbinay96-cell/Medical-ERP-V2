# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'reset_password.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QSize, Qt)
from PySide6.QtGui import (QIcon, QFont)
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout)


class Ui_ResetPasswordDialog(object):
    def setupUi(self, ResetPasswordDialog):
        if not ResetPasswordDialog.objectName():
            ResetPasswordDialog.setObjectName(u"ResetPasswordDialog")
        ResetPasswordDialog.resize(420, 300)
        ResetPasswordDialog.setMinimumSize(QSize(400, 280))
        ResetPasswordDialog.setModal(True)

        self.verticalLayout_root = QVBoxLayout(ResetPasswordDialog)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")
        self.verticalLayout_root.setSpacing(12)
        self.verticalLayout_root.setContentsMargins(20, 20, 20, 16)

        self.lbl_form_title = QLabel(ResetPasswordDialog)
        self.lbl_form_title.setObjectName(u"lbl_form_title")
        font = self.lbl_form_title.font()
        font.setPointSize(13)
        font.setBold(True)
        font.setWeight(QFont.Weight.Bold)
        self.lbl_form_title.setFont(font)
        self.verticalLayout_root.addWidget(self.lbl_form_title)

        self.lbl_target_user = QLabel(ResetPasswordDialog)
        self.lbl_target_user.setObjectName(u"lbl_target_user")
        self.lbl_target_user.setStyleSheet(u"color: #546E7A;")
        self.verticalLayout_root.addWidget(self.lbl_target_user)

        self.line_top_sep = QFrame(ResetPasswordDialog)
        self.line_top_sep.setObjectName(u"line_top_sep")
        self.line_top_sep.setFrameShape(QFrame.HLine)
        self.line_top_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_top_sep)

        self.frame_fields = QFrame(ResetPasswordDialog)
        self.frame_fields.setObjectName(u"frame_fields")
        self.frame_fields.setFrameShape(QFrame.NoFrame)
        self.gridLayout_fields = QGridLayout(self.frame_fields)
        self.gridLayout_fields.setObjectName(u"gridLayout_fields")
        self.gridLayout_fields.setHorizontalSpacing(12)
        self.gridLayout_fields.setVerticalSpacing(10)
        self.gridLayout_fields.setContentsMargins(0, 0, 0, 0)

        self.lbl_new_password = QLabel(self.frame_fields)
        self.lbl_new_password.setObjectName(u"lbl_new_password")
        self.gridLayout_fields.addWidget(self.lbl_new_password, 0, 0, 1, 1)

        self.input_new_password = QLineEdit(self.frame_fields)
        self.input_new_password.setObjectName(u"input_new_password")
        self.input_new_password.setMinimumSize(QSize(0, 30))
        self.input_new_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_fields.addWidget(self.input_new_password, 0, 1, 1, 1)

        self.lbl_confirm_password = QLabel(self.frame_fields)
        self.lbl_confirm_password.setObjectName(u"lbl_confirm_password")
        self.gridLayout_fields.addWidget(self.lbl_confirm_password, 1, 0, 1, 1)

        self.input_confirm_password = QLineEdit(self.frame_fields)
        self.input_confirm_password.setObjectName(u"input_confirm_password")
        self.input_confirm_password.setMinimumSize(QSize(0, 30))
        self.input_confirm_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_fields.addWidget(self.input_confirm_password, 1, 1, 1, 1)

        self.verticalLayout_root.addWidget(self.frame_fields)

        self.chk_force_change_on_login = QCheckBox(ResetPasswordDialog)
        self.chk_force_change_on_login.setObjectName(u"chk_force_change_on_login")
        self.chk_force_change_on_login.setChecked(True)
        self.verticalLayout_root.addWidget(self.chk_force_change_on_login)

        self.lbl_validation_message = QLabel(ResetPasswordDialog)
        self.lbl_validation_message.setObjectName(u"lbl_validation_message")
        self.lbl_validation_message.setStyleSheet(u"color: #C62828;")
        self.lbl_validation_message.setWordWrap(True)
        self.lbl_validation_message.setVisible(False)
        self.verticalLayout_root.addWidget(self.lbl_validation_message)

        self.verticalSpacer_fields = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.verticalLayout_root.addItem(self.verticalSpacer_fields)

        self.line_bottom_sep = QFrame(ResetPasswordDialog)
        self.line_bottom_sep.setObjectName(u"line_bottom_sep")
        self.line_bottom_sep.setFrameShape(QFrame.HLine)
        self.line_bottom_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_bottom_sep)

        self.frame_buttons = QFrame(ResetPasswordDialog)
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

        self.btn_reset = QPushButton(self.frame_buttons)
        self.btn_reset.setObjectName(u"btn_reset")
        self.btn_reset.setMinimumSize(QSize(120, 34))
        self.btn_reset.setDefault(True)
        icon_reset = QIcon()
        icon_reset.addFile(u"resources/icons/reset_password.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_reset.setIcon(icon_reset)
        self.horizontalLayout_buttons.addWidget(self.btn_reset)

        self.verticalLayout_root.addWidget(self.frame_buttons)

        self.retranslateUi(ResetPasswordDialog)

        QMetaObject.connectSlotsByName(ResetPasswordDialog)
    # setupUi

    def retranslateUi(self, ResetPasswordDialog):
        ResetPasswordDialog.setWindowTitle(QCoreApplication.translate("ResetPasswordDialog", u"Reset Password", None))
        self.lbl_form_title.setText(QCoreApplication.translate("ResetPasswordDialog", u"Reset Password", None))
        self.lbl_target_user.setText(QCoreApplication.translate("ResetPasswordDialog", u"Resetting password for: -", None))
        self.lbl_new_password.setText(QCoreApplication.translate("ResetPasswordDialog", u"New Password *", None))
        self.input_new_password.setPlaceholderText(QCoreApplication.translate("ResetPasswordDialog", u"Minimum 8 characters", None))
        self.lbl_confirm_password.setText(QCoreApplication.translate("ResetPasswordDialog", u"Confirm Password *", None))
        self.input_confirm_password.setPlaceholderText(QCoreApplication.translate("ResetPasswordDialog", u"Re-enter password", None))
        self.chk_force_change_on_login.setText(QCoreApplication.translate("ResetPasswordDialog", u"Require password change at next login", None))
        self.lbl_validation_message.setText("")
        self.btn_cancel.setText(QCoreApplication.translate("ResetPasswordDialog", u"Cancel", None))
        self.btn_reset.setText(QCoreApplication.translate("ResetPasswordDialog", u" Reset Password", None))
    # retranslateUi
