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


def get_current_theme() -> str:
    """Returns the name of the theme currently applied."""
    return _current_theme


def _build_dynamic_overrides() -> str:
    """Builds a QSS override block from user-adjustable appearance
    settings (ui.control_height, ui.font_size, ui.font_family), applied
    on top of the base theme stylesheet so it always wins the cascade.
    Local import avoids any risk of circular imports at startup."""
    from engines import settings_engine

    try:
        height = int(settings_engine.get_setting("ui.control_height", 34))
    except (TypeError, ValueError):
        height = 34
    try:
        font_size = float(settings_engine.get_setting("ui.font_size", 10.5))
    except (TypeError, ValueError):
        font_size = 10.5
    font_family = settings_engine.get_setting("ui.font_family", "Segoe UI") or "Segoe UI"

    return f"""
/* ---------- Dynamic appearance overrides (ui.* settings) ---------- */
* {{
    font-family: "{font_family}";
    font-size: {font_size}pt;
}}
QPushButton[cssClass="actionButton"] {{
    min-height: {height}px;
}}
QTreeWidget#treeSidebarMenu::item {{
    padding: {max(height - 22, 4)}px 4px;
}}
"""


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
            base_qss = f.read()
        app.setStyleSheet(base_qss + _build_dynamic_overrides())
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

def get_available_themes() -> list[str]:
    """
    Returns the list of valid theme names, in display order.
    Used by the Settings screen to build the theme selector.
    """
    return list(THEME_STYLESHEETS.keys())
