"""
=========================================================
Medical ERP V2
Settings Engine (LOCKED - the "Brain" of the ERP)
---------------------------------------------------------
Rule: no module ever queries the `settings` database table
directly. Every module reads settings ONLY through this
Engine's get_setting(). This is what makes the whole app
Settings-driven instead of hardcoded.

Responsibilities:
    - load_all_settings   - populate the cache (call at startup)
    - get_setting          - read a value (from cache)
    - save_setting         - validate + persist + history + cache update
    - apply_setting        - instant/temporary effect, no DB write
    - reset_default        - restore one setting to its default
    - import_settings      - load a settings.json export
    - export_settings      - write a settings.json snapshot
    - refresh_cache        - force a reload from the database
=========================================================
"""

import json
from datetime import datetime

from utils.app_logger import get_logger
from models import settings_model
from engines import settings_cache
from engines.settings_validator import validate_setting_value

logger = get_logger()

# Settings that change behaviour immediately without needing an
# application restart (Blueprint-13: runtime-apply vs restart-required).
RUNTIME_APPLY_GROUPS = {"General", "Print"}
RESTART_REQUIRED_GROUPS = {"Date & Calendar", "Company"}


def load_all_settings() -> None:
    """
    Loads every global setting from the database into the
    in-memory cache. Call this once at application startup.
    Never raises - if the database is unavailable, the cache
    stays empty and get_setting() falls back to whatever
    default the caller supplies, rather than crashing the app.
    """
    try:
        rows = settings_model.get_all_settings()
        settings_cache.load_cache(rows)
    except Exception as e:
        logger.exception(f"load_all_settings: failed to load settings from database: {e}")


def refresh_cache() -> None:
    """Forces a fresh reload from the database into the cache."""
    load_all_settings()


def get_setting(key: str, default=None):
    """
    Returns a setting's value, already converted to its real
    type (int/float/bool/str). This is the ONLY way any other
    module should read a setting.
    """
    if not settings_cache.is_loaded():
        load_all_settings()

    return settings_cache.get_cached_value(key, default=default)


def get_settings_grouped() -> dict[str, list[dict]]:
    """
    Returns all cached settings grouped by category, in display
    order - what the Settings screen's category tree is built from.
    """
    if not settings_cache.is_loaded():
        load_all_settings()

    grouped: dict[str, list[dict]] = {}

    for row in settings_cache.get_all_cached().values():
        grouped.setdefault(row["setting_group"], []).append(row)

    for group_rows in grouped.values():
        group_rows.sort(key=lambda r: (r["display_order"], r["setting_key"]))

    return grouped


def search_settings(search_text: str) -> list[dict]:
    """
    Backs the Settings screen's global search box. Searches
    the database directly (not just the cache) so results are
    always current even immediately after another user's change.
    """
    try:
        return settings_model.search_settings(search_text)
    except Exception as e:
        logger.exception(f"search_settings: database error: {e}")
        return []


def save_setting(key: str, new_value: str, updated_by: str, reason: str = "") -> tuple[bool, str]:
    """
    Validates, persists to the database, writes a history
    record, and updates the cache. This is "Save" (Blueprint-11) -
    permanent, unlike apply_setting() which is temporary.
    """
    row = settings_cache.get_cached_row(key)

    if row is None:
        row = settings_model.get_setting_by_key(key)
        if row is None:
            return False, f"Setting '{key}' not found."

    is_valid, error_message = validate_setting_value(row["data_type"], new_value)
    if not is_valid:
        return False, error_message

    try:
        success, message = settings_model.update_setting_value(key, new_value, updated_by, reason)
    except Exception as e:
        logger.exception(f"save_setting: database error saving '{key}': {e}")
        return False, "Could not save setting - please try again."

    if success:
        settings_cache.update_cached_value(key, new_value)
        logger.info(f"Setting '{key}' updated by {updated_by}.")

    return success, message


def apply_setting_temporarily(key: str, new_value: str) -> tuple[bool, str]:
    """
    "Apply" (Blueprint-11): updates the cache only, for an
    instant preview/effect, WITHOUT writing to the database or
    history. A later Save (or app restart) is what makes it
    permanent; otherwise it reverts next time settings load.
    """
    row = settings_cache.get_cached_row(key)

    if row is None:
        return False, f"Setting '{key}' not found."

    is_valid, error_message = validate_setting_value(row["data_type"], new_value)
    if not is_valid:
        return False, error_message

    settings_cache.update_cached_value(key, new_value)
    return True, "Applied (not yet saved)."


