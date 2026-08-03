"""
engines/item_lookup_registry.py

Item Lookup Registry - Medical ERP V2

Single wiring point for every lookup Item Master depends on. Screens and
ItemEngine both import FROM HERE, never directly from
engines/simple_master_engine.py or engines/manufacturer_engine.py -- that's
what lets this one file be the only place that needs editing if either of
those ever changes shape.

MANUFACTURER NOTE: ManufacturerEngine has its OWN API shape, different
from SimpleMasterEngine (it is NOT a MasterTableConfig-based engine) --
confirmed by reading the real engines/manufacturer_engine.py:
    - get_manufacturer(id, include_deleted=False) -> ManufacturerDTO   (not .get())
    - search_manufacturers(search_text=None, status=None, country=None,
      include_deleted=False, page=1, page_size=50) -> (list[DTO], total)
      (no list_active() method)
    - ManufacturerDTO fields: manufacturer_id, manufacturer_code,
      manufacturer_name, manufacturer_short_name, country, status,
      is_deleted, ... (NOT .id / .code / .name like MasterDTO)
Because of this shape difference, ManufacturerEngine is NOT a drop-in
replacement inside screens/master_manage_screen.MasterManageDialog (which
expects a SimpleMasterEngine + MasterDTO). Manufacturer already has its own
dedicated screens (ManufacturerListScreen / ManufacturerFormScreen, already
wired on the Dashboard sidebar) -- the Item Form's "Manage..." button for
Manufacturer opens THAT screen instead of MasterManageDialog.
"""

from __future__ import annotations

import logging
from typing import Optional

from engines.manufacturer_engine import ManufacturerEngine
from engines.simple_master_engine import (
    SimpleMasterEngine,
    category_engine,
    generic_engine,
    item_group_engine,
    sub_category_engine,
    unit_engine,
)

logger = logging.getLogger(__name__)

__all__ = [
    "category_engine",
    "sub_category_engine",
    "item_group_engine",
    "unit_engine",
    "generic_engine",
    "manufacturer_engine",
    "country_tax_lookup",
    "manufacturer_lookup",
]


# ------------------------------------------------------------------ #
# MANUFACTURER -- now wired to the real, migrated module.
# ------------------------------------------------------------------ #
def manufacturer_engine() -> ManufacturerEngine:
    return ManufacturerEngine()


def manufacturer_lookup(manufacturer_id: Optional[int]) -> Optional[dict]:
    """
    Used by ItemEngine.resolve_item_tax() to fetch a Manufacturer's
    `country` for country_default tax mode. Never raises -- returns None
    for "not selected" or "not found", and ItemEngine._resolve_tax_for_row()
    already treats a None/missing country as (0, 0).
    """
    if manufacturer_id is None:
        return None
    try:
        dto = manufacturer_engine().get_manufacturer(manufacturer_id)
        return {"country": dto.country}
    except Exception:  # noqa: BLE001 -- must never break Item save/resolve
        logger.exception("manufacturer_lookup: could not resolve manufacturer_id=%s.", manufacturer_id)
        return None


# ------------------------------------------------------------------ #
# COUNTRY TAX SETTINGS -- PLACEHOLDER until the Settings module's
# Country Tax table/engine (country_name, vat_percent, custom_percent)
# is built.
# ------------------------------------------------------------------ #
def country_tax_lookup(country: str) -> tuple[float, float]:
    """
    TODO: once the Country Tax Settings engine exists, replace this
    function's body with a real lookup, e.g.:

        from engines.country_tax_engine import get_country_tax
        return get_country_tax(country)

    Until then, ALWAYS returns (0, 0) -- exactly the blueprint's rule for
    an unconfigured/unknown/missing country. Never raises.
    """
    logger.info("country_tax_lookup: Country Tax Settings not configured yet; '%s' defaults to (0, 0).", country)
    return 0.0, 0.0
