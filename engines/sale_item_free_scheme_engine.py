# engines/sale_item_free_scheme_engine.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, EngineError, RecordNotFoundError, ValidationError
from engines.sale_validator import ItemFreeSchemeValidator
from models.sale_item_free_scheme_model import SaleItemFreeSchemeModel, SaleItemFreeSchemeSearchFilters

logger = logging.getLogger(__name__)


@dataclass
class ItemFreeSchemeDTO:
    sale_item_free_scheme_id: Optional[int]
    item_id: int
    item_name: str
    item_code: str
    scheme_qty: float
    scheme_free: float
    is_active: bool
    remarks: Optional[str]

    def to_dict(self) -> dict:
        return {
            "sale_item_free_scheme_id": self.sale_item_free_scheme_id,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "item_code": self.item_code,
            "scheme_qty": self.scheme_qty,
            "scheme_free": self.scheme_free,
            "is_active": self.is_active,
            "remarks": self.remarks,
        }


class SaleItemFreeSchemeEngine:
    """Business-rule orchestration for Sale Item Free Scheme master.
    Separate from Purchase's ItemFreeSchemeEngine (engines/item_free_scheme_engine.py)
    -- these are two different business concepts (inbound vs outbound free
    schemes) with different table schemas. Do NOT merge these classes."""

    def __init__(self, model: SaleItemFreeSchemeModel) -> None:
        self._model = model
        self._validator = ItemFreeSchemeValidator(
            scheme_exists_fn=self._model.exists_active_for_item,
        )

    def create_scheme(self, data: dict, current_user_id: int) -> ItemFreeSchemeDTO:
        errors = self._validator.validate(data)
        if not errors.is_valid:
            raise ValidationError(errors.errors)
        now_ad, now_bs = self._now_stamps()
        scheme_data = {
            "item_id": data["item_id"],
            "scheme_qty": data["scheme_qty"],
            "scheme_free": data["scheme_free"],
            "is_active": data.get("is_active", True),
            "remarks": (data.get("remarks") or "").strip() or None,
            "created_by": current_user_id,
            "created_at_ad": now_ad,
            "created_at_bs": now_bs,
        }
        try:
            new_id = self._model.insert(scheme_data)
        except Exception as exc:
            if self._is_unique_violation(exc):
                raise DuplicateRecordError("An active free scheme already exists for this item.") from exc
            logger.exception("Unexpected error inserting sale item free scheme.")
            raise
        return self.get_scheme(new_id)

    def update_scheme(self, sale_item_free_scheme_id: int, data: dict, current_user_id: int) -> ItemFreeSchemeDTO:
        existing = self._model.get_by_id(sale_item_free_scheme_id, include_deleted=False)
        if existing is None:
            raise RecordNotFoundError(f"Free scheme {sale_item_free_scheme_id} not found.")
        errors = self._validator.validate(data, exclude_id=sale_item_free_scheme_id)
        if not errors.is_valid:
            raise ValidationError(errors.errors)
        now_ad, now_bs = self._now_stamps()
        update_data = {
            "scheme_qty": data["scheme_qty"],
            "scheme_free": data["scheme_free"],
            "is_active": data.get("is_active", True),
            "remarks": (data.get("remarks") or "").strip() or None,
            "updated_by": current_user_id,
            "updated_at_ad": now_ad,
            "updated_at_bs": now_bs,
        }
        self._model.update(sale_item_free_scheme_id, update_data)
        return self.get_scheme(sale_item_free_scheme_id)

    # ------------------------------------------------------------------ #
    # READ
    # ------------------------------------------------------------------ #
    def get_scheme(self, sale_item_free_scheme_id: int) -> ItemFreeSchemeDTO:
        row = self._model.get_by_id(sale_item_free_scheme_id, include_deleted=False)
        if row is None:
            raise RecordNotFoundError(f"Free scheme {sale_item_free_scheme_id} not found.")
        return self._to_dto(row)

    def get_scheme_for_item(self, item_id: int) -> Optional[tuple[float, float]]:
        """Returns (scheme_qty, scheme_free) for the item's active scheme,
        or None if no scheme is configured. Called live by SaleEngine's
        compute_line()."""
        row = self._model.get_active_by_item(item_id)
        if row is None:
            return None
        return (float(row["scheme_qty"]), float(row["scheme_free"]))

    def list_schemes(
        self,
        search_text: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ItemFreeSchemeDTO], int]:
        filters = SaleItemFreeSchemeSearchFilters(
            search_text=search_text,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )
        rows, total = self._model.search(filters)
        return [self._to_dto(r) for r in rows], total

    # ------------------------------------------------------------------ #
    # SOFT DELETE / RESTORE
    # ------------------------------------------------------------------ #
    def soft_delete_scheme(self, sale_item_free_scheme_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(sale_item_free_scheme_id, include_deleted=False)
        if existing is None:
            raise RecordNotFoundError(f"Free scheme {sale_item_free_scheme_id} not found.")
        now_ad, now_bs = self._now_stamps()
        self._model.soft_delete(
            sale_item_free_scheme_id=sale_item_free_scheme_id,
            deleted_by=current_user_id,
            deleted_at_ad=now_ad,
            deleted_at_bs=now_bs,
        )

    def restore_scheme(self, sale_item_free_scheme_id: int, current_user_id: int) -> None:
        existing = self._model.get_by_id(sale_item_free_scheme_id, include_deleted=True)
        if existing is None:
            raise RecordNotFoundError(f"Free scheme {sale_item_free_scheme_id} not found.")
        now_ad, now_bs = self._now_stamps()
        self._model.restore(
            sale_item_free_scheme_id=sale_item_free_scheme_id,
            updated_by=current_user_id,
            updated_at_ad=now_ad,
            updated_at_bs=now_bs,
        )

    # ------------------------------------------------------------------ #
    # INTERNALS
    # ------------------------------------------------------------------ #
    def _to_dto(self, row: dict) -> ItemFreeSchemeDTO:
        return ItemFreeSchemeDTO(
            sale_item_free_scheme_id=row.get("sale_item_free_scheme_id"),
            item_id=row["item_id"],
            item_name=row.get("item_name", ""),
            item_code=row.get("item_code", ""),
            scheme_qty=float(row["scheme_qty"]),
            scheme_free=float(row["scheme_free"]),
            is_active=bool(row.get("is_active", True)),
            remarks=row.get("remarks"),
        )

    @staticmethod
    def _now_stamps() -> tuple:
        now_ad = datetime.now(timezone.utc)
        now_bs = ""
        try:
            from engines.date_engine import ad_to_bs
            now_bs = ad_to_bs(now_ad.date())
        except Exception:
            logger.warning("Could not convert AD->BS for now_stamps.")
        return now_ad, now_bs

    @staticmethod
    def _is_unique_violation(exc: Exception) -> bool:
        return "unique" in str(exc).lower() or "duplicate" in str(exc).lower()


__all__ = ["SaleItemFreeSchemeEngine", "ItemFreeSchemeDTO"]