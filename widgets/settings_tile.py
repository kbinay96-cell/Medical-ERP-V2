"""
=========================================================
Medical ERP V2
Settings Tile Widget
---------------------------------------------------------
A single clickable "card" representing one Settings group
on the landing page - icon, group name, tagline, live count
of settings in that group, and a restart-required badge
when applicable. Visual language borrows the rounded-card,
dark-surface feel of the reference design, restyled with
this app's own accent colours (resources/style.qss /
dark_style.qss) rather than copying it verbatim.

No SQL, no engine calls here - purely a display component
fed by whatever the Settings Screen already loaded.
=========================================================
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from utils.settings_ui_helpers import group_icon_name, group_tagline

ICON_DIR = "resources/icons"


class SettingsTile(QFrame):
    """Emits `clicked(setting_group)` when the card is activated."""

    clicked = Signal(str)

    def __init__(self, setting_group: str, item_count: int, requires_restart: bool, parent=None):
        super().__init__(parent)

        self.setting_group = setting_group

        self.setObjectName(f"tile_{setting_group}")
        self.setProperty("cssClass", "settingsTile")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumSize(QSize(220, 140))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui(item_count, requires_restart)

    def _build_ui(self, item_count: int, requires_restart: bool):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setProperty("cssClass", "tileIcon")
        icon_label.setFixedSize(QSize(40, 40))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_name = group_icon_name(self.setting_group)
        icon_label.setPixmap(QIcon(f"{ICON_DIR}/{icon_name}.svg").pixmap(QSize(20, 20)))
        top_row.addWidget(icon_label)
        top_row.addStretch(1)

        if requires_restart:
            restart_badge = QLabel("Restart")
            restart_badge.setProperty("cssClass", "tileRestartBadge")
            restart_badge.setToolTip("Changes in this group take effect after restarting the app.")
            top_row.addWidget(restart_badge, 0, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(top_row)

        title_label = QLabel(self.setting_group)
        title_label.setProperty("cssClass", "tileTitle")
        title_label.setWordWrap(True)
        outer.addWidget(title_label)

        subtitle_label = QLabel(group_tagline(self.setting_group))
        subtitle_label.setProperty("cssClass", "tileSubtitle")
        subtitle_label.setWordWrap(True)
        outer.addWidget(subtitle_label)

        outer.addStretch(1)

        count_row = QHBoxLayout()
        count_badge = QLabel(f"{item_count} setting{'s' if item_count != 1 else ''}")
        count_badge.setProperty("cssClass", "tileBadge")
        count_row.addWidget(count_badge)
        count_row.addStretch(1)
        outer.addLayout(count_row)

    def update_count(self, item_count: int):
        """Called after a save/import so the tile reflects the live count."""
        for label in self.findChildren(QLabel):
            if label.property("cssClass") == "tileBadge":
                label.setText(f"{item_count} setting{'s' if item_count != 1 else ''}")
                return

    # -----------------------------------------------------
    # Interaction - clickable + keyboard activatable
    # -----------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.setting_group)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.setting_group)
        else:
            super().keyPressEvent(event)
