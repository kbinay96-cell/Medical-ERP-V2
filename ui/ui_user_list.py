# -*- coding: utf-8 -*-
################################################################################
## Form generated from reading UI file 'user_list.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect, QSize, Qt)
from PySide6.QtGui import (QIcon, QFont)
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QStatusBar, QTableView, QVBoxLayout, QWidget)


class Ui_UserListView(object):
    def setupUi(self, UserListView):
        if not UserListView.objectName():
            UserListView.setObjectName(u"UserListView")
        UserListView.resize(1180, 720)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(UserListView.sizePolicy().hasHeightForWidth())
        UserListView.setSizePolicy(sizePolicy)

        self.verticalLayout_root = QVBoxLayout(UserListView)
        self.verticalLayout_root.setObjectName(u"verticalLayout_root")
        self.verticalLayout_root.setSpacing(10)
        self.verticalLayout_root.setContentsMargins(16, 16, 16, 12)

        # ---- Title ----
        self.lbl_title = QLabel(UserListView)
        self.lbl_title.setObjectName(u"lbl_title")
        font = self.lbl_title.font()
        font.setPointSize(15)
        font.setBold(True)
        font.setWeight(QFont.Weight.Bold)
        self.lbl_title.setFont(font)
        self.verticalLayout_root.addWidget(self.lbl_title)

        # ---- Filter bar ----
        self.frame_filters = QFrame(UserListView)
        self.frame_filters.setObjectName(u"frame_filters")
        self.frame_filters.setFrameShape(QFrame.StyledPanel)
        self.frame_filters.setFrameShadow(QFrame.Raised)
        self.frame_filters.setStyleSheet(u"#frame_filters { background-color: #F5F7FA; border: 1px solid #E1E5EA; border-radius: 6px; }")
        self.horizontalLayout_filters = QHBoxLayout(self.frame_filters)
        self.horizontalLayout_filters.setObjectName(u"horizontalLayout_filters")
        self.horizontalLayout_filters.setSpacing(10)
        self.horizontalLayout_filters.setContentsMargins(12, 10, 12, 10)

        self.lbl_search = QLabel(self.frame_filters)
        self.lbl_search.setObjectName(u"lbl_search")
        self.horizontalLayout_filters.addWidget(self.lbl_search)

        self.search_input = QLineEdit(self.frame_filters)
        self.search_input.setObjectName(u"search_input")
        self.search_input.setMinimumSize(QSize(220, 30))
        self.search_input.setClearButtonEnabled(True)
        self.horizontalLayout_filters.addWidget(self.search_input)

        self.lbl_status_filter = QLabel(self.frame_filters)
        self.lbl_status_filter.setObjectName(u"lbl_status_filter")
        self.horizontalLayout_filters.addWidget(self.lbl_status_filter)

        self.filter_status = QComboBox(self.frame_filters)
        self.filter_status.addItem("")
        self.filter_status.addItem("")
        self.filter_status.addItem("")
        self.filter_status.addItem("")
        self.filter_status.setObjectName(u"filter_status")
        self.filter_status.setMinimumSize(QSize(120, 30))
        self.horizontalLayout_filters.addWidget(self.filter_status)

        self.lbl_role_filter = QLabel(self.frame_filters)
        self.lbl_role_filter.setObjectName(u"lbl_role_filter")
        self.horizontalLayout_filters.addWidget(self.lbl_role_filter)

        self.filter_role = QComboBox(self.frame_filters)
        self.filter_role.addItem("")
        self.filter_role.setObjectName(u"filter_role")
        self.filter_role.setMinimumSize(QSize(150, 30))
        self.horizontalLayout_filters.addWidget(self.filter_role)

        self.lbl_company_filter = QLabel(self.frame_filters)
        self.lbl_company_filter.setObjectName(u"lbl_company_filter")
        self.horizontalLayout_filters.addWidget(self.lbl_company_filter)

        self.filter_company = QComboBox(self.frame_filters)
        self.filter_company.addItem("")
        self.filter_company.setObjectName(u"filter_company")
        self.filter_company.setMinimumSize(QSize(160, 30))
        self.horizontalLayout_filters.addWidget(self.filter_company)

        self.horizontalSpacer_filters = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_filters.addItem(self.horizontalSpacer_filters)

        self.btn_refresh = QPushButton(self.frame_filters)
        self.btn_refresh.setObjectName(u"btn_refresh")
        self.btn_refresh.setMinimumSize(QSize(110, 32))
        icon_refresh = QIcon()
        icon_refresh.addFile(u"resources/icons/refresh.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_refresh.setIcon(icon_refresh)
        self.horizontalLayout_filters.addWidget(self.btn_refresh)

        self.verticalLayout_root.addWidget(self.frame_filters)

        # ---- Action bar ----
        self.frame_actions = QFrame(UserListView)
        self.frame_actions.setObjectName(u"frame_actions")
        self.frame_actions.setFrameShape(QFrame.NoFrame)
        self.horizontalLayout_actions = QHBoxLayout(self.frame_actions)
        self.horizontalLayout_actions.setObjectName(u"horizontalLayout_actions")
        self.horizontalLayout_actions.setSpacing(8)
        self.horizontalLayout_actions.setContentsMargins(0, 0, 0, 0)

        self.btn_new = QPushButton(self.frame_actions)
        self.btn_new.setObjectName(u"btn_new")
        self.btn_new.setMinimumSize(QSize(100, 34))
        icon_new = QIcon()
        icon_new.addFile(u"resources/icons/new_user.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_new.setIcon(icon_new)
        self.btn_new.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_new)

        self.btn_edit = QPushButton(self.frame_actions)
        self.btn_edit.setObjectName(u"btn_edit")
        self.btn_edit.setMinimumSize(QSize(90, 34))
        icon_edit = QIcon()
        icon_edit.addFile(u"resources/icons/edit.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_edit.setIcon(icon_edit)
        self.btn_edit.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_edit)

        self.btn_delete = QPushButton(self.frame_actions)
        self.btn_delete.setObjectName(u"btn_delete")
        self.btn_delete.setMinimumSize(QSize(90, 34))
        icon_delete = QIcon()
        icon_delete.addFile(u"resources/icons/delete.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_delete.setIcon(icon_delete)
        self.btn_delete.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_delete)

        self.btn_restore = QPushButton(self.frame_actions)
        self.btn_restore.setObjectName(u"btn_restore")
        self.btn_restore.setMinimumSize(QSize(100, 34))
        icon_restore = QIcon()
        icon_restore.addFile(u"resources/icons/restore.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_restore.setIcon(icon_restore)
        self.btn_restore.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_restore)

        self.btn_toggle_active = QPushButton(self.frame_actions)
        self.btn_toggle_active.setObjectName(u"btn_toggle_active")
        self.btn_toggle_active.setMinimumSize(QSize(150, 34))
        icon_toggle = QIcon()
        icon_toggle.addFile(u"resources/icons/toggle_active.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_toggle_active.setIcon(icon_toggle)
        self.btn_toggle_active.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_toggle_active)

        self.btn_reset_password = QPushButton(self.frame_actions)
        self.btn_reset_password.setObjectName(u"btn_reset_password")
        self.btn_reset_password.setMinimumSize(QSize(140, 34))
        icon_reset = QIcon()
        icon_reset.addFile(u"resources/icons/reset_password.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_reset_password.setIcon(icon_reset)
        self.btn_reset_password.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_reset_password)

        self.line_actions_sep = QFrame(self.frame_actions)
        self.line_actions_sep.setObjectName(u"line_actions_sep")
        self.line_actions_sep.setFrameShape(QFrame.VLine)
        self.line_actions_sep.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_actions.addWidget(self.line_actions_sep)

        self.btn_export = QPushButton(self.frame_actions)
        self.btn_export.setObjectName(u"btn_export")
        self.btn_export.setMinimumSize(QSize(100, 34))
        icon_export = QIcon()
        icon_export.addFile(u"resources/icons/export.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_export.setIcon(icon_export)
        self.btn_export.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_export)

        self.btn_print = QPushButton(self.frame_actions)
        self.btn_print.setObjectName(u"btn_print")
        self.btn_print.setMinimumSize(QSize(90, 34))
        icon_print = QIcon()
        icon_print.addFile(u"resources/icons/print.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_print.setIcon(icon_print)
        self.btn_print.setIconSize(QSize(18, 18))
        self.horizontalLayout_actions.addWidget(self.btn_print)

        self.horizontalSpacer_actions = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_actions.addItem(self.horizontalSpacer_actions)

        self.verticalLayout_root.addWidget(self.frame_actions)

        # ---- Table ----
        self.table_users = QTableView(UserListView)
        self.table_users.setObjectName(u"table_users")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(1)
        sizePolicy1.setHeightForWidth(self.table_users.sizePolicy().hasHeightForWidth())
        self.table_users.setSizePolicy(sizePolicy1)
        self.table_users.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_users.setAlternatingRowColors(True)
        self.table_users.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_users.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_users.setSortingEnabled(True)
        self.table_users.setWordWrap(False)
        self.table_users.horizontalHeader().setStretchLastSection(True)
        self.table_users.verticalHeader().setVisible(False)
        self.verticalLayout_root.addWidget(self.table_users)

        # ---- Status bar ----
        self.status_bar = QStatusBar(UserListView)
        self.status_bar.setObjectName(u"status_bar")
        self.status_bar.setSizeGripEnabled(True)
        self.verticalLayout_root.addWidget(self.status_bar)

        self.retranslateUi(UserListView)

        QMetaObject.connectSlotsByName(UserListView)
    # setupUi

    def retranslateUi(self, UserListView):
        UserListView.setWindowTitle(QCoreApplication.translate("UserListView", u"User Master", None))
        self.lbl_title.setText(QCoreApplication.translate("UserListView", u"User Master", None))
        self.lbl_search.setText(QCoreApplication.translate("UserListView", u"Search:", None))
        self.search_input.setPlaceholderText(QCoreApplication.translate("UserListView", u"Search by username or display name...", None))
        self.lbl_status_filter.setText(QCoreApplication.translate("UserListView", u"Status:", None))
        self.filter_status.setItemText(0, QCoreApplication.translate("UserListView", u"All", None))
        self.filter_status.setItemText(1, QCoreApplication.translate("UserListView", u"Active", None))
        self.filter_status.setItemText(2, QCoreApplication.translate("UserListView", u"Inactive", None))
        self.filter_status.setItemText(3, QCoreApplication.translate("UserListView", u"Deleted", None))
        self.lbl_role_filter.setText(QCoreApplication.translate("UserListView", u"Role:", None))
        self.filter_role.setItemText(0, QCoreApplication.translate("UserListView", u"All Roles", None))
        self.lbl_company_filter.setText(QCoreApplication.translate("UserListView", u"Company:", None))
        self.filter_company.setItemText(0, QCoreApplication.translate("UserListView", u"All Companies", None))
        self.btn_refresh.setToolTip(QCoreApplication.translate("UserListView", u"Refresh list", None))
        self.btn_refresh.setText(QCoreApplication.translate("UserListView", u" Refresh", None))
        self.btn_new.setText(QCoreApplication.translate("UserListView", u" New", None))
        self.btn_edit.setText(QCoreApplication.translate("UserListView", u" Edit", None))
        self.btn_delete.setText(QCoreApplication.translate("UserListView", u" Delete", None))
        self.btn_restore.setText(QCoreApplication.translate("UserListView", u" Restore", None))
        self.btn_toggle_active.setText(QCoreApplication.translate("UserListView", u" Activate/Deactivate", None))
        self.btn_reset_password.setText(QCoreApplication.translate("UserListView", u" Reset Password", None))
        self.btn_export.setText(QCoreApplication.translate("UserListView", u" Export", None))
        self.btn_print.setText(QCoreApplication.translate("UserListView", u" Print", None))
    # retranslateUi
