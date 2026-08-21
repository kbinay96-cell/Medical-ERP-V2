# engines/purchase_order_engine.py
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional, List

from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_order_model import PurchaseOrderModel, PurchaseOrderSearchFilters
from models.item_model import ItemModel
from engines.purchase_validator import PurchaseOrderValidator

logger = logging.getLogger(__name__)


@dataclass
class LowStockSuggestionDTO:
    item_id: int
    item_name: str
    current_stock: float
    minimum_stock: float
    suggested_qty: float
    already_ordered_elsewhere: List[dict] = field(default_factory=list)


@dataclass
class PurchaseOrderLineDTO:
    item_id: int
    ordered_qty: float
    rate: float = 0.0
    is_auto_suggested: bool = False
    stock_at_order_time: Optional[float] = None
    minimum_stock_at_order_time: Optional[float] = None


@dataclass
class PurchaseOrderDTO:
    purchase_order_id: Optional[int]
    po_number: str
    supplier_id: int
    order_date_bs: str
    status: str
    sent_via: Optional[str]
    lines: List[PurchaseOrderLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class PurchaseOrderEngine:
    def __init__(self, model: PurchaseOrderModel, item_model: ItemModel, date_engine, settings_engine) -> None:
        self._model = model
        self._item_model = item_model
        self._date_engine = date_engine
        self._settings_engine = settings_engine

    def _now_ad(self):
        return datetime.now()

    def _now_bs(self):
        try:
            return self._date_engine.ad_to_bs(self._now_ad().date())
        except Exception:
            return ""

    def generate_po_number(self) -> str:
        prefix = self._settings_engine.get_setting("purchase.po_prefix", "PO-")
        last = self._model.get_last_po_number_sequence(prefix)
        next_seq = (last or 0) + 1
        return f"{prefix}{next_seq:04d}"

    def get_low_stock_suggestions(self) -> List[LowStockSuggestionDTO]:
        raw = self._item_model.get_low_stock_items()
        if not raw:
            return []
        item_ids = [r["item_id"] for r in raw]
        open_order_rows = self._model.get_open_order_items_for_item_ids(item_ids) if item_ids else []
        # group open orders by item_id
        open_map = {}
        for r in open_order_rows:
            iid = r.get("item_id")
            open_map.setdefault(iid, []).append(r)

        multiplier = float(self._settings_engine.get_setting("purchase.reorder_target_multiplier", "2") or 2)
        suggestions = []
        for r in raw:
            item_id = r.get("item_id")
            current_stock = float(r.get("total_stock") or 0)
            minimum_stock = float(r.get("minimum_stock") or 0)
            target = (minimum_stock * multiplier) - current_stock
            suggested_qty = int(max(0, round(target)))
            suggestions.append(
                LowStockSuggestionDTO(
                    item_id=item_id,
                    item_name=r.get("item_name"),
                    current_stock=current_stock,
                    minimum_stock=minimum_stock,
                    suggested_qty=suggested_qty,
                    already_ordered_elsewhere=open_map.get(item_id, []),
                )
            )
        return suggestions

    def create_purchase_order(self, payload: dict[str, Any], current_user_id: int) -> PurchaseOrderDTO:
        ok, err = PurchaseOrderValidator.validate_order_header(payload)
        if not ok:
            raise ValidationError([err])
        lines = payload.get("lines", [])
        if not isinstance(lines, list) or len(lines) == 0:
            raise ValidationError(["At least one order line is required."])
        # Validate each line
        for idx, ln in enumerate(lines):
            ok, err = PurchaseOrderValidator.validate_order_line(ln)
            if not ok:
                raise ValidationError([f"Line {idx+1}: {err}"])

        po_number = payload.get("po_number") or self.generate_po_number()
        header = {
            "po_number": po_number,
            "supplier_id": payload["supplier_id"],
            "order_date_ad": payload.get("order_date_ad") or self._now_ad().date(),
            "order_date_bs": payload.get("order_date_bs") or self._now_bs(),
            "status": payload.get("status", "Draft"),
            "sent_via": payload.get("sent_via"),
            "remarks": payload.get("remarks"),
            "created_by": current_user_id,
            "created_at_ad": self._now_ad(),
            "created_at_bs": self._now_bs(),
        }
        po_id = self._model.insert_order(header)
        # Insert items
        for ln in lines:
            # Snapshot current_stock + minimum_stock if not provided
            stock_snapshot = ln.get("stock_at_order_time")
            min_snapshot = ln.get("minimum_stock_at_order_time")
            if stock_snapshot is None or min_snapshot is None:
                item_row = self._item_model.get_by_id(ln["item_id"])
                stock_snapshot = float(item_row.get("total_stock") if item_row and item_row.get("total_stock") is not None else 0)
                min_snapshot = float(item_row.get("minimum_stock") if item_row and item_row.get("minimum_stock") is not None else 0)
            item_data = {
                "item_id": ln["item_id"],
                "ordered_qty": ln["ordered_qty"],
                "rate": ln.get("rate", 0.0),
                "is_auto_suggested": ln.get("is_auto_suggested", False),
                "stock_at_order_time": stock_snapshot,
                "minimum_stock_at_order_time": min_snapshot,
                "remarks": ln.get("remarks"),
            }
            self._model.insert_order_item(po_id, item_data)
        dto = PurchaseOrderDTO(
            purchase_order_id=po_id,
            po_number=po_number,
            supplier_id=payload["supplier_id"],
            order_date_bs=header["order_date_bs"],
            status=header["status"],
            sent_via=header.get("sent_via"),
            lines=[],  # callers can retrieve lines via get_purchase_order if needed
        )
        return dto

    def build_supplier_message(self, purchase_order_id: int) -> dict[str, str]:
        po = self._model.get_by_id(purchase_order_id, include_deleted=False)
        if not po:
            raise RecordNotFoundError("Purchase order not found.")
        items = self._model.get_items_by_order(purchase_order_id)
        # Build item list
        from models.item_model import ItemModel
        im = ItemModel()
        item_lines = []
        for it in items:
            item_info = im.get_by_id(it["item_id"])
            item_name = item_info.get("item_name") if item_info else f"Item-{it['item_id']}"
            item_lines.append(f"- {item_name} : {it.get('ordered_qty')}")
        item_list_text = "\n".join(item_lines)
        supplier_name = ""  # try to fetch supplier name
        try:
            from models.supplier_model import SupplierModel
            supplier_row = SupplierModel().get_by_id(po.get("supplier_id"))
            supplier_name = supplier_row.get("supplier_name") if supplier_row else ""
        except Exception:
            supplier_name = ""

        company_name = self._settings_engine.get_setting("company.name", "Your Company")
        whatsapp_tpl = self._settings_engine.get_setting("purchase.whatsapp_message_template", "Hello {supplier_name}, please arrange the following items:\n{item_list}\n\nRegards, {company_name}")
        email_sub_tpl = self._settings_engine.get_setting("purchase.email_subject_template", "Purchase Order - {po_number}")
        email_body_tpl = self._settings_engine.get_setting("purchase.email_body_template", "Dear {supplier_name},\n\nPlease find our purchase order below:\n{item_list}\n\nRegards,\n{company_name}")

        whatsapp_text = whatsapp_tpl.format(supplier_name=supplier_name, po_number=po.get("po_number"), item_list=item_list_text, company_name=company_name)
        email_subject = email_sub_tpl.format(supplier_name=supplier_name, po_number=po.get("po_number"), item_list=item_list_text, company_name=company_name)
        email_body = email_body_tpl.format(supplier_name=supplier_name, po_number=po.get("po_number"), item_list=item_list_text, company_name=company_name)

        return {"whatsapp_text": whatsapp_text, "email_subject": email_subject, "email_body": email_body}

    def mark_sent(self, purchase_order_id: int, sent_via: str, current_user_id: int) -> None:
        updated_at_ad = self._now_ad()
        updated_at_bs = self._now_bs()
        # Use model.mark_status (exists) to set status to Sent if current is Draft
        self._model.mark_status(purchase_order_id, "Sent", updated_by=current_user_id, updated_at_ad=updated_at_ad, updated_at_bs=updated_at_bs)

    def mark_received(self, purchase_order_id: int, current_user_id: int) -> None:
        updated_at_ad = self._now_ad()
        updated_at_bs = self._now_bs()
        self._model.mark_status(purchase_order_id, "Received", updated_by=current_user_id, updated_at_ad=updated_at_ad, updated_at_bs=updated_at_bs)

    def get_purchase_order(self, purchase_order_id: int, include_deleted: bool = False) -> Optional[PurchaseOrderDTO]:
        row = self._model.get_by_id(purchase_order_id, include_deleted=include_deleted)
        if not row:
            return None
        # load lines
        lines = []
        raw_lines = self._model.get_items_by_order(purchase_order_id)
        for r in raw_lines:
            lines.append(PurchaseOrderLineDTO(
                item_id=r.get("item_id"),
                ordered_qty=float(r.get("ordered_qty") or 0),
                rate=float(r.get("rate") or 0),
                is_auto_suggested=bool(r.get("is_auto_suggested")),
                stock_at_order_time=r.get("stock_at_order_time"),
                minimum_stock_at_order_time=r.get("minimum_stock_at_order_time"),
            ))
        dto = PurchaseOrderDTO(
            purchase_order_id=row.get("purchase_order_id"),
            po_number=row.get("po_number"),
            supplier_id=row.get("supplier_id"),
            order_date_bs=row.get("order_date_bs"),
            status=row.get("status"),
            sent_via=row.get("sent_via"),
            lines=lines,
        )
        return dto

    def search_purchase_orders(self, **kwargs):
        filters = PurchaseOrderSearchFilters(
            search_text=kwargs.get("search_text"),
            supplier_id=kwargs.get("supplier_id"),
            status=kwargs.get("status"),
            include_deleted=kwargs.get("include_deleted", False),
            page=kwargs.get("page", 1),
            page_size=kwargs.get("page_size", 50),
        )
        rows, total = self._model.search(filters)
        return rows, total

    def cancel_purchase_order(self, purchase_order_id: int, current_user_id: int) -> None:
        deleted_at_ad = self._now_ad()
        deleted_at_bs = self._now_bs()
        self._model.soft_delete(purchase_order_id, deleted_by=current_user_id, deleted_at_ad=deleted_at_ad, deleted_at_bs=deleted_at_bs)