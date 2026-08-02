# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'user_form.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect, QSize, Qt)
from PySide6.QtGui import (QIcon, QFont)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)


class Ui_UserFormView(object):
    def setupUi(self, UserFormView):
        if not UserFormView.objectName():
            UserFormView.setObjectName(u"UserFormView")
        UserFormView.resize(520, 620)
        UserFormView.setMinimumSize(QSize(480, 580))
        UserFormView.setModal(True)

        self.verticalLayout_root = QVBoxLayout(UserFormView)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")
        self.verticalLayout_root.setSpacing(12)
        self.verticalLayout_root.setContentsMargins(20, 20, 20, 16)

        self.lbl_form_title = QLabel(UserFormView)
        self.lbl_form_title.setObjectName(u"lbl_form_title")
        font = self.lbl_form_title.font()
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(QFont.Weight.Bold)
        self.lbl_form_title.setFont(font)
        self.verticalLayout_root.addWidget(self.lbl_form_title)

        self.line_top_sep = QFrame(UserFormView)
        self.line_top_sep.setObjectName(u"line_top_sep")
        self.line_top_sep.setFrameShape(QFrame.HLine)
        self.line_top_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_top_sep)

        # ---- Scroll area ----
        self.scroll_area = QScrollArea(UserFormView)
        self.scroll_area.setObjectName(u"scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.scroll_area_contents = QWidget()
        self.scroll_area_contents.setObjectName(u"scroll_area_contents")
        self.scroll_area_contents.setGeometry(QRect(0, 0, 478, 460))
        self.verticalLayout_scroll = QVBoxLayout(self.scroll_area_contents)
        self.verticalLayout_scroll.setObjectName(u"verticalLayout_scroll")
        self.verticalLayout_scroll.setSpacing(14)
        self.verticalLayout_scroll.setContentsMargins(2, 2, 2, 2)

        # ---- Identity group ----
        self.group_identity = QGroupBox(self.scroll_area_contents)
        self.group_identity.setObjectName(u"group_identity")
        self.gridLayout_identity = QGridLayout(self.group_identity)
        self.gridLayout_identity.setObjectName(u"gridLayout_identity")
        self.gridLayout_identity.setHorizontalSpacing(12)
        self.gridLayout_identity.setVerticalSpacing(10)
        self.gridLayout_identity.setContentsMargins(12, 16, 12, 12)

        self.lbl_username = QLabel(self.group_identity)
        self.lbl_username.setObjectName(u"lbl_username")
        self.gridLayout_identity.addWidget(self.lbl_username, 0, 0, 1, 1)

        self.input_username = QLineEdit(self.group_identity)
        self.input_username.setObjectName(u"input_username")
        self.input_username.setMinimumSize(QSize(0, 38))
        self.input_username.setMaxLength(50)
        self.gridLayout_identity.addWidget(self.input_username, 0, 1, 1, 1)

        self.lbl_display_name = QLabel(self.group_identity)
        self.lbl_display_name.setObjectName(u"lbl_display_name")
        self.gridLayout_identity.addWidget(self.lbl_display_name, 1, 0, 1, 1)

        self.input_display_name = QLineEdit(self.group_identity)
        self.input_display_name.setObjectName(u"input_display_name")
        self.input_display_name.setMinimumSize(QSize(0, 38))
        self.input_display_name.setMaxLength(150)
        self.gridLayout_identity.addWidget(self.input_display_name, 1, 1, 1, 1)

        self.lbl_email = QLabel(self.group_identity)
        self.lbl_email.setObjectName(u"lbl_email")
        self.gridLayout_identity.addWidget(self.lbl_email, 2, 0, 1, 1)

        self.input_email = QLineEdit(self.group_identity)
        self.input_email.setObjectName(u"input_email")
        self.input_email.setMinimumSize(QSize(0, 38))
        self.input_email.setMaxLength(150)
        self.gridLayout_identity.addWidget(self.input_email, 2, 1, 1, 1)

        self.lbl_phone = QLabel(self.group_identity)
        self.lbl_phone.setObjectName(u"lbl_phone")
        self.gridLayout_identity.addWidget(self.lbl_phone, 3, 0, 1, 1)

        self.input_phone = QLineEdit(self.group_identity)
        self.input_phone.setObjectName(u"input_phone")
        self.input_phone.setMinimumSize(QSize(0, 38))
        self.input_phone.setMaxLength(20)
        self.gridLayout_identity.addWidget(self.input_phone, 3, 1, 1, 1)

        self.verticalLayout_scroll.addWidget(self.group_identity)

        # ---- Access & mapping group ----
        self.group_access = QGroupBox(self.scroll_area_contents)
        self.group_access.setObjectName(u"group_access")
        self.gridLayout_access = QGridLayout(self.group_access)
        self.gridLayout_access.setObjectName(u"gridLayout_access")
        self.gridLayout_access.setHorizontalSpacing(12)
        self.gridLayout_access.setVerticalSpacing(10)
        self.gridLayout_access.setContentsMargins(12, 16, 12, 12)

        self.lbl_role = QLabel(self.group_access)
        self.lbl_role.setObjectName(u"lbl_role")
        self.gridLayout_access.addWidget(self.lbl_role, 0, 0, 1, 1)

        self.combo_role = QComboBox(self.group_access)
        self.combo_role.addItem("")
        self.combo_role.setObjectName(u"combo_role")
        self.combo_role.setMinimumSize(QSize(0, 38))
        self.gridLayout_access.addWidget(self.combo_role, 0, 1, 1, 1)

        self.lbl_company = QLabel(self.group_access)
        self.lbl_company.setObjectName(u"lbl_company")
        self.gridLayout_access.addWidget(self.lbl_company, 1, 0, 1, 1)

        self.combo_company = QComboBox(self.group_access)
        self.combo_company.addItem("")
        self.combo_company.setObjectName(u"combo_company")
        self.combo_company.setMinimumSize(QSize(0, 38))
        self.gridLayout_access.addWidget(self.combo_company, 1, 1, 1, 1)

        self.verticalLayout_scroll.addWidget(self.group_access)

        # ---- Password group ----
        self.group_password = QGroupBox(self.scroll_area_contents)
        self.group_password.setObjectName(u"group_password")
        self.gridLayout_password = QGridLayout(self.group_password)
        self.gridLayout_password.setObjectName(u"gridLayout_password")
        self.gridLayout_password.setHorizontalSpacing(12)
        self.gridLayout_password.setVerticalSpacing(10)
        self.gridLayout_password.setContentsMargins(12, 16, 12, 12)

        self.lbl_password = QLabel(self.group_password)
        self.lbl_password.setObjectName(u"lbl_password")
        self.gridLayout_password.addWidget(self.lbl_password, 0, 0, 1, 1)

        self.input_password = QLineEdit(self.group_password)
        self.input_password.setObjectName(u"input_password")
        self.input_password.setMinimumSize(QSize(0, 38))
        self.input_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_password.addWidget(self.input_password, 0, 1, 1, 1)

        self.lbl_confirm_password = QLabel(self.group_password)
        self.lbl_confirm_password.setObjectName(u"lbl_confirm_password")
        self.gridLayout_password.addWidget(self.lbl_confirm_password, 1, 0, 1, 1)

        self.input_confirm_password = QLineEdit(self.group_password)
        self.input_confirm_password.setObjectName(u"input_confirm_password")
        self.input_confirm_password.setMinimumSize(QSize(0, 38))
        self.input_confirm_password.setEchoMode(QLineEdit.Password)
        self.gridLayout_password.addWidget(self.input_confirm_password, 1, 1, 1, 1)

        self.verticalLayout_scroll.addWidget(self.group_password)

        # ---- Flags row ----
        self.frame_flags = QFrame(self.scroll_area_contents)
        self.frame_flags.setObjectName(u"frame_flags")
        self.frame_flags.setFrameShape(QFrame.NoFrame)
        self.horizontalLayout_flags = QHBoxLayout(self.frame_flags)
        self.horizontalLayout_flags.setObjectName(u"horizontalLayout_flags")
        self.horizontalLayout_flags.setSpacing(20)
        self.horizontalLayout_flags.setContentsMargins(0, 0, 0, 0)

        self.chk_must_change_password = QCheckBox(self.frame_flags)
        self.chk_must_change_password.setObjectName(u"chk_must_change_password")
        self.chk_must_change_password.setChecked(True)
        self.horizontalLayout_flags.addWidget(self.chk_must_change_password)

        self.chk_is_active = QCheckBox(self.frame_flags)
        self.chk_is_active.setObjectName(u"chk_is_active")
        self.chk_is_active.setChecked(True)
        self.horizontalLayout_flags.addWidget(self.chk_is_active)

        self.horizontalSpacer_flags = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_flags.addItem(self.horizontalSpacer_flags)

        self.verticalLayout_scroll.addWidget(self.frame_flags)

        self.scroll_area.setWidget(self.scroll_area_contents)
        self.verticalLayout_root.addWidget(self.scroll_area)

        # ---- Validation message ----
        self.lbl_validation_message = QLabel(UserFormView)
        self.lbl_validation_message.setObjectName(u"lbl_validation_message")
        self.lbl_validation_message.setStyleSheet(u"color: #C62828;")
        self.lbl_validation_message.setWordWrap(True)
        self.lbl_validation_message.setVisible(False)
        self.verticalLayout_root.addWidget(self.lbl_validation_message)

        self.line_bottom_sep = QFrame(UserFormView)
        self.line_bottom_sep.setObjectName(u"line_bottom_sep")
        self.line_bottom_sep.setFrameShape(QFrame.HLine)
        self.line_bottom_sep.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_root.addWidget(self.line_bottom_sep)

        # ---- Buttons ----
        self.frame_buttons = QFrame(UserFormView)
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

        self.btn_save = QPushButton(self.frame_buttons)
        self.btn_save.setObjectName(u"btn_save")
        self.btn_save.setMinimumSize(QSize(110, 34))
        self.btn_save.setDefault(True)
        icon_save = QIcon()
        icon_save.addFile(u"resources/icons/save.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_save.setIcon(icon_save)
        self.horizontalLayout_buttons.addWidget(self.btn_save)

        self.verticalLayout_root.addWidget(self.frame_buttons)

        self.retranslateUi(UserFormView)

        QMetaObject.connectSlotsByName(UserFormView)
    # setupUi

    def retranslateUi(self, UserFormView):
        UserFormView.setWindowTitle(QCoreApplication.translate("UserFormView", u"User Form", None))
        self.lbl_form_title.setText(QCoreApplication.translate("UserFormView", u"New User", None))
        self.group_identity.setTitle(QCoreApplication.translate("UserFormView", u"Identity", None))
        self.lbl_username.setText(QCoreApplication.translate("UserFormView", u"Username *", None))
        self.input_username.setPlaceholderText(QCoreApplication.translate("UserFormView", u"e.g. jsmith", None))
        self.lbl_display_name.setText(QCoreApplication.translate("UserFormView", u"Display Name *", None))
        self.input_display_name.setPlaceholderText(QCoreApplication.translate("UserFormView", u"e.g. John Smith", None))
        self.lbl_email.setText(QCoreApplication.translate("UserFormView", u"Email", None))
        self.input_email.setPlaceholderText(QCoreApplication.translate("UserFormView", u"name@example.com", None))
        self.lbl_phone.setText(QCoreApplication.translate("UserFormView", u"Phone", None))
        self.input_phone.setPlaceholderText(QCoreApplication.translate("UserFormView", u"e.g. 98XXXXXXXX", None))
        self.group_access.setTitle(QCoreApplication.translate("UserFormView", u"Access && Mapping", None))
        self.lbl_role.setText(QCoreApplication.translate("UserFormView", u"Role", None))
        self.combo_role.setItemText(0, QCoreApplication.translate("UserFormView", u"-- Select Role --", None))
        self.lbl_company.setText(QCoreApplication.translate("UserFormView", u"Company", None))
        self.combo_company.setItemText(0, QCoreApplication.translate("UserFormView", u"-- Select Company --", None))
        self.group_password.setTitle(QCoreApplication.translate("UserFormView", u"Password", None))
        self.lbl_password.setText(QCoreApplication.translate("UserFormView", u"Password *", None))
        self.input_password.setPlaceholderText(QCoreApplication.translate("UserFormView", u"Minimum 8 characters", None))
        self.lbl_confirm_password.setText(QCoreApplication.translate("UserFormView", u"Confirm Password *", None))
        self.input_confirm_password.setPlaceholderText(QCoreApplication.translate("UserFormView", u"Re-enter password", None))
        self.chk_must_change_password.setText(QCoreApplication.translate("UserFormView", u"Must change password at next login", None))
        self.chk_is_active.setText(QCoreApplication.translate("UserFormView", u"Active", None))
        self.lbl_validation_message.setText("")
        self.btn_cancel.setText(QCoreApplication.translate("UserFormView", u"Cancel", None))
        self.btn_save.setText(QCoreApplication.translate("UserFormView", u" Save", None))
    # retranslateUi
