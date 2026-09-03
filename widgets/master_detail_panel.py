"""
Right-side read-only detail card used by Customer/Item/Supplier/User lists.
"""

from __future__ import annotations
from utils.icon_utils import themed_icon_from_path
from typing import Optional, Sequence

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

DETAIL_PHOTO_SIZE = 120
DETAIL_PHOTO_SIZE_WIDE = 360
ICON_DIR = "resources/icons"


class MasterDetailPanel(QScrollArea):
    def __init__(
        self,
        *,
        placeholder_title: str,
        placeholder_icon: str = "user.svg",
        field_captions: Sequence[str],
        wide: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._placeholder_title = placeholder_title
        self._placeholder_icon = f"{ICON_DIR}/{placeholder_icon}"
        self._value_labels: dict[str, QLabel] = {}
        self._wide = wide

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        if not wide:
            # Compact side-panel mode (Supplier/User lists, and Item's own
            # non-embedded/splitter mode) keeps its original narrow caps.
            self.setMinimumWidth(260)
            self.setMaximumWidth(360)

        panel = QWidget()

        photo_size = DETAIL_PHOTO_SIZE_WIDE if wide else DETAIL_PHOTO_SIZE
        self.lbl_photo = QLabel()
        self.lbl_photo.setFixedSize(QSize(photo_size, photo_size))
        self.lbl_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_title = QLabel(placeholder_title)
        self.lbl_title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self.lbl_title.setWordWrap(True)

        self.lbl_subtitle = QLabel("")
        self.lbl_subtitle.setStyleSheet("color: #7A8599;")

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)

        if wide:
            # Wide/full-screen mode (embedded Item detail): fields on the
            # left, a bigger photo on the right instead of photo-on-top --
            # everything fits without scrolling at this size.
            root_layout = QHBoxLayout(panel)
            root_layout.setContentsMargins(16, 16, 16, 16)
            root_layout.setSpacing(24)

            left_col = QVBoxLayout()
            left_col.setSpacing(6)
            left_col.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
            left_col.addWidget(self.lbl_title)
            left_col.addWidget(self.lbl_subtitle)
            left_col.addWidget(divider)
            for caption in field_captions:
                self._value_labels[caption] = self._field_row(left_col, caption)
            left_col.addStretch(1)

            root_layout.addLayout(left_col, 1)
            root_layout.addWidget(self.lbl_photo, 0, Qt.AlignmentFlag.AlignVCenter)
            root_layout.addSpacing(220)  # ~8cm at standard 96 DPI, shifts photo left from the right edge
        else:
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(6)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(self.lbl_photo, 0, Qt.AlignmentFlag.AlignHCenter)
            self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(self.lbl_title)
            layout.addWidget(self.lbl_subtitle)
            layout.addWidget(divider)
            for caption in field_captions:
                self._value_labels[caption] = self._field_row(layout, caption)
            layout.addStretch(1)

        self.setWidget(panel)
        self.show_placeholder()

    @staticmethod
    def _field_row(parent_layout: QVBoxLayout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(6)
        caption = QLabel(label_text)
        caption.setStyleSheet("color: #7A8599; font-weight: 600;")
        caption.setFixedWidth(96)
        row.addWidget(caption)
        value_label = QLabel("-")
        value_label.setWordWrap(True)
        row.addWidget(value_label, 1)
        parent_layout.addLayout(row)
        return value_label

    def show_placeholder(self) -> None:
        self.lbl_photo.setPixmap(themed_icon_from_path(self._placeholder_icon).pixmap(QSize(48, 48)))
        self.lbl_title.setText(self._placeholder_title)
        self.lbl_subtitle.setText("")
        for label in self._value_labels.values():
            label.setText("-")

    def set_photo(self, photo_path: Optional[str]) -> None:
        size = DETAIL_PHOTO_SIZE_WIDE if self._wide else DETAIL_PHOTO_SIZE
        pixmap = QPixmap(photo_path) if photo_path else None
        if pixmap and not pixmap.isNull():
            self.lbl_photo.setPixmap(
                pixmap.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.lbl_photo.setPixmap(QIcon(self._placeholder_icon).pixmap(QSize(48, 48)))

    def set_heading(self, title: str, subtitle: str = "") -> None:
        self.lbl_title.setText(title or "-")
        self.lbl_subtitle.setText(subtitle or "")

    def set_field(self, caption: str, value: str) -> None:
        label = self._value_labels.get(caption)
        if label is not None:
            label.setText(value or "-")

    @staticmethod
    def format_audit(by, at_bs, at_ad) -> str:
        if not by and not at_bs and not at_ad:
            return "-"
        when = at_bs or (at_ad.strftime("%Y-%m-%d %H:%M") if at_ad else "")
        who = str(by) if by else "-"
        return f"{who}\n{when}" if when else who


__all__ = ["MasterDetailPanel", "DETAIL_PHOTO_SIZE"]
