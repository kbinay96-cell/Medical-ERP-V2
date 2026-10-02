"""
Record Detail Hub.

Landing screen for a Master Search result on a Customer, Supplier or Item:
a read-only key-info card (the shared MasterDetailPanel) plus action
buttons -- Edit, and one or more ledger/history report shortcuts -- so that
Edit is a deliberate choice instead of the default landing.

The screen itself is entity-agnostic: the dashboard hands it a loader
(returns a HubPayload), an edit callback and a list of HubActions. The
build_*_payload() functions below map each entity's real data onto the card.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from engines.exceptions import RecordNotFoundError
from utils.integration_adapters import show_error
from utils.item_form_helpers import format_qty
from widgets.master_detail_panel import MasterDetailPanel

logger = logging.getLogger(__name__)


CUSTOMER_HUB_CAPTIONS = (
    "Mobile:", "Phone:", "Address:", "City:", "Area:", "Route:", "Price Level:",
    "Open. Balance:", "Credit Limit:", "Status:", "Created:", "Updated:", "Deleted:",
)
SUPPLIER_HUB_CAPTIONS = (
    "Contact:", "Mobile:", "Phone:", "Email:", "Address:", "City:", "PAN/VAT:",
    "Open. Balance:", "Credit Limit:", "Credit Days:", "Status:",
    "Created:", "Updated:", "Deleted:",
)
ITEM_HUB_CAPTIONS = (
    "Category:", "Manufacturer:", "Unit:", "Packing:", "Purchase Rate:", "Sale Rate:",
    "MRP:", "Stock:", "Min. Stock:", "Status:", "Created:", "Updated:", "Deleted:",
)


@dataclass
class HubPayload:
    title: str
    subtitle: str
    photo_path: Optional[str]
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class HubAction:
    label: str
    callback: Callable[[], None]


class RecordDetailHubScreen(QWidget):
    close_requested = Signal()

    def __init__(
        self,
        parent,
        *,
        heading: str,
        placeholder_title: str,
        placeholder_icon: str,
        field_captions: Sequence[str],
        loader: Callable[[], HubPayload],
        on_edit: Callable[[], None],
        history_actions: Sequence[HubAction] = (),
    ) -> None:
        super().__init__(parent)
        self._heading = heading
        self._captions = tuple(field_captions)
        self._loader = loader

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        self.btnBack = QPushButton("← Back")
        self.btnBack.clicked.connect(lambda _checked=False: self.close_requested.emit())
        self.lblHeading = QLabel(heading)
        self.lblHeading.setStyleSheet("font-size: 13pt; font-weight: 700;")
        top_row.addWidget(self.btnBack)
        top_row.addWidget(self.lblHeading)
        top_row.addStretch(1)
        root.addLayout(top_row)

        self._panel = MasterDetailPanel(
            placeholder_title=placeholder_title,
            placeholder_icon=placeholder_icon,
            field_captions=self._captions,
            wide=True,
        )
        root.addWidget(self._panel, 1)

        action_row = QHBoxLayout()
        self.btnEdit = QPushButton("Edit")
        self.btnEdit.clicked.connect(lambda _checked=False: on_edit())
        action_row.addWidget(self.btnEdit)

        self._action_buttons: list[QPushButton] = [self.btnEdit]
        for action in history_actions:
            button = QPushButton(action.label)
            button.clicked.connect(lambda _checked=False, cb=action.callback: cb())
            action_row.addWidget(button)
            self._action_buttons.append(button)
        action_row.addStretch(1)
        root.addLayout(action_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Every time this page becomes current -- first open, and again when
        # the user comes back from Edit / a report -- reload the card so it
        # never shows stale data. Deferred so any error dialog appears after
        # the screen is on stage rather than inside the show event.
        if not event.spontaneous():
            QTimer.singleShot(0, self.refresh)

    def refresh(self) -> None:
        try:
            self._refresh()
        except RuntimeError:
            # C++ widget already disposed (user navigated away before a
            # deferred refresh / dialog-finished signal fired).
            return

    def _refresh(self) -> None:
        try:
            payload = self._loader()
        except RecordNotFoundError as exc:
            self._show_load_failure(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("RecordDetailHubScreen: failed to load '%s'.", self._heading)
            self._show_load_failure("Could not load this record. Please try again.")
            return

        self._panel.set_photo(payload.photo_path)
        self._panel.set_heading(payload.title, payload.subtitle)
        for caption in self._captions:
            self._panel.set_field(caption, payload.fields.get(caption, "-"))
        for button in self._action_buttons:
            button.setEnabled(True)

    def _show_load_failure(self, message: str) -> None:
        self._panel.show_placeholder()
        for button in self._action_buttons:
            button.setEnabled(False)
        show_error(self, self._heading, message)


def _money(value) -> str:
    return f"{float(value or 0):,.2f}"


def build_customer_payload(customer_engine_module, customer_id: int) -> HubPayload:
    row = customer_engine_module.get_customer(customer_id)
    if row is None:
        raise RecordNotFoundError(f"Customer {customer_id} not found.")

    if row.get("is_deleted"):
        status = "Deleted"
    elif row.get("is_active"):
        status = "Active"
    else:
        status = "Inactive"

    opening = f"{_money(row.get('opening_balance'))} {row.get('balance_type') or ''}".strip()
    fmt = MasterDetailPanel.format_audit
    return HubPayload(
        title=row.get("customer_name") or "-",
        subtitle=row.get("customer_code") or "",
        photo_path=row.get("photo_path"),
        fields={
            "Mobile:": row.get("mobile") or "-",
            "Phone:": row.get("phone") or "-",
            "Address:": row.get("address") or "-",
            "City:": row.get("city") or "-",
            "Area:": row.get("area_name") or "-",
            "Route:": row.get("route_name") or "-",
            "Price Level:": row.get("price_level_name") or "-",
            "Open. Balance:": opening,
            "Credit Limit:": _money(row.get("credit_limit")),
            "Status:": status,
            "Created:": fmt(row.get("created_by"), row.get("created_at_bs"), row.get("created_at_ad")),
            "Updated:": fmt(row.get("updated_by"), row.get("updated_at_bs"), row.get("updated_at_ad")),
            "Deleted:": (
                fmt(row.get("deleted_by"), row.get("deleted_at_bs"), row.get("deleted_at_ad"))
                if row.get("is_deleted") else "-"
            ),
        },
    )


def build_supplier_payload(supplier_engine, supplier_id: int) -> HubPayload:
    dto = supplier_engine.get_supplier(supplier_id, include_deleted=True)
    fmt = MasterDetailPanel.format_audit
    return HubPayload(
        title=dto.supplier_name or "-",
        subtitle=dto.supplier_code or "",
        photo_path=dto.photo_path,
        fields={
            "Contact:": dto.contact_person or "-",
            "Mobile:": dto.mobile_no or "-",
            "Phone:": dto.phone_no or "-",
            "Email:": dto.email or "-",
            "Address:": dto.address or "-",
            "City:": dto.city or "-",
            "PAN/VAT:": dto.pan_vat_no or "-",
            "Open. Balance:": f"{_money(dto.opening_balance)} {dto.balance_type or ''}".strip(),
            "Credit Limit:": _money(dto.credit_limit) if dto.credit_limit is not None else "-",
            "Credit Days:": str(dto.credit_days) if dto.credit_days is not None else "-",
            "Status:": "Deleted" if dto.is_deleted else (dto.status or "-"),
            "Created:": fmt(dto.created_by, dto.created_at_bs, dto.created_at_ad),
            "Updated:": fmt(dto.updated_by, dto.updated_at_bs, dto.updated_at_ad),
            "Deleted:": (
                fmt(dto.deleted_by, dto.deleted_at_bs, dto.deleted_at_ad) if dto.is_deleted else "-"
            ),
        },
    )


def _item_lookup_names() -> tuple[dict, dict, dict]:
    """Same lookup-name loading the Item list screen does (_load_lookup_names)."""
    from engines.item_lookup_registry import category_engine, manufacturer_engine, unit_engine

    categories: dict = {}
    manufacturers: dict = {}
    units: dict = {}
    try:
        categories = {dto.id: dto.name for dto in category_engine().list_active()}
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load category names for Item hub.")
    try:
        rows, _ = manufacturer_engine().search_manufacturers(page=1, page_size=1000)
        manufacturers = {m.manufacturer_id: m.manufacturer_name for m in rows}
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load manufacturer names for Item hub.")
    try:
        units = {dto.id: dto.name for dto in unit_engine().list_active()}
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load unit names for Item hub.")
    return categories, manufacturers, units


def build_item_payload(item_engine, item_id: int) -> HubPayload:
    dto = item_engine.get_item(item_id, include_deleted=True)
    categories, manufacturers, units = _item_lookup_names()
    unit_name = units.get(dto.unit_id, "") if dto.unit_id else ""
    fmt = MasterDetailPanel.format_audit
    return HubPayload(
        title=dto.item_name or "-",
        subtitle=dto.item_code or "",
        photo_path=dto.photo_path,
        fields={
            "Category:": categories.get(dto.category_id, "-") if dto.category_id else "-",
            "Manufacturer:": manufacturers.get(dto.manufacturer_id, "-") if dto.manufacturer_id else "-",
            "Unit:": unit_name or "-",
            "Packing:": dto.packing or "-",
            "Purchase Rate:": _money(dto.purchase_rate),
            "Sale Rate:": _money(dto.sale_rate),
            "MRP:": _money(dto.mrp),
            "Stock:": f"{format_qty(dto.total_stock)} {unit_name}".strip(),
            "Min. Stock:": (
                f"{format_qty(dto.minimum_stock)} {unit_name}".strip()
                if dto.minimum_stock is not None else "-"
            ),
            "Status:": "Deleted" if dto.is_deleted else (dto.status or "-"),
            "Created:": fmt(dto.created_by, dto.created_at_bs, dto.created_at_ad),
            "Updated:": fmt(dto.updated_by, dto.updated_at_bs, dto.updated_at_ad),
            "Deleted:": (
                fmt(dto.deleted_by, dto.deleted_at_bs, dto.deleted_at_ad) if dto.is_deleted else "-"
            ),
        },
    )