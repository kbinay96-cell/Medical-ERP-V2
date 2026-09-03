"""
Standard window framing, size, and on-screen position for Master screens.

Screens/Controllers call this after setupUi(). No SQL, no business rules.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget

STANDARD_WINDOW_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.WindowSystemMenuHint
    | Qt.WindowType.WindowMinimizeButtonHint
    | Qt.WindowType.WindowMaximizeButtonHint
    | Qt.WindowType.WindowCloseButtonHint
)


def apply_standard_window_chrome(widget, *, width=1100, height=700, min_size=None,
                                  start_maximized=False, embedded=False):
    """
    embedded=True: skip window-flag/resize/center/maximize entirely -- used
    when a screen is being mounted inside the Dashboard's QStackedWidget
    instead of shown as its own top-level window. This lets every existing
    screen keep its single apply_standard_window_chrome(self, ...) call in
    __init__ unchanged; only the caller decides embedded=True/False.
    """
    if embedded:
        return
    widget.setWindowFlags(STANDARD_WINDOW_FLAGS)
    if min_size is None:
        min_size = QSize(min(720, width), min(480, height))
    widget.setMinimumSize(min_size)
    widget.resize(width, height)
    center_on_screen(widget)
    if start_maximized:
        widget.setWindowState(Qt.WindowState.WindowMaximized)


def center_on_screen(widget: QWidget) -> None:
    screen = widget.screen()
    if screen is None:
        return
    available = screen.availableGeometry()
    max_w = int(available.width() * 0.95)
    max_h = int(available.height() * 0.92)
    if widget.width() > max_w or widget.height() > max_h:
        widget.resize(min(widget.width(), max_w), min(widget.height(), max_h))
    frame = widget.frameGeometry()
    frame.moveCenter(available.center())
    widget.move(frame.topLeft())


def polish_master_window(widget: QWidget, *, width: int = 1100, height: int = 700) -> None:
    from utils.ui_standards import standardize_action_buttons

    apply_standard_window_chrome(widget, width=width, height=height)
    standardize_action_buttons(widget)


__all__ = ["STANDARD_WINDOW_FLAGS", "apply_standard_window_chrome", "center_on_screen"]
