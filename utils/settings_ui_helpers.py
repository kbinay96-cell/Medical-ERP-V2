"""
=========================================================
Medical ERP V2
Settings UI Helpers
---------------------------------------------------------
Purpose:
    Pure, Qt-free logic used by the Settings Screen and its
    widgets (widgets/settings_tile.py, widgets/settings_field_row.py).
    Kept separate from any PySide6 import so it can be unit
    tested directly, the same way engines/date_engine.py
    separates its pure-logic functions from Qt.

    Nothing here touches the database or the Settings Engine -
    it only transforms strings that are already in hand.
=========================================================
"""

# Icon files that ship in resources/icons/ - see ICONS_README.txt.
_GROUP_ICONS = {
    "General": "settings",
    "Date & Calendar": "calendar",
    "Company": "building",
    "User & Security": "lock",
    "Print": "report",
    "Backup": "backup",
}
_DEFAULT_GROUP_ICON = "list"

# Short, one-line taglines shown under each group's tile title.
# UI copy only - not settings data - so this is not a "fake data"
# violation; the settings themselves always come from the DB.
_GROUP_TAGLINES = {
    "General": "App name, language, theme & currency",
    "Date & Calendar": "BS/AD calendar and fiscal year rules",
    "Company": "Company identity used on prints & reports",
    "User & Security": "Login, lockout, session & password rules",
    "Print": "Paper size, copies & print branding",
    "Backup": "Automatic database backup schedule",
}
_DEFAULT_GROUP_TAGLINE = "Application preferences"


def group_icon_name(setting_group: str) -> str:
    """Returns the icon filename stem (no extension) for a group."""
    return _GROUP_ICONS.get(setting_group, _DEFAULT_GROUP_ICON)


def group_tagline(setting_group: str) -> str:
    """Returns a short descriptive line for a group's tile."""
    return _GROUP_TAGLINES.get(setting_group, _DEFAULT_GROUP_TAGLINE)


def humanize_setting_key(setting_key: str) -> str:
    """
    Turns a dotted setting_key into a human-readable label,
    e.g. "security.max_login_attempts" -> "Max Login Attempts".
    Falls back to the raw key if it has no '.' segment.
    """
    if not setting_key:
        return ""

    tail = setting_key.split(".")[-1]
    words = tail.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words) if words else tail


def parse_enum_options(description: str) -> list[str] | None:
    """
    Some setting descriptions document their valid values as a
    pipe-separated list, e.g. "Retail | Wholesale | Hospital" or
    "Light | Dark". When that pattern is present, return the
    parsed options so the UI can render a dropdown instead of a
    free-text box - WITHOUT hardcoding per-key option lists.

    Returns None when no such pattern is found (plain free text).
    """
    if not description or " | " not in description:
        return None

    # Some descriptions have trailing prose after the option list,
    # separated by " - " (e.g. "BS (primary) or AD (secondary) -
    # BS-first is LOCKED..." - that one has no " | " so it never
    # reaches here anyway, but guard the general case too).
    candidate = description.split(" - ")[0].strip()

    if " | " not in candidate:
        return None

    options = [part.strip() for part in candidate.split("|")]
    options = [opt for opt in options if opt]

    if 2 <= len(options) <= 10 and all(len(opt) <= 30 for opt in options):
        return options

    return None


def is_file_path_setting(setting_key: str, description: str) -> bool:
    """
    For data_type == "path": decide whether this points at a
    single FILE (e.g. a logo image - use a file-open dialog) or
    a FOLDER (e.g. a backup destination - use a folder dialog).
    """
    text = f"{setting_key} {description or ''}".lower()
    file_hints = ("logo", "image", "photo", "picture", "file")
    return any(hint in text for hint in file_hints)


def is_image_path_setting(setting_key: str, description: str) -> bool:
    """Narrower check used to decide the file dialog's filter."""
    text = f"{setting_key} {description or ''}".lower()
    return any(hint in text for hint in ("logo", "image", "photo", "picture"))
