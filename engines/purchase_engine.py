# engines/purchase_engine.py
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from engines.exceptions import DuplicateRecordError, RecordNotFoundError, ValidationError
from models.purchase_invoice_model import PurchaseInvoiceModel, PurchaseInvoiceSearchFilters
from engines.purchase_validator import PurchaseValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class PurchaseInvoiceLineDTO:
    item_id: int
    batch_no: str
    expiry_month: int
    expiry_year: int
    qty: float
    free_qty: float
    purchase_rate: float
    discount_percent: float
    cc_percent: float
    mrp: float
    sale_rate: float
    # computed/output fields (Engine fills these, never accepted as input):
    discount_amount: float = 0.0
    cc_amount: float = 0.0
    # invoice-level freight/other charges allocated to this line, proportional
    # to its (qty + free_qty) share of total units — filled by
    # _allocate_invoice_level_charges() and consumed by _calculate_line_amounts().
    freight_allocated: float = 0.0
    other_charges_allocated: float = 0.0
    landing_cost_per_unit: float = 0.0
    item_batch_id: Optional[int] = None


@dataclass
class PurchaseInvoiceDTO:
    purchase_invoice_id: Optional[int]
    internal_ref_number: str
    invoice_number: str
    supplier_id: int
    invoice_date_bs: str
    grand_total: float
    status: str
    lines: list[PurchaseInvoiceLineDTO] = field(default_factory=list)
    bill_discount_amount: float = 0.0
    round_off_amount: float = 0.0
    invoice_date_ad: Optional[str] = None
    remarks: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PurchaseEngine:
    """Business-rule orchestration for Purchase Invoice (GRN + Bill combined).
    Screens call ONLY this class — mirrors SupplierEngine/ItemEngine shape.

    Golden rule reused from item_engine.py: this Engine does NOT write to
    item_batch or stock_ledger directly. It calls the already-built
    ItemEngine.add_batch(item_id, batch_payload, current_user_id,
    transaction_type='PURCHASE', reference_type='purchase_invoice',
    reference_id=purchase_invoice_id) — no duplicate stock-writing logic.
    """

    def __init__(
        self,
        model: PurchaseInvoiceModel,
        date_engine,
        settings_engine,
        item_engine,
        purchase_order_engine,
        discount_engine=None,
    ) -> None:
        """item_engine: an ItemEngine instance — Purchase Engine delegates
        all stock/batch writes to it, never touches item_batch/stock_ledger
        itself. CC% is resolved via item_engine.resolve_item_tax(item_id)
        (confirmed to exist on the real ItemEngine — returns
        (vat_percent, custom_percent)), so no separate country-tax/
        manufacturer lookup functions need to be injected here anymore.
        purchase_order_engine: injected so create_purchase_invoice() can
        mark a linked PO 'Received' — Purchase Invoice Engine never
        touches the purchase_order table directly."""
        self._model = model
        self._date_engine = date_engine
        self._settings_engine = settings_engine
        self._item_engine = item_engine
        self._purchase_order_engine = purchase_order_engine
        self._discount_engine = discount_engine

    # -- numbering ----------------------------------------------------------

    def generate_internal_ref_number(self) -> str:
        """Next sequential PINV-0001, PINV-0002... Settings-driven prefix,
        same pattern as ItemEngine.generate_item_code()."""
        from engines.settings_engine import get_setting
        prefix = get_setting("purchase.invoice_prefix", "PINV-")
        last_seq = self._model.get_last_internal_ref_sequence(prefix)
        return f"{prefix}{last_seq + 1:04d}"

    # -- resolution / calculation --------------------------------------------

    def _resolve_cc_percent(self, item_id: int) -> float:
        """Delegates to ItemEngine.resolve_item_tax(item_id), which is the
        SAME resolution logic Item Master already uses (manufacturer ->
        country -> country_tax, with the (0, 0) fallback for anything
        unconfigured) — Purchase Engine never queries manufacturer/country
        tables itself, just reuses the Engine that already owns this."""
        try:
            _vat_percent, custom_percent = self._item_engine.resolve_item_tax(item_id)
            return float(custom_percent) if custom_percent else 0.0
        except Exception:
            logger.exception(
                "Failed to resolve CC%% for item_id=%s via ItemEngine.resolve_item_tax — falling back to 0.0",
                item_id,
            )
            return 0.0

    def _resolve_discount_percent(self, item_id: int, supplier_id: int) -> float:
        """Auto-resolves per-item discount% for this supplier, via the
        item's manufacturer_id + SupplierManufacturerDiscountEngine.
        get_discount() — same never-raise fallback contract as
        _resolve_cc_percent(): a missing/unconfigured mapping never
        blocks invoice entry, just returns 0.0."""
        try:
            item = self._item_engine.get_item(item_id)
            manufacturer_id = item.manufacturer_id
            if not manufacturer_id:
                return 0.0
            if self._discount_engine is None:
                from engines.supplier_manufacturer_discount_engine import SupplierManufacturerDiscountEngine
                self._discount_engine = SupplierManufacturerDiscountEngine()
            return self._discount_engine.get_discount(supplier_id, manufacturer_id)
        except Exception:
            logger.exception(
                "Failed to resolve discount%% for item_id=%s supplier_id=%s — falling back to 0.0",
                item_id, supplier_id,
            )
            return 0.0

    def _calculate_line_amounts(self, line: PurchaseInvoiceLineDTO) -> PurchaseInvoiceLineDTO:
        """Pure calculation, no DB writes:
        1. discount_amount = qty * purchase_rate * (discount_percent / 100)
        2. cc_amount = free_qty * declared_customs_value_per_unit * (cc_percent / 100)
           -- declared_customs_value_per_unit is the item's purchase_rate
              of the PAID units on this same line (free qty's own rate is
              always 0 by definition, per glossary — so CC basis is the
              paid-unit rate, applied only to the free-qty count).
        3. landing_cost_per_unit = OUTPUT ONLY:
           ((qty * purchase_rate) - discount_amount + cc_amount
            + freight_allocated + other_charges_allocated) / (qty + free_qty)
           -- never used as an input to any other calculation (glossary rule).
        Returns the line with all computed fields filled in."""
        discount_amount = line.qty * line.purchase_rate * (line.discount_percent / 100.0)

        declared_customs_value_per_unit = line.purchase_rate
        cc_amount = line.free_qty * declared_customs_value_per_unit * (line.cc_percent / 100.0)

        total_units = line.qty + line.free_qty
        if total_units > 0:
            landing_cost_per_unit = (
                (line.qty * line.purchase_rate)
                - discount_amount
                + cc_amount
                + line.freight_allocated
                + line.other_charges_allocated
            ) / total_units
        else:
            # Both qty and free_qty are zero — validator should already have
            # rejected this line, but guard against a divide-by-zero anyway.
            landing_cost_per_unit = 0.0

        line.discount_amount = round(discount_amount, 4)
        line.cc_amount = round(cc_amount, 4)
        line.landing_cost_per_unit = round(landing_cost_per_unit, 4)
        return line

    def _allocate_invoice_level_charges(
        self,
        lines: list[PurchaseInvoiceLineDTO],
        total_freight: float,
        total_other: float,
    ) -> list[PurchaseInvoiceLineDTO]:
        """Splits invoice-level freight/other-charges across lines,
        proportional to each line's (qty + free_qty) share of total units.
        Must run BEFORE _calculate_line_amounts's landing_cost step."""
        grand_total_units = sum(l.qty + l.free_qty for l in lines)

        if grand_total_units <= 0:
            for l in lines:
                l.freight_allocated = 0.0
                l.other_charges_allocated = 0.0
            return lines

        for l in lines:
            share = (l.qty + l.free_qty) / grand_total_units
            l.freight_allocated = round(total_freight * share, 4)
            l.other_charges_allocated = round(total_other * share, 4)

        return lines

    # -- create / read / search / cancel ------------------------------------

    def create_purchase_invoice(self, payload: dict[str, Any], current_user_id: int) -> PurchaseInvoiceDTO:
        """Full flow:
        1. PurchaseValidator.validate_invoice_header() + validate_invoice_line() per line
        2. Duplicate check: model.exists_by_supplier_and_billno()
        3. Resolve CC% per line (_resolve_cc_percent)
        4. Allocate freight/other charges (_allocate_invoice_level_charges)
        5. Calculate amounts per line (_calculate_line_amounts)
        6. Insert purchase_invoice header (model.insert_invoice)
        7. For each line: insert purchase_invoice_item, THEN call
           self._item_engine.add_batch(item_id, batch_payload, current_user_id,
               transaction_type='PURCHASE', reference_type='purchase_invoice',
               reference_id=new_invoice_id)
           -- this is what actually creates the item_batch + stock_ledger row.
        8. Stamp resulting item_batch_id back via model.update_invoice_item_batch_link()
        9. If payload includes purchase_order_id: calls
           self._purchase_order_engine.mark_received(purchase_order_id, current_user_id)
           -- marks the WHOLE linked PO as 'Received' (no partial tracking,
           per confirmed scope). purchase_order_id stays optional — an
           invoice can be created without ever referencing a PO.
        10. Stamps BS-first audit fields via self._date_engine, same pattern
           as SupplierEngine._now_bs()/_now_ad()
        Raises ValidationError, DuplicateRecordError."""
        from engines.date_engine import ad_to_bs, DateEngineError  # noqa: F401

        # 1. validate header + lines
        is_valid, error = PurchaseValidator.validate_invoice_header(payload)
        if not is_valid:
            raise ValidationError(error)

        raw_lines = payload.get("lines") or []
        for raw_line in raw_lines:
            is_valid, error = PurchaseValidator.validate_invoice_line(raw_line)
            if not is_valid:
                raise ValidationError(error)
            is_valid, error = PurchaseValidator.validate_free_qty_rate(raw_line)
            if not is_valid:
                raise ValidationError(error)

        # 2. duplicate check (supplier + bill number)
        if self._model.exists_by_supplier_and_billno(
            supplier_id=payload["supplier_id"], invoice_number=payload["invoice_number"]
        ):
            raise DuplicateRecordError(
                f"Invoice number '{payload['invoice_number']}' already exists for this supplier."
            )

        # build DTOs from the raw payload lines
        lines: list[PurchaseInvoiceLineDTO] = []
        for raw_line in raw_lines:
            dto_line = PurchaseInvoiceLineDTO(
                item_id=raw_line["item_id"],
                batch_no=raw_line["batch_no"],
                expiry_month=int(raw_line["expiry_month"]),
                expiry_year=int(raw_line["expiry_year"]),
                qty=float(raw_line.get("qty") or 0.0),
                free_qty=float(raw_line.get("free_qty") or 0.0),
                purchase_rate=float(raw_line.get("purchase_rate") or 0.0),
                discount_percent=float(raw_line.get("discount_percent") or 0.0),
                cc_percent=0.0,  # resolved below
                mrp=float(raw_line.get("mrp") or 0.0),
                sale_rate=float(raw_line.get("sale_rate") or 0.0),
            )
            lines.append(dto_line)

        # 3. resolve CC% per line
        for dto_line in lines:
            dto_line.cc_percent = self._resolve_cc_percent(dto_line.item_id)

        # 4. allocate invoice-level charges
        total_freight = float(payload.get("total_freight") or 0.0)
        total_other = float(payload.get("total_other_charges") or 0.0)
        lines = self._allocate_invoice_level_charges(lines, total_freight, total_other)

        # 5. calculate per-line amounts (discount, cc, landing cost)
        lines = [self._calculate_line_amounts(dto_line) for dto_line in lines]

        # BS-first audit stamps (same pattern as SupplierEngine._now_bs()/_now_ad())
        now_ad = datetime.now(timezone.utc)
        try:
            now_bs = ad_to_bs(now_ad.date())
        except DateEngineError:
            logger.exception("Could not resolve BS date for purchase invoice audit stamp")
            now_bs = None

        raw_total = sum(
            (l.qty * l.purchase_rate) - l.discount_amount + l.cc_amount
            + l.freight_allocated + l.other_charges_allocated
            for l in lines
        )

        bill_discount_amount = round(float(payload.get("bill_discount_amount") or 0.0), 4)
        total_after_bill_discount = raw_total - bill_discount_amount

        grand_total = round(total_after_bill_discount)  # nearest whole rupee
        round_off_amount = round(grand_total - total_after_bill_discount, 2)

        internal_ref_number = self.generate_internal_ref_number()

        from engines.date_engine import bs_to_ad

        invoice_date_ad = bs_to_ad(payload["invoice_date_bs"])

        # NOTE: total_qty/total_gross_amount assume "paid" units (qty), not
        # including free_qty, matching how raw_total/grand_total are already
        # computed above (qty * purchase_rate, free units contribute 0 cost).
        total_qty = sum(l.qty for l in lines)
        total_gross_amount = sum(l.qty * l.purchase_rate for l in lines)
        total_discount_amount = sum(l.discount_amount for l in lines)
        total_cc_amount = sum(l.cc_amount for l in lines)

        # 6. insert header
        new_invoice_id = self._model.insert_invoice(
            {
                "internal_ref_number": internal_ref_number,
                "invoice_number": payload["invoice_number"],
                "supplier_id": payload["supplier_id"],
                "invoice_date_ad": invoice_date_ad,
                "invoice_date_bs": payload["invoice_date_bs"],
                "total_qty": round(total_qty, 4),
                "total_gross_amount": round(total_gross_amount, 4),
                "total_discount_amount": round(total_discount_amount, 4),
                "total_cc_amount": round(total_cc_amount, 4),
                "total_freight_amount": total_freight,
                "total_other_charges": total_other,
                "grand_total": round(grand_total, 4),
                "status": "Posted",
                "bill_discount_amount": bill_discount_amount,
                "round_off_amount": round_off_amount,
                "remarks": (payload.get("remarks") or "").strip() or None,
                "purchase_order_id": payload.get("purchase_order_id"),
                "created_by": current_user_id,
                "created_at_ad": now_ad,
                "created_at_bs": now_bs,
            }
        )

        # 7. insert each line, then delegate stock/batch creation to ItemEngine
        for dto_line in lines:
            invoice_item_id = self._model.insert_invoice_item(
                purchase_invoice_id=new_invoice_id,
                data={
                    "item_id": dto_line.item_id,
                    "batch_no": dto_line.batch_no,
                    "expiry_month": dto_line.expiry_month,
                    "expiry_year": dto_line.expiry_year,
                    "qty": dto_line.qty,
                    "free_qty": dto_line.free_qty,
                    "purchase_rate": dto_line.purchase_rate,
                    "discount_percent": dto_line.discount_percent,
                    "discount_amount": dto_line.discount_amount,
                    "cc_percent": dto_line.cc_percent,
                    "cc_amount": dto_line.cc_amount,
                    "freight_amount_allocated": dto_line.freight_allocated,
                    "other_charges_allocated": dto_line.other_charges_allocated,
                    "landing_cost_per_unit": dto_line.landing_cost_per_unit,
                    "mrp": dto_line.mrp,
                    "sale_rate": dto_line.sale_rate,
                },
            )

            existing_batch = self._item_engine.get_batch_by_no(dto_line.item_id, dto_line.batch_no)

            if existing_batch is not None:
                # Same batch number re-supplied -- add stock to the SAME
                # batch row (expiry/rate stay as originally recorded),
                # instead of raising a duplicate-batch-no error.
                item_batch = self._item_engine.post_stock_movement(
                    item_batch_id=existing_batch.item_batch_id,
                    transaction_type="PURCHASE",
                    quantity_change=dto_line.qty + dto_line.free_qty,
                    current_user_id=current_user_id,
                    reference_type="purchase_invoice",
                    reference_id=new_invoice_id,
                )
                item_batch_id = item_batch.item_batch_id
            else:
                item_batch = self._item_engine.add_batch(
                    item_id=dto_line.item_id,
                    batch_payload={
                        "batch_no": dto_line.batch_no,
                        "expiry_month": dto_line.expiry_month,
                        "expiry_year": dto_line.expiry_year,
                        "batch_qty": dto_line.qty + dto_line.free_qty,
                        # ItemEngine.add_batch()/item_batch table only tracks
                        # batch_purchase_rate -- MRP/Sale Rate/Landing Cost live
                        # on the purchase_invoice_item row (already inserted
                        # above), not on item_batch.
                        "batch_purchase_rate": dto_line.landing_cost_per_unit,
                    },
                    current_user_id=current_user_id,
                    transaction_type="PURCHASE",
                    reference_type="purchase_invoice",
                    reference_id=new_invoice_id,
                )
                item_batch_id = getattr(item_batch, "item_batch_id", None) or item_batch["item_batch_id"]

            dto_line.item_batch_id = item_batch_id

            # 8. stamp the resulting item_batch_id back onto the invoice line
            self._model.update_invoice_item_batch_link(
                purchase_invoice_item_id=invoice_item_id, item_batch_id=item_batch_id
            )

        # 9. mark linked PO as received, if any
        purchase_order_id = payload.get("purchase_order_id")
        if purchase_order_id:
            self._purchase_order_engine.mark_received(purchase_order_id, current_user_id)

        return PurchaseInvoiceDTO(
            purchase_invoice_id=new_invoice_id,
            internal_ref_number=internal_ref_number,
            invoice_number=payload["invoice_number"],
            supplier_id=payload["supplier_id"],
            invoice_date_bs=payload["invoice_date_bs"],
            grand_total=round(grand_total, 4),
            status="Posted",
            lines=lines,
            invoice_date_ad=str(invoice_date_ad),
        )

    def get_purchase_invoice(self, purchase_invoice_id: int, include_deleted: bool = False) -> PurchaseInvoiceDTO:
        row = self._model.get_by_id(purchase_invoice_id, include_deleted=include_deleted)
        if row is None:
            raise RecordNotFoundError(f"Purchase invoice {purchase_invoice_id} not found.")

        line_rows = self._model.get_items_by_invoice(purchase_invoice_id)
        lines = [
            PurchaseInvoiceLineDTO(
                item_id=r["item_id"],
                batch_no=r["batch_no"],
                expiry_month=r["expiry_month"],
                expiry_year=r["expiry_year"],
                qty=r["qty"],
                free_qty=r["free_qty"],
                purchase_rate=r["purchase_rate"],
                discount_percent=r["discount_percent"],
                cc_percent=r["cc_percent"],
                mrp=r["mrp"],
                sale_rate=r["sale_rate"],
                discount_amount=r["discount_amount"],
                cc_amount=r["cc_amount"],
                freight_allocated=r.get("freight_allocated", 0.0),
                other_charges_allocated=r.get("other_charges_allocated", 0.0),
                landing_cost_per_unit=r["landing_cost_per_unit"],
                item_batch_id=r.get("item_batch_id"),
            )
            for r in line_rows
        ]

        return PurchaseInvoiceDTO(
            purchase_invoice_id=row["purchase_invoice_id"],
            internal_ref_number=row["internal_ref_number"],
            invoice_number=row["invoice_number"],
            supplier_id=row["supplier_id"],
            invoice_date_bs=row["invoice_date_bs"],
            grand_total=row["grand_total"],
            status=row["status"],
            lines=lines,
        bill_discount_amount=row.get("bill_discount_amount", 0.0) or 0.0,
        round_off_amount=row.get("round_off_amount", 0.0) or 0.0,
        invoice_date_ad=str(row.get("invoice_date_ad")) if row.get("invoice_date_ad") else None,
        remarks=row.get("remarks"),
    )

    def search_purchase_invoices(
        self,
        search_text: Optional[str] = None,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
        order_by: Optional[str] = None,
        order_dir: str = "ASC",
    ) -> tuple[list[PurchaseInvoiceDTO], int]:
        filters = PurchaseInvoiceSearchFilters(
            search_text=search_text,
            supplier_id=supplier_id,
            status=status,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_dir=order_dir,
        )
        rows, total_count = self._model.search(filters)

        results = [
            PurchaseInvoiceDTO(
                purchase_invoice_id=r["purchase_invoice_id"],
                internal_ref_number=r["internal_ref_number"],
                invoice_number=r["invoice_number"],
                supplier_id=r["supplier_id"],
                invoice_date_bs=r["invoice_date_bs"],
                grand_total=r["grand_total"],
                status=r["status"],
                lines=[],  # list views don't hydrate lines — use get_purchase_invoice() for detail
            )
            for r in rows
        ]
        return results, total_count

    def cancel_purchase_invoice(self, purchase_invoice_id: int, current_user_id: int, reason: str) -> None:
        """Soft-delete only (project rule: no physical DELETE). Does NOT
        automatically reverse the stock_ledger entries — that reversal is a
        separate, explicit Purchase Return flow (Part-2, section 3), never
        an implicit side-effect of cancelling an invoice."""
        if not reason or not reason.strip():
            raise ValidationError("A cancellation reason is required.")

        existing = self._model.get_invoice_by_id(purchase_invoice_id, include_deleted=False)
        if existing is None:
            raise RecordNotFoundError(f"Purchase invoice {purchase_invoice_id} not found.")

        self._model.soft_delete_invoice(
            purchase_invoice_id=purchase_invoice_id,
            current_user_id=current_user_id,
            reason=reason,
        )