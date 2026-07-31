"""
=========================================================
Medical ERP V2
Theme Engine
---------------------------------------------------------
Loads/toggles the application-wide QSS stylesheet.

Supported themes: Light, Dark (Blue accent), Black (violet
accent, near-black background). "Dark" is kept as the name
for the Blue theme for backward compatibility with existing
saved settings and callers.
=========================================================
"""
from PySide6.QtWidgets import QApplication

from utils.app_logger import get_logger

logger = get_logger()

THEME_STYLESHEETS: dict[str, str] = {
    "Light": "resources/style.qss",
    "Dark": "resources/dark_style.qss",
    "Black": "resources/dark_black.qss",
}

DEFAULT_THEME = "Light"

_current_theme = DEFAULT_THEME


def apply_theme(theme_name: str) -> None:
    """
    Applies the given theme's stylesheet to the running QApplication.

    Falls back to the Light theme if theme_name is not recognized,
    or if the stylesheet file cannot be found/read.
    """
    global _current_theme

    if theme_name not in THEME_STYLESHEETS:
        logger.warning(
            f"apply_theme: unknown theme '{theme_name}', falling back to "
            f"'{DEFAULT_THEME}'."
        )
        theme_name = DEFAULT_THEME

    path = THEME_STYLESHEETS[theme_name]
    app = QApplication.instance()
    if app is None:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        _current_theme = theme_name
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"apply_theme: stylesheet '{path}' not found: {e}")


def toggle_theme() -> str:
    """
    Cycles through the available themes in order: Light -> Dark -> Black
    -> Light. Returns the new theme name.
    """
    theme_order = list(THEME_STYLESHEETS.keys())
    try:
        current_index = theme_order.index(_current_theme)
    except ValueError:
        current_index = -1
    next_theme = theme_order[(current_index + 1) % len(theme_order)]
    apply_theme(next_theme)
    return next_theme


def get_current_theme() -> str:
    return _current_theme


def get_available_themes() -> list[str]:
    """
    Returns the list of valid theme names, in display order.
    Used by the Settings screen to build the theme selector.
    """
    return list(THEME_STYLESHEETS.keys())
