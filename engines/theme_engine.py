"""
=========================================================
Medical ERP V2
Theme Engine
---------------------------------------------------------
Loads/toggles the application-wide QSS stylesheet.
=========================================================
"""

from PySide6.QtWidgets import QApplication

from utils.app_logger import get_logger

logger = get_logger()

LIGHT_STYLESHEET_PATH = "resources/style.qss"
DARK_STYLESHEET_PATH = "resources/dark_style.qss"

_current_theme = "Light"


def apply_theme(theme_name: str) -> None:
    global _current_theme

    path = DARK_STYLESHEET_PATH if theme_name == "Dark" else LIGHT_STYLESHEET_PATH

    app = QApplication.instance()
    if app is None:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        _current_theme = theme_name
    except FileNotFoundError as e:
        logger.warning(f"apply_theme: stylesheet '{path}' not found: {e}")


def toggle_theme() -> str:
    """
    Switches between Light and Dark. Returns the new theme name.
    """
    new_theme = "Dark" if _current_theme == "Light" else "Light"
    apply_theme(new_theme)
    return new_theme


def get_current_theme() -> str:
    return _current_theme
