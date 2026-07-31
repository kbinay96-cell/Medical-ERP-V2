"""
=========================================================
Medical ERP V2
Settings Cache
---------------------------------------------------------
Purpose:
    In-memory cache of all global settings. Loaded once
    (e.g. at app startup, or on first access), then every
    module reads from this cache - only Save/Refresh ever
    touch the database again.
=========================================================
"""

from utils.app_logger import get_logger
from engines.settings_validator import parse_setting_value

logger = get_logger()

_cache: dict[str, dict] = {}
_is_loaded = False


def is_loaded() -> bool:
    return _is_loaded


def load_cache(settings_rows: list[dict]) -> None:
    """
    Populates the cache from a list of setting rows (as
    returned by models.settings_model.get_all_settings()).

    Stores a shallow COPY of each row rather than the caller's
    own dict objects - update_cached_value() mutates a row's
    stored value in place, and without copying here that would
    also mutate whatever list/dict the caller passed in.
    """
    global _cache, _is_loaded

    _cache = {row["setting_key"]: dict(row) for row in settings_rows}
    _is_loaded = True
    logger.info(f"Settings cache loaded with {len(_cache)} entries.")


def get_cached_value(key: str, default=None):
    """
    Returns the setting's value already converted to its real
    Python type (int/float/bool/str), or `default` if the key
    isn't in the cache.
    """
    row = _cache.get(key)

    if row is None:
        return default

    return parse_setting_value(row["data_type"], row["setting_value"])


def get_cached_row(key: str) -> dict | None:
    return _cache.get(key)


def get_all_cached() -> dict[str, dict]:
    return dict(_cache)


def update_cached_value(key: str, new_value: str) -> None:
    """
    Updates just one cached row's value after a successful
    save, so the app doesn't need a full reload for a single
    change.
    """
    if key in _cache:
        _cache[key]["setting_value"] = new_value


def clear_cache() -> None:
    global _cache, _is_loaded
    _cache = {}
    _is_loaded = False
