"""
utils/password_field_helper.py

Adds a click-to-reveal "eye" icon inside any password QLineEdit.
Shared by user_form_screen.py, change_password_screen.py, and
reset_password_screen.py so the toggle behavior is written once.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLineEdit
from utils.icon_utils import themed_icon_from_path

_EYE_OPEN_ICON = "resources/icons/eye.svg"
_EYE_CLOSED_ICON = "resources/icons/eye_off.svg"


def attach_show_password_toggle(line_edit: QLineEdit) -> None:
    """Adds a clickable eye icon to the right side of a password field
    that toggles between hidden and visible text."""
    line_edit.setEchoMode(QLineEdit.EchoMode.Password)

    action = line_edit.addAction(themed_icon_from_path(_EYE_OPEN_ICON), QLineEdit.ActionPosition.TrailingPosition)
    action.setCheckable(True)
    action.setToolTip("Show password")

    def _on_toggled(checked: bool) -> None:
        if checked:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            action.setIcon(themed_icon_from_path(_EYE_CLOSED_ICON))
            action.setToolTip("Hide password")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            action.setIcon(themed_icon_from_path(_EYE_OPEN_ICON))
            action.setToolTip("Show password")

    action.toggled.connect(_on_toggled)
