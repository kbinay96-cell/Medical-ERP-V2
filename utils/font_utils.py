"""Registers bundled font files with QFontDatabase so families in
resources/fonts/ are available for QSS font-family rules, without
relying on the font being installed on the host OS."""

from PySide6.QtGui import QFontDatabase

from utils.app_logger import get_logger

logger = get_logger()

FONT_DIR = "resources/fonts"

BUNDLED_FONTS = [
    f"{FONT_DIR}/OpenSans-Regular.ttf",
    f"{FONT_DIR}/OpenSans-SemiBold.ttf",
    f"{FONT_DIR}/NotoSans-Regular.ttf",
    f"{FONT_DIR}/Roboto-Regular.ttf",
]


def load_application_fonts() -> None:
    """Registers all bundled TTFs with QFontDatabase. Call once at
    startup, before apply_theme(), so QSS font-family rules can resolve
    the bundled families immediately."""
    for path in BUNDLED_FONTS:
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id == -1:
            logger.warning(f"load_application_fonts: failed to load '{path}'.")