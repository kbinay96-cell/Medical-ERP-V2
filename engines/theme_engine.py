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
from utils.button_cursor_filter import ButtonCursorFilter

logger = get_logger()

_button_cursor_filter = None


def _install_button_cursor_filter(app) -> None:
    global _button_cursor_filter
    if _button_cursor_filter is None:
        _button_cursor_filter = ButtonCursorFilter(app)
        app.installEventFilter(_button_cursor_filter)

THEME_STYLESHEETS: dict[str, str] = {
    "Light": "resources/style.qss",
    "Dark": "resources/dark_style.qss",
    "Black": "resources/dark_black.qss",
}

DEFAULT_THEME = "Light"

_current_theme = DEFAULT_THEME
_active_user_id: int | None = None


def set_active_user_id(userid: int | None) -> None:
    """Select the personal appearance override used for the active session."""
    global _active_user_id
    _active_user_id = userid


def get_current_theme() -> str:
    """Returns the name of the theme currently applied."""
    return _current_theme


def _get_control_height() -> int:
    from engines import settings_engine

    try:
        default_height = int(settings_engine.get_setting("ui.control_height", 28))
        height = (
            int(settings_engine.get_user_setting(_active_user_id, "ui.control_height", default_height))
            if _active_user_id is not None else default_height
        )
    except (TypeError, ValueError):
        height = 28
    return max(26, min(height, 48))


def apply_control_density() -> None:
    app = QApplication.instance()
    if app is None:
        return
    from utils.ui_standards import apply_application_density

    apply_application_density(app, _get_control_height())


def _build_dynamic_overrides() -> str:
    """Build a QSS override block for user-adjustable appearance settings."""
    from engines import settings_engine

    height = _get_control_height()
    try:
        font_size = float(settings_engine.get_setting("ui.font_size", 10.5))
    except (TypeError, ValueError):
        font_size = 10.5
    font_family = settings_engine.get_setting("ui.font_family", "Segoe UI") or "Segoe UI"
    widget_height = max(height - 2, 0)

    return f"""
/* ---------- Dynamic appearance overrides (ui.* settings) ---------- */
* {{
    font-family: "{font_family}";
    font-size: {font_size}pt;
}}
QPushButton[uiDensityButton="true"] {{
    min-height: {widget_height}px;
    max-height: {widget_height}px;
    padding: 2px 6px;
}}
QPushButton[uiButtonWidth="144"] {{
    min-width: 144px;
    max-width: 144px;
}}
QPushButton[uiButtonWidth="84"] {{
    min-width: 84px;
    max-width: 84px;
    padding: 1px 3px;
}}
QPushButton[uiButtonWidth="32"] {{
    min-width: 32px;
    max-width: 32px;
    padding: 0;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {{
    min-height: {widget_height}px;
    max-height: {widget_height}px;
    padding: 2px 6px;
}}
QPlainTextEdit, QTextEdit {{
    min-height: {widget_height}px;
    padding: 2px 6px;
}}
QHeaderView::section {{
    min-height: {widget_height}px;
    padding: 0px 6px;
}}
QTableView::item {{
    padding: 2px 5px;
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
        apply_control_density()
        _current_theme = theme_name
        _install_button_cursor_filter(app)
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
