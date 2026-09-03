"""
Icon theming utility.

resources/icons/*.svg use stroke="currentColor" intending to tint with
the active theme, but Qt's SVG renderer never resolves currentColor from
any stylesheet on its own -- icons built via plain QIcon(path) always
render in the SVG's literal default (black), in every theme.

Use themed_icon()/themed_icon_from_path() instead of QIcon(...) anywhere
an icon from resources/icons/ is loaded, so it picks up the active
theme's actual color.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from engines.theme_engine import get_current_theme

ICON_DIR = "resources/icons"

ICON_COLORS: dict[str, str] = {
    "Light": "#1B2430",
    "Dark": "#E6EDF7",
    "Black": "#E8E8ED",
}

DEFAULT_ICON_COLOR = "#1B2430"


def _render_tinted(svg_path: str, color: str | None, base_size: int) -> QPixmap:
    tint = color or ICON_COLORS.get(get_current_theme(), DEFAULT_ICON_COLOR)
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_text = f.read()
    svg_bytes = QByteArray(svg_text.replace("currentColor", tint).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def themed_icon(name: str, color: str | None = None, base_size: int = 64) -> QIcon:
    """For bare icon names under resources/icons/, e.g. themed_icon("plus")."""
    return QIcon(_render_tinted(f"{ICON_DIR}/{name}.svg", color, base_size))


def themed_icon_from_path(svg_path: str, color: str | None = None, base_size: int = 64) -> QIcon:
    """For call sites that already hold a full/relative svg path string/constant."""
    return QIcon(_render_tinted(svg_path, color, base_size))