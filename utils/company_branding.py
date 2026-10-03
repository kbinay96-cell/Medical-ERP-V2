"""Shared company-logo rendering for Login and Dashboard."""

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from utils.app_logger import get_logger
from utils.icon_utils import themed_icon

logger = get_logger()
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def set_company_logo(label: QLabel, logo_path: str | None, size: QSize) -> None:
    """Show a company logo scaled proportionally, with a branded fallback."""
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(size)
    pixmap = QPixmap()

    if logo_path:
        path = Path(logo_path).expanduser()
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        if not pixmap.load(str(path)):
            logger.warning("Company logo could not be loaded from '%s'.", path)
    else:
        logger.info("No company logo path is configured; showing the company icon.")

    if pixmap.isNull():
        pixmap = themed_icon("building").pixmap(size)
        label.setToolTip("Company logo is not configured or could not be loaded.")
    else:
        pixmap = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setToolTip("Company logo")

    label.setPixmap(pixmap)
    label.setText("")
