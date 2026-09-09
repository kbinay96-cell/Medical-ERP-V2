"""
=========================================================
Medical ERP V2
Idle Activity Filter
---------------------------------------------------------
App-wide QObject event filter. Install on QApplication so
it sees every mouse/keyboard event across all screens, and
forwards each interaction to session_manager.record_activity().

No UI code here, no business rules - pure event plumbing.
=========================================================
"""

from PySide6.QtCore import QObject, QEvent
from engines import session_manager


class IdleActivityFilter(QObject):

    _ACTIVITY_EVENT_TYPES = (
        QEvent.MouseButtonPress,
        QEvent.MouseMove,
        QEvent.KeyPress,
        QEvent.Wheel,
    )

    def eventFilter(self, watched, event):
        if event.type() in self._ACTIVITY_EVENT_TYPES:
            session_manager.record_activity()
        return super().eventFilter(watched, event)