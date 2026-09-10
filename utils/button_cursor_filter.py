"""
utils/button_cursor_filter.py

App-wide QObject event filter. Install on QApplication so every
QPushButton gets a pointing-hand cursor on mouse Enter. QSS has no
`cursor` property (Qt parser: "Unknown property cursor"), so runtime
setCursor() is the only reliable mechanism. Mirrors the shape of
utils/idle_activity_filter.py.
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QPushButton


class ButtonCursorFilter(QObject):
    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Enter
            and isinstance(watched, QPushButton)
            and watched.isEnabled()
        ):
            watched.setCursor(Qt.CursorShape.PointingHandCursor)
        return super().eventFilter(watched, event)