def reset_setting_to_default(key: str, updated_by: str) -> tuple[bool, str]:
    try:
        success, message = settings_model.reset_setting_to_default(key, updated_by)
    except Exception as e:
        logger.exception(f"reset_setting_to_default: database error for '{key}': {e}")
        return False, "Could not reset setting - please try again."

    if success:
        row = settings_model.get_setting_by_key(key)
        if row is not None:
            settings_cache.update_cached_value(key, row["setting_value"])

    return success, message


def requires_restart(setting_group: str) -> bool:
    return setting_group in RESTART_REQUIRED_GROUPS


def export_settings(file_path: str) -> tuple[bool, str]:
    """
    Writes all current global settings to a JSON file - e.g.
    to clone a Retail Pharmacy configuration into a new
    Wholesale Pharmacy setup.
    """
    try:
        rows = settings_model.get_all_settings()
    except Exception as e:
        logger.exception(f"export_settings: database error: {e}")
        return False, "Could not read settings to export."

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "settings": [
            {
                "setting_key": row["setting_key"],
                "setting_value": row["setting_value"],
                "setting_group": row["setting_group"],
                "data_type": row["data_type"],
            }
            for row in rows
        ],
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.exception(f"export_settings: could not write file '{file_path}': {e}")
        return False, f"Could not write export file: {e}"

    return True, f"Exported {len(rows)} settings to {file_path}."


def get_setting_history(key: str) -> list[dict]:
    """
    Returns the audit trail for one setting_key, most recent
    first - backs the Settings screen's per-field "History" view.
    """
    try:
        return settings_model.get_setting_history(key)
    except Exception as e:
        logger.exception(f"get_setting_history: database error for '{key}': {e}")
        return []


def get_recent_changes(limit: int = 10) -> list[dict]:
    """
    Returns the most recent settings_history rows across every
    key - backs the Settings screen's "Recently changed" panel.
    """
    try:
        return settings_model.get_recent_history(limit)
    except Exception as e:
        logger.exception(f"get_recent_changes: database error: {e}")
        return []


def import_settings(file_path: str, updated_by: str) -> tuple[bool, str]:
    """
    Reads a settings.json file (from export_settings) and
    applies each value via save_setting() - so validation and
    history still apply to every imported value.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.exception(f"import_settings: could not read file '{file_path}': {e}")
        return False, f"Could not read import file: {e}"

    imported = 0
    skipped = 0

    for entry in data.get("settings", []):
        success, _ = save_setting(
            entry["setting_key"], entry["setting_value"], updated_by,
            reason=f"Imported from {file_path}"
        )
        if success:
            imported += 1
        else:
            skipped += 1

    return True, f"Imported {imported} settings ({skipped} skipped)."

# ---------------------------------------------------------
# Company-scoped settings (additive -- e.g. per-company SMTP).
# Global load_all_settings()/get_setting() above are untouched;
# these are separate entry points for company-specific values.
# ---------------------------------------------------------

def load_company_settings(companyid: str) -> None:
    """
    Loads one company's EFFECTIVE settings (global defaults with
    that company's own overrides applied) into the company-scoped
    cache. Call this once per login (or company switch).
    Never raises -- falls back to whatever default the caller
    supplies via get_company_setting(), same pattern as
    load_all_settings().
    """
    try:
        rows = settings_model.get_effective_settings_for_company(companyid)
        settings_cache.load_company_cache(companyid, rows)
    except Exception as e:
        logger.exception(f"load_company_settings: failed to load for '{companyid}': {e}")


def get_company_setting(companyid: str, key: str, default=None):
    """
    Returns a company-scoped setting's value (company override if
    one exists, else the global default), already converted to
    its real type. Loads the company cache automatically if it
    isn't loaded yet or belongs to a different company.
    """
    if not settings_cache.is_company_cache_loaded(companyid):
        load_company_settings(companyid)

    return settings_cache.get_company_cached_value(key, default=default)


def save_company_setting_value(
    companyid: str, key: str, new_value: str, updated_by: str, reason: str = ""
) -> tuple[bool, str]:
    """
    Validates, persists a company-specific override, writes
    history, and updates the company-scoped cache. Mirrors
    save_setting() above but scoped to one company.
    """
    row = settings_cache.get_cached_row(key) or settings_model.get_setting_by_key(key)

    if row is None:
        return False, f"Setting '{key}' not found."

    is_valid, error_message = validate_setting_value(row["data_type"], new_value)
    if not is_valid:
        return False, error_message

    try:
        success, message = settings_model.save_company_setting(
            key, new_value, companyid, updated_by, reason
        )
    except Exception as e:
        logger.exception(f"save_company_setting_value: database error saving '{key}' for '{companyid}': {e}")
        return False, "Could not save setting - please try again."

    if success:
        settings_cache.update_company_cached_value(key, new_value)
        logger.info(f"Company setting '{key}' updated for '{companyid}' by {updated_by}.")

    return success, message
