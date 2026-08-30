# engines/purchase_return_engine.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_return_model import PurchaseReturnModel

logger = logging.getLogger(__name__)


class PurchaseReturnEngine:
    """Phase-2 — build only after Purchase Invoice/Order are live and
    tested. Reuses ItemEngine.post_stock_movement(), which is ALREADY
    built for exactly this future case (see its docstring in
    item_engine.py: 'negative = stock OUT ... a Purchase Return')."""

    def __init__(self, model: PurchaseReturnModel, date_engine, item_engine) -> None:
        self._model = model
        self._date_engine = date_engine
        self._item_engine = item_engine

    def create_return(self, payload: dict[str, Any], current_user_id: int) -> dict:
        """Validates basic payload shape, then calls
        self._item_engine.post_stock_movement(item_batch_id,
        transaction_type='PURCHASE_RETURN', quantity_change=-return_qty, ...)
        -- reuses ItemEngine.post_stock_movement(), which is ALREADY built
        for exactly this future case (see its docstring in item_engine.py:
        'negative = stock OUT ... a Purchase Return'). post_stock_movement()
        itself rejects any movement that would take the batch below zero,
        so the remaining-quantity check does not need to be duplicated
        here — ItemEngine has no single-batch getter exposed for that
        anyway (only get_batches(item_id), a list, and post_stock_movement
        internally)."""
        from engines.date_engine import ad_to_bs, DateEngineError  # noqa: F401

        item_batch_id = payload.get("item_batch_id")
        if not item_batch_id:
            raise ValidationError("item_batch_id is required.")

        return_qty = payload.get("return_qty")
        try:
            return_qty = float(return_qty)
        except (TypeError, ValueError):
            raise ValidationError("return_qty is required and must be numeric.")

        if return_qty <= 0:
            raise ValidationError("return_qty must be greater than zero.")

        reason = payload.get("reason")
        if not reason or not str(reason).strip():
            raise ValidationError("A return reason is required.")

        now_ad = datetime.now(timezone.utc)
        try:
            now_bs = ad_to_bs(now_ad.date())
        except DateEngineError:
            logger.exception("Could not resolve BS date for purchase return audit stamp")
            now_bs = None

        purchase_return_id = self._model.insert_return(
            {
                "item_batch_id": item_batch_id,
                "return_qty": return_qty,
                "reason": reason,
                "purchase_invoice_id": payload.get("purchase_invoice_id"),
                "created_by": current_user_id,
                "created_at_ad": now_ad,
                "created_at_bs": now_bs,
            }
        )

        # post_stock_movement() raises ValidationError itself if this
        # return would take the batch below zero — no pre-check needed.
        self._item_engine.post_stock_movement(
            item_batch_id=item_batch_id,
            transaction_type="PURCHASE_RETURN",
            quantity_change=-return_qty,
            current_user_id=current_user_id,
            reference_type="purchase_return",
            reference_id=purchase_return_id,
            remarks=reason,
        )

        return {
            "purchase_return_id": purchase_return_id,
            "item_batch_id": item_batch_id,
            "return_qty": return_qty,
            "reason": reason,
        }