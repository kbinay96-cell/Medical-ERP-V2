# engines/purchase_return_engine.py
from __future__ import annotations
from typing import Any

from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_return_model import PurchaseReturnModel

logger = __import__("logging").getLogger(__name__)


class PurchaseReturnEngine:
    def __init__(self, model: PurchaseReturnModel, date_engine, item_engine) -> None:
        self._model = model
        self._date_engine = date_engine
        self._item_engine = item_engine

    def _now_ad(self):
        from datetime import datetime
        return datetime.now()

    def _now_bs(self):
        try:
            return self._date_engine.ad_to_bs(self._now_ad().date())
        except Exception:
            return ""

    def create_return(self, payload: dict[str, Any], current_user_id: int) -> dict:
        """
        payload must include:
          - purchase_invoice_id
          - supplier_id
          - lines: [{ item_batch_id, return_qty, return_rate, remarks }]
        Validates return_qty <= current batch current balance (caller must ensure),
        inserts return header and items, and calls ItemEngine.post_stock_movement()
        to record the negative stock movement atomically with ledger.
        """
        if not payload or not payload.get("lines"):
            raise ValidationError(["Return payload missing or no lines provided."])

        # Phase-2: Minimal checks, then call ItemEngine.post_stock_movement for each line.
        return_id = self._model.insert_return({
            "purchase_invoice_id": payload.get("purchase_invoice_id"),
            "supplier_id": payload.get("supplier_id"),
            "return_date_ad": payload.get("return_date_ad") or self._now_ad().date(),
            "return_date_bs": payload.get("return_date_bs") or self._now_bs(),
            "total_amount": payload.get("total_amount") or 0,
            "reason": payload.get("reason"),
            "created_by": current_user_id,
            "created_at_ad": self._now_ad(),
            "created_at_bs": self._now_bs(),
        })

        for line in payload.get("lines", []):
            item_batch_id = line.get("item_batch_id")
            return_qty = float(line.get("return_qty") or 0)
            if return_qty <= 0:
                raise ValidationError(["return_qty must be > 0"])
            # Insert return item
            item_line_data = {
                "purchase_return_id": return_id,
                "item_batch_id": item_batch_id,
                "return_qty": return_qty,
                "return_rate": line.get("return_rate") or 0,
                "remarks": line.get("remarks"),
            }
            rid = self._model.insert_return_item(return_id, item_line_data)
            # Now call ItemEngine.post_stock_movement() to effect the stock change
            try:
                self._item_engine.post_stock_movement(
                    item_batch_id=item_batch_id,
                    transaction_type="PURCHASE_RETURN",
                    quantity_change=-abs(return_qty),
                    current_user_id=current_user_id,
                    reference_type="purchase_return",
                    reference_id=return_id,
                    remarks=line.get("remarks"),
                )
            except Exception:
                logger.exception("Failed to post stock movement for return line (item_batch_id=%s)", item_batch_id)
                # Do not attempt automatic compensation here; surface error to caller if desired.
                raise

        return {"purchase_return_id": return_id}