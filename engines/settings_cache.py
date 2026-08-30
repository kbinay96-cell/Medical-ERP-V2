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

# ---------------------------------------------------------
# Company-scoped cache (additive -- separate from the global
# _cache above, which stays untouched for General/Print/etc).
# Single active company at a time, matching this desktop app's
# single in-memory session model.
# ---------------------------------------------------------

_company_cache: dict[str, dict] = {}
_company_cache_id: str | None = None


def is_company_cache_loaded(companyid: str) -> bool:
    return _company_cache_id == companyid and bool(_company_cache)


def load_company_cache(companyid: str, settings_rows: list[dict]) -> None:
    """Populates the company-scoped cache with a company's EFFECTIVE
    settings (global + that company's overrides already merged by
    the caller, e.g. settings_model.get_effective_settings_for_company()).
    Replaces any previously cached company (single active company)."""
    global _company_cache, _company_cache_id

    _company_cache = {row["setting_key"]: dict(row) for row in settings_rows}
    _company_cache_id = companyid
    logger.info(f"Company settings cache loaded for '{companyid}' with {len(_company_cache)} entries.")


def get_company_cached_value(key: str, default=None):
    row = _company_cache.get(key)

    if row is None:
        return default

    return parse_setting_value(row["data_type"], row["setting_value"])


def update_company_cached_value(key: str, new_value: str) -> None:
    if key in _company_cache:
        _company_cache[key]["setting_value"] = new_value


def clear_company_cache() -> None:
    global _company_cache, _company_cache_id
    _company_cache = {}
    _company_cache_id = None
