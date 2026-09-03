"""
Shared Master-screen UI sizing: action buttons and table columns.

Presentation only — Screens still call Engines for data.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from PySide6.QtWidgets import QHeaderView, QPushButton, QTableView, QTableWidget, QWidget

ACTION_BUTTON_MIN_WIDTH = 110
ACTION_BUTTON_MIN_HEIGHT = 34

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
    "configure_table_columns",
    "install_detail_splitter",
]
