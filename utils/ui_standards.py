"""
Shared Master-screen UI sizing: action buttons and table columns.

Presentation only — Screens still call Engines for data.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QTreeView,
    QTableView,
    QTableWidget,
    QWidget,
)

ACTION_BUTTON_MIN_WIDTH = 144
ACTION_BUTTON_MIN_HEIGHT = 28

_ACTION_KEYWORDS = (
    "save", "edit", "delete", "clear", "close", "cancel", "add", "restore",
    "refresh", "new", "print", "export", "activate", "deactivate",
)


def apply_action_button_style(button: QPushButton) -> None:
    # Height is intentionally NOT set here anymore — it now comes from
    # the dynamic QSS override (ui.control_height setting) so it stays
    # adjustable at runtime. setMinimumSize() would silently override
    # any stylesheet min-height, so only width is enforced in code.
    button.setMinimumWidth(ACTION_BUTTON_MIN_WIDTH)
    button.setProperty("cssClass", "actionButton")
    button.style().unpolish(button)
    button.style().polish(button)


def standardize_action_buttons(root: QWidget) -> None:
    """Uniform height/width/padding for Save, Edit, Delete, Clear, Close, and siblings."""
    for button in root.findChildren(QPushButton):
        if button.property("cssClass") == "rowIconBtn":
            continue
        blob = f"{button.objectName()} {button.text()}".lower()
        if any(keyword in blob for keyword in _ACTION_KEYWORDS):
            apply_action_button_style(button)


def add_embedded_back_button(root: QWidget, layout, callback, label: str = "← Back") -> QPushButton:
    """Add a consistent navigation control to the top of an embedded page."""
    row = QHBoxLayout()
    button = QPushButton(label)
    button.setObjectName("btnEmbeddedBack")
    button.setProperty("cssClass", "actionButton")
    button.clicked.connect(callback)
    row.addWidget(button)
    row.addStretch(1)
    layout.insertLayout(0, row)
    return button


def apply_application_density(app, control_height: int) -> None:
    """Tighten existing layouts and table rows to match the active control size."""
    margin_limit = max(6, min(12, control_height // 4))
    spacing_limit = max(4, min(8, control_height // 6))
    table_action_buttons = {
        button
        for table in app.allWidgets()
        if isinstance(table, QTableView)
        for button in table.findChildren(QPushButton)
        if button.property("cssClass") != "rowIconBtn"
    }

    for widget in app.allWidgets():
        layout = widget.layout()
        if layout is not None:
            if not hasattr(layout, "_erp_base_margins"):
                layout._erp_base_margins = layout.getContentsMargins()
                layout._erp_base_spacing = layout.spacing()
            left, top, right, bottom = layout._erp_base_margins
            margins = (
                min(left, margin_limit),
                min(top, margin_limit),
                min(right, margin_limit),
                min(bottom, margin_limit),
            )
            if margins != (left, top, right, bottom):
                layout.setContentsMargins(*margins)
            base_spacing = layout._erp_base_spacing
            if base_spacing >= 0 and base_spacing > spacing_limit:
                layout.setSpacing(spacing_limit)
            elif base_spacing >= 0:
                layout.setSpacing(base_spacing)

        if isinstance(widget, QPushButton):
            css_class = widget.property("cssClass")
            if css_class == "bsCalendarDayButton":
                fixed_width = widget.property("uiDensityFixedWidth")
                fixed_height = widget.property("uiDensityFixedHeight")
                if fixed_width and fixed_height:
                    widget.setFixedSize(int(fixed_width), int(fixed_height))
            else:
                if widget in table_action_buttons:
                    css_class = "rowActionButton"
                    widget.setProperty("cssClass", css_class)
                widget.setProperty("uiDensityButton", True)
                width = "32" if css_class == "rowIconBtn" else (
                    "84" if css_class == "rowActionButton" else "144"
                )
                widget.setProperty("uiButtonWidth", width)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.setFixedSize(int(width), control_height)
        elif isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit)):
            widget.setFixedHeight(control_height)

        if isinstance(widget, QTableView):
            widget.setWordWrap(False)
            widget.setAlternatingRowColors(True)
            widget.verticalHeader().setVisible(False)
            widget.verticalHeader().setDefaultSectionSize(control_height)
            widget.horizontalHeader().setFixedHeight(control_height)
        elif isinstance(widget, QTreeView):
            widget.setUniformRowHeights(True)


def configure_table_columns(
    table: QTableView | QTableWidget,
    *,
    stretch_columns: Sequence[int] = (),
    content_columns: Optional[Iterable[int]] = None,
) -> None:
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    column_count = table.columnCount() if isinstance(table, QTableWidget) else table.model().columnCount()
    content_set = set(content_columns) if content_columns is not None else None
    stretch_set = set(stretch_columns)

    for index in range(column_count):
        if index in stretch_set:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        elif content_set is None or index in content_set:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        else:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)

    if isinstance(table, QTableWidget):
        for index in range(column_count):
            if index not in stretch_set:
                table.resizeColumnToContents(index)
    else:
        for index in range(column_count):
            if index not in stretch_set:
                table.resizeColumnToContents(index)


def install_detail_splitter(root_layout, table_widget: QWidget, panel: QWidget, stretch=(3, 1)):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter

    index = root_layout.indexOf(table_widget)
    root_layout.removeWidget(table_widget)
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)
    splitter.addWidget(table_widget)
    splitter.addWidget(panel)
    splitter.setStretchFactor(0, stretch[0])
    splitter.setStretchFactor(1, stretch[1])
    root_layout.insertWidget(index, splitter, 1)
    return splitter


__all__ = [
    "ACTION_BUTTON_MIN_WIDTH",
    "ACTION_BUTTON_MIN_HEIGHT",
    "apply_action_button_style",
    "standardize_action_buttons",
    "add_embedded_back_button",
    "apply_application_density",
    "configure_table_columns",
    "install_detail_splitter",
]
