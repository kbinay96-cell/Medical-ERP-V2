# engines/item_free_scheme_engine.py
from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Tuple

from models.item_free_scheme_model import ItemFreeSchemeModel

logger = logging.getLogger(__name__)


def _load_date_engine():
    try:
        from engines import date_engine
        return date_engine
    except ImportError:
        logger.warning(
            "engines.date_engine not importable; ItemFreeSchemeEngine will leave "
            "updated_at_bs blank until the Date Engine is wired in."
        )
        return None


class ItemFreeSchemeEngine:
    """Business-rule orchestration for the item+supplier 'free scheme'
    memory (e.g. '10+1'). Never raises -- a missing or broken scheme just
    means no auto-suggestion is offered, it must never block Purchase (or
    future Sale) entry. Reusable as-is by the future Sale module, since
    the scheme belongs to the item+supplier pair, not to any one
    transaction or module."""

    def __init__(self, model: Optional[ItemFreeSchemeModel] = None, date_engine=None) -> None:
        self._model = model or ItemFreeSchemeModel()
        self._date_engine = date_engine if date_engine is not None else _load_date_engine()

    def _now_bs(self) -> Optional[str]:
        if self._date_engine is None:
            return None
        try:
            return self._date_engine.ad_to_bs(date.today())
        except self._date_engine.DateEngineError:
            return None

    def get_scheme(self, item_id: int, supplier_id: int) -> Optional[Tuple[float, float]]:
        """Returns (scheme_qty, scheme_free_qty) for this item+supplier
        pair, or None if nothing is stored yet. Never raises."""
        try:
            row = self._model.get_by_item_supplier(item_id, supplier_id)
        except Exception:
            logger.exception(
                "get_scheme: failed to resolve for item_id=%s supplier_id=%s", item_id, supplier_id
            )
            return None
        if row is None:
            return None
        return float(row["scheme_qty"]), float(row["scheme_free_qty"])

    def suggest_free_qty(self, item_id: int, supplier_id: int, qty: float) -> float:
        """Scales the stored scheme ratio to the given qty (e.g. a stored
        10+1 scheme with qty=25 suggests free_qty = round(25/10 * 1) = 3).
        Returns 0.0 if no scheme is stored, or qty <= 0. This is always a
        suggestion -- the Screen must leave it fully editable."""
        scheme = self.get_scheme(item_id, supplier_id)
        if not scheme or qty <= 0:
            return 0.0
        scheme_qty, scheme_free_qty = scheme
        if scheme_qty <= 0:
            return 0.0
        return round((qty / scheme_qty) * scheme_free_qty)

    def save_scheme(
        self, item_id: int, supplier_id: int, qty: float, free_qty: float, current_user_id: int
    ) -> None:
        """Overwrites the stored scheme for this item+supplier pair with
        whatever ratio was actually used on this invoice line, so the
        next entry suggests the latest known deal. Called unconditionally
        on every save (whether the user kept the suggestion or overrode
        it) -- an unchanged ratio just re-saves the same values. Never
        raises -- a failed save must never block the invoice itself."""
        if qty <= 0:
            return
        try:
            self._model.upsert(item_id, supplier_id, qty, free_qty, current_user_id, self._now_bs())
        except Exception:
            logger.exception(
                "save_scheme: failed to save for item_id=%s supplier_id=%s", item_id, supplier_id
            )


__all__ = ["ItemFreeSchemeEngine"]