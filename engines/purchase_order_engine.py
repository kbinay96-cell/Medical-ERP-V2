# engines/purchase_order_engine.py
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

from engines.exceptions import RecordNotFoundError, ValidationError
from models.purchase_order_model import PurchaseOrderModel, PurchaseOrderSearchFilters
from models.item_model import ItemModel
from engines.purchase_validator import PurchaseOrderValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class LowStockSuggestionDTO:
    """One row for the auto-suggest screen."""
    item_id: int
    item_name: str
    current_stock: float
    minimum_stock: float
    suggested_qty: float          # (minimum_stock * reorder_multiplier) - current_stock
    already_ordered_elsewhere: list[dict] = field(default_factory=list)
    # e.g. [{"po_number": "PO-0012", "supplier_name": "Sun Pharma", "status": "Sent", "ordered_qty": 50}]


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
    lines: list[PurchaseOrderLineDTO] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PurchaseOrderEngine:
    """Business-rule orchestration for Purchase Orders — auto low-stock
    suggestion, manual add/remove, duplicate-order warning, WhatsApp/Email
    message building. Screens call ONLY this class."""

    def __init__(
        self,
        model: PurchaseOrderModel,
        item_model: ItemModel,
        date_engine,
        settings_engine,
    ) -> None:
        self._model = model
        self._item_model = item_model
        self._date_engine = date_engine
        self._settings_engine = settings_engine

    # -- numbering ------------------------------------------------------

    def generate_po_number(self) -> str:
        """Next sequential PO-0001, PO-0002... Settings-driven
        (purchase.po_prefix), same pattern as ItemEngine.generate_item_code()."""
        from engines.settings_engine import get_setting

        prefix = get_setting("purchase.po_prefix", "PO-")
        next_seq = self._model.get_next_po_sequence()
        return f"{prefix}{next_seq:04d}"

    # -- low stock suggestions -------------------------------------------

    def get_low_stock_suggestions(self) -> list[LowStockSuggestionDTO]:
        """LIVE query, called fresh every time the PO screen opens:
        1. self._item_model.get_low_stock_items() -> raw low-stock rows
        2. self._model.get_open_order_items_for_item_ids([...]) -> duplicate
           warnings, attached per item
        3. suggested_qty = (minimum_stock * settings.purchase.reorder_target_multiplier)
           - current_stock, floored at 0
        Never raises — an item stays in this list until its real stock
        (via a posted Purchase Invoice) rises back above minimum_stock,
        because this is a live comparison, not a stored flag."""
        from engines.settings_engine import get_setting

        try:
            low_stock_rows = self._item_model.get_low_stock_items()
        except Exception:
            logger.exception("Failed to fetch low-stock items")
            return []

        if not low_stock_rows:
            return []

        item_ids = [row["item_id"] for row in low_stock_rows]

        try:
            open_order_rows = self._model.get_open_order_items_for_item_ids(item_ids)

            open_order_items_by_item_id = {}
            for order_row in open_order_rows:
                open_order_items_by_item_id.setdefault(
                    order_row["item_id"], []
                ).append(order_row)

        except Exception:
            logger.exception("Failed to fetch open PO items for duplicate-order warnings")
            open_order_items_by_item_id = {}

        reorder_multiplier = float(get_setting("purchase.reorder_target_multiplier", 1.5))

        suggestions: list[LowStockSuggestionDTO] = []
        for row in low_stock_rows:
            current_stock = float(row["current_stock"])
            minimum_stock = float(row["minimum_stock"])
            suggested_qty = max(0.0, (minimum_stock * reorder_multiplier) - current_stock)

            suggestions.append(
                LowStockSuggestionDTO(
                    item_id=row["item_id"],
                    item_name=row["item_name"],
                    current_stock=current_stock,
                    minimum_stock=minimum_stock,
                    suggested_qty=round(suggested_qty, 2),
                    already_ordered_elsewhere=open_order_items_by_item_id.get(row["item_id"], []),
                )
            )

        return suggestions

    # -- create / read / search / lifecycle -------------------------------

    def create_purchase_order(self, payload: dict[str, Any], current_user_id: int) -> PurchaseOrderDTO:
        """Validates header + each line (PurchaseOrderValidator), inserts
        purchase_order + purchase_order_item rows (both manual and
        auto-suggested lines saved the same way, is_auto_suggested flag
        just for audit/reporting). Does NOT touch item_batch/stock —
        a PO is a request, not a stock movement."""
        from engines.date_engine import ad_to_bs, DateEngineError  # noqa: F401

        is_valid, error = PurchaseOrderValidator.validate_order_header(payload)
        if not is_valid:
            raise ValidationError(error)

        raw_lines = payload.get("lines") or []
        for raw_line in raw_lines:
            is_valid, error = PurchaseOrderValidator.validate_order_line(raw_line)
            if not is_valid:
                raise ValidationError(error)

        lines = [
            PurchaseOrderLineDTO(
                item_id=raw_line["item_id"],
                ordered_qty=float(raw_line["ordered_qty"]),
                rate=float(raw_line.get("rate") or 0.0),
                is_auto_suggested=bool(raw_line.get("is_auto_suggested", False)),
                stock_at_order_time=raw_line.get("stock_at_order_time"),
                minimum_stock_at_order_time=raw_line.get("minimum_stock_at_order_time"),
            )
            for raw_line in raw_lines
        ]

        now_ad = datetime.now(timezone.utc)
        try:
            now_bs = ad_to_bs(now_ad.date())
        except DateEngineError:
            logger.exception("Could not resolve BS date for purchase order audit stamp")
            now_bs = None

        po_number = self.generate_po_number()

        new_po_id = self._model.insert_order(
            {
                "po_number": po_number,
                "supplier_id": payload["supplier_id"],
                "order_date_bs": payload["order_date_bs"],
                "status": "Draft",
                "sent_via": None,
                "created_by": current_user_id,
                "created_at_ad": now_ad,
                "created_at_bs": now_bs,
            }
        )

        for line in lines:
            self._model.insert_order_item(purchase_order_id=new_po_id, line=asdict(line))

        return PurchaseOrderDTO(
            purchase_order_id=new_po_id,
            po_number=po_number,
            supplier_id=payload["supplier_id"],
            order_date_bs=payload["order_date_bs"],
            status="Draft",
            sent_via=None,
            lines=lines,
        )

    def build_supplier_message(self, purchase_order_id: int) -> dict[str, str]:
        """Reads Settings templates (purchase.whatsapp_message_template,
        purchase.email_subject_template, purchase.email_body_template),
        fills in {supplier_name}, {po_number}, {item_list}, {company_name}
        placeholders using the PO's actual lines + item names + company
        name (from Settings' existing company.name key). Returns:
        {"whatsapp_text": "...", "email_subject": "...", "email_body": "..."}
        Pure text building — no webbrowser/UI calls here (Screen's job)."""
        from engines.settings_engine import get_setting

        order = self.get_purchase_order(purchase_order_id)

        supplier_name = self._model.get_supplier_name(order.supplier_id)
        company_name = get_setting("company.name", "")

        item_lines = []
        for line in order.lines:
            item_name = self._item_model.get_item_name(line.item_id)
            item_lines.append(f"- {item_name}: {line.ordered_qty}")
        item_list = "\n".join(item_lines)

        whatsapp_template = get_setting(
            "purchase.whatsapp_message_template",
            "Hello {supplier_name}, please find our order {po_number} from {company_name}:\n{item_list}",
        )
        email_subject_template = get_setting(
            "purchase.email_subject_template",
            "Purchase Order {po_number} — {company_name}",
        )
        email_body_template = get_setting(
            "purchase.email_body_template",
            "Dear {supplier_name},\n\nPlease find our purchase order {po_number} below:\n\n{item_list}\n\nRegards,\n{company_name}",
        )

        format_kwargs = {
            "supplier_name": supplier_name,
            "po_number": order.po_number,
            "item_list": item_list,
            "company_name": company_name,
        }

        whatsapp_text = whatsapp_template.format(**format_kwargs)
        email_subject = email_subject_template.format(**format_kwargs)
        email_body = email_body_template.format(**format_kwargs)

        return {
            "whatsapp_text": whatsapp_text,
            "email_subject": email_subject,
            "email_body": email_body,
        }

    def mark_sent(self, purchase_order_id: int, sent_via: str, current_user_id: int) -> None:
        """sent_via = 'whatsapp' | 'email'. Called by the Screen right after
        the wa.me/mailto link is opened. Sets status='Sent' if it was
        'Draft'."""
        if sent_via not in ("whatsapp", "email"):
            raise ValidationError("sent_via must be 'whatsapp' or 'email'.")

        order = self._model.get_order_by_id(purchase_order_id, include_deleted=False)
        if order is None:
            raise RecordNotFoundError(f"Purchase order {purchase_order_id} not found.")

        if order["status"] == "Draft":
            self._model.update_order_status(
                purchase_order_id=purchase_order_id,
                status="Sent",
                sent_via=sent_via,
                current_user_id=current_user_id,
            )

    def mark_received(self, purchase_order_id: int, current_user_id: int) -> None:
        """Called by PurchaseEngine.create_purchase_invoice() when an
        invoice references this PO. Sets status='Received' — whole PO,
        no partial tracking (confirmed scope)."""
        order = self._model.get_order_by_id(purchase_order_id, include_deleted=False)
        if order is None:
            raise RecordNotFoundError(f"Purchase order {purchase_order_id} not found.")

        self._model.update_order_status(
            purchase_order_id=purchase_order_id,
            status="Received",
            sent_via=order.get("sent_via"),
            current_user_id=current_user_id,
        )

    def get_purchase_order(self, purchase_order_id: int, include_deleted: bool = False) -> PurchaseOrderDTO:
        row = self._model.get_order_by_id(purchase_order_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Purchase order {purchase_order_id} not found.")

        line_rows = self._model.get_order_items(purchase_order_id)
        lines = [
            PurchaseOrderLineDTO(
                item_id=r["item_id"],
                ordered_qty=r["ordered_qty"],
                rate=r.get("rate", 0.0),
                is_auto_suggested=r.get("is_auto_suggested", False),
                stock_at_order_time=r.get("stock_at_order_time"),
                minimum_stock_at_order_time=r.get("minimum_stock_at_order_time"),
            )
            for r in line_rows
        ]

        return PurchaseOrderDTO(
            purchase_order_id=row["purchase_order_id"],
            po_number=row["po_number"],
            supplier_id=row["supplier_id"],
            order_date_bs=row["order_date_bs"],
            status=row["status"],
            sent_via=row.get("sent_via"),
            lines=lines,
        )

    def search_purchase_orders(
        self,
        search_text: Optional[str] = None,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PurchaseOrderDTO], int]:
        filters = PurchaseOrderSearchFilters(
            search_text=search_text,
            supplier_id=supplier_id,
            status=status,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
        )

        rows, total_count = self._model.search(filters)

        results = [
            PurchaseOrderDTO(
                purchase_order_id=r["purchase_order_id"],
                po_number=r["po_number"],
                supplier_id=r["supplier_id"],
                order_date_bs=r["order_date_bs"],
                status=r["status"],
                sent_via=r.get("sent_via"),
                lines=[],
            )
            for r in rows
        ]
        return results, total_count

    def cancel_purchase_order(self, purchase_order_id: int, current_user_id: int) -> None:
        """Soft-delete only. An item on a cancelled PO reappears in
        get_low_stock_suggestions() next time (if still genuinely low),
        since that query ignores cancelled/deleted POs by design."""
        order = self._model.get_order_by_id(purchase_order_id, include_deleted=False)
        if order is None:
            raise RecordNotFoundError(f"Purchase order {purchase_order_id} not found.")

        self._model.soft_delete_order(
            purchase_order_id=purchase_order_id, current_user_id=current_user_id
        )


# ---------------------------------------------------------------------------
# WhatsApp/Email link helpers (kept here as pure text-to-URL utilities;
# the Screen, not this Engine, is responsible for actually calling
# webbrowser.open() — see the note in the blueprint).
# ---------------------------------------------------------------------------

def build_whatsapp_url(mobile_no: str, whatsapp_text: str) -> str:
    """https://wa.me/{mobile_no}?text={urlencoded_text} — zero API cost,
    Phase-1 approach. Purely builds the URL string; opening it is the
    Screen's job via webbrowser.open()."""
    digits_only = "".join(ch for ch in mobile_no if ch.isdigit())
    return f"https://wa.me/{digits_only}?text={quote(whatsapp_text)}"


def build_mailto_url(email: str, subject: str, body: str) -> str:
    """mailto:{email}?subject=...&body=... — opens the user's default email
    client via webbrowser.open() (Screen's job), pre-filled, zero SMTP
    server required."""
    return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